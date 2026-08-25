# Deployment Guide

This guide describes deployment on Linux with Gunicorn behind Nginx, backed by Redis.

**Gunicorn** is a WSGI application server that runs the Django app itself — it loads `weatherview_project` and executes the Python request-handling code. It listens on a local address (e.g. a Unix socket or `127.0.0.1`) and is managed as a systemd service so it starts on boot and restarts on failure.

**Nginx** is the reverse proxy that sits in front of Gunicorn and is the only process exposed to the internet. It terminates TLS, serves static assets (`weather/static/`) directly from disk instead of routing them through Django, and forwards dynamic requests to Gunicorn over the internal socket/port while adding headers like `X-Forwarded-For` so the app can see the real client IP.

The reason for using Gunicorn and Nginx instead of just `manage.py runserver` is that Django's built-in server is single-threaded, unencrypted, and explicitly documented as unfit for production — it can't handle concurrent requests safely or efficiently. Gunicorn provides multiple worker processes so the app can serve concurrent requests, while Nginx handles TLS termination, serves static files without invoking Python, and shields Gunicorn from being directly reachable from the internet.

**Redis** is the cache backend used to store cached Digitraffic/FMI responses and rate-limiting counters. It's needed because Gunicorn runs multiple worker processes: each worker is a separate process with its own memory, so an in-process cache (Django's LocMemCache) would give every worker its own inconsistent copy of the cache and rate-limit counts. Redis is external to all workers, so they share one consistent cache and rate limiter — which is what lets the app skip a Digitraffic/FMI call and serve a cached response whenever it already knows no new data is due yet.

## 1. Install system dependencies

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3 python3-venv git nginx redis-server
```

## 2. Clone and install

```bash
cd /opt
sudo mkdir weatherview && sudo chown $USER:$USER weatherview
git clone https://github.com/jjankkil/weatherview-django weatherview
cd weatherview

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

> **Important — build the venv in place.** Always create `.venv` directly inside
> `/opt/weatherview` (as above). Never build it in another directory and copy or
> move it here. Virtual environments are **not relocatable**: console scripts such
> as `gunicorn` have the interpreter's absolute path baked into their shebang, so a
> moved venv makes systemd fail to start Gunicorn with `status=203/EXEC`. If you
> ever see that error, rebuild the venv in place: `rm -rf .venv && python3 -m venv
> .venv && source .venv/bin/activate && pip install -r requirements.txt`.

## 3. Configure environment

Create `/opt/weatherview/.env` from the template:

```bash
cp /opt/weatherview/.env.example /opt/weatherview/.env
```

Then set at least:

```env
WVD_SECRET_KEY=<generate with: python3 -c "from django.utils.crypto import get_random_string; print(get_random_string(50))">
WVD_ALLOWED_HOSTS=<hostname-or-ip>,localhost
WVD_TRUSTED_PROXY_IPS=127.0.0.1
```

If this deployment will be reachable from the internet, `WVD_ALLOWED_HOSTS` must
include the actual public hostname(s) used to reach it, and you should also set
`WVD_CSRF_TRUSTED_ORIGINS` (scheme-qualified, e.g. `https://weather.example.com`) —
see [`CONFIGURATION.md`](CONFIGURATION.md) and [`INTERNET_ACCESS.md`](INTERNET_ACCESS.md).

> **Note:** `WVD_TRUSTED_PROXY_IPS=127.0.0.1` tells the rate limiter to trust the `X-Forwarded-For` header forwarded by Nginx (which connects from localhost). Without this, every request would be rate-limited against Nginx's IP instead of the real client IP.

Restrict permissions on the env file:

```bash
chmod 640 /opt/weatherview/.env
```

Collect static files:

```bash
source .venv/bin/activate
python manage.py collectstatic --noinput
```

## 4. Configure systemd

Create `/etc/systemd/system/weatherview.service`:

```ini
[Unit]
Description=WeatherView Django app
After=network.target redis.service

[Service]
User=<service-user>
EnvironmentFile=/opt/weatherview/.env
WorkingDirectory=/opt/weatherview
ExecStart=/opt/weatherview/.venv/bin/gunicorn weatherview_project.wsgi:application --bind 127.0.0.1:8000 --workers 4
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Set `User=` to the account that owns `/opt/weatherview` (the one used in step 2).
Prefer a dedicated service account over a general-purpose login account, and avoid
your distribution's well-known default user — service account names are a common
first guess in SSH brute-force attempts.

Enable and start the service:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now weatherview
```

Check status and logs:

```bash
sudo systemctl status weatherview
sudo journalctl -u weatherview -n 50
```

## 5. Configure HTTPS certificate

For private LAN-only setups, create a self-signed certificate:

```bash
sudo mkdir -p /etc/ssl/weatherview
sudo openssl req -x509 -nodes -days 3650 -newkey rsa:2048 \
  -keyout /etc/ssl/weatherview/key.pem \
  -out /etc/ssl/weatherview/cert.pem \
  -subj "/CN=<server-ip-or-hostname>" \
  -addext "subjectAltName=IP:<server-ip>"
```

Browsers will show a warning on first access. Accept the certificate for local/private usage.

**If the app needs to be reachable from the internet** (a real public hostname,
port-forwarded through a router, etc.), use a real Let's Encrypt certificate
instead of a self-signed one — see [`INTERNET_ACCESS.md`](INTERNET_ACCESS.md) for
the full setup, including DDNS, router firewall/NAT rules, and a DNS-01 Certbot
flow that never requires opening port 80. In short:

```bash
sudo apt install -y pipx
pipx install certbot
pipx inject certbot certbot-dns-duckdns   # or whichever DNS provider plugin applies

sudo ~/.local/bin/certbot certonly \
  --authenticator dns-duckdns \
  --dns-duckdns-credentials /etc/letsencrypt/duckdns.ini \
  -d <your-public-hostname>
```

then point the Nginx config below at
`/etc/letsencrypt/live/<your-public-hostname>/{fullchain,privkey}.pem` instead of
the self-signed paths — the certificate must exist *before* Nginx is configured to
reference it, since `nginx -t` (next section) will fail loudly if the certificate
file doesn't exist yet.

## 6. Configure Nginx

Create `/etc/nginx/sites-available/weatherview`:

```nginx
server {
    listen 80;
    server_name _;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl;
    server_name _;

    ssl_certificate     /etc/ssl/weatherview/cert.pem;
    ssl_certificate_key /etc/ssl/weatherview/key.pem;

    location /static/ {
        alias /opt/weatherview/staticfiles/;
        add_header Cache-Control "no-cache";
    }

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
    }
}
```

> The Django app trusts `X-Forwarded-For` only from addresses listed in `WVD_TRUSTED_PROXY_IPS`. Since Nginx connects from `127.0.0.1`, set `WVD_TRUSTED_PROXY_IPS=127.0.0.1` in your `.env`.

Enable the site:

```bash
sudo ln -s /etc/nginx/sites-available/weatherview /etc/nginx/sites-enabled/
sudo rm /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl restart nginx
```

## Updating after changes

After pulling updates, **always run `collectstatic`** — do not skip it. Nginx serves
CSS/JS from `/opt/weatherview/staticfiles/` (see the `location /static/` block above),
which is populated only by `collectstatic`. The `index.html` template is rendered live
by Django, but the static assets are not: if you restart Gunicorn without re-collecting,
Nginx keeps serving the **old** CSS/JS against the **new** HTML, which silently breaks
layout and client-side rendering (e.g. missing forecast/history, panels no longer shown
side by side). When in doubt, run it — it is cheap and idempotent.

```bash
cd /opt/weatherview
source .venv/bin/activate
git pull
pip install -r requirements.txt      # in case dependencies changed
python manage.py collectstatic --noinput
sudo systemctl restart weatherview
sudo systemctl status weatherview
```

Static filenames are not content-hashed, so the `location /static/` block sends
`Cache-Control: no-cache`, forcing browsers to revalidate (a cheap 304 when unchanged)
instead of trusting a cached copy. If a deployed Nginx config predates this header, add it
manually and `sudo systemctl reload nginx`, or hard-refresh the browser (Ctrl+Shift+R) once
as a one-off workaround.
