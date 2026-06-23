# Deployment Guide

This guide describes deployment on Linux (tested on Raspberry Pi 3, Debian Bookworm) with Gunicorn behind Nginx.

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

## 3. Configure environment

Create `/opt/weatherview/.env` from the template:

```bash
cp /opt/weatherview/.env.example /opt/weatherview/.env
```

Then set at least:

```env
WVD_SECRET_KEY=<generate with: python3 -c "from django.utils.crypto import get_random_string; print(get_random_string(50))">
WVD_ALLOWED_HOSTS=<hostname-or-ip>,localhost
```

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
User=pi
EnvironmentFile=/opt/weatherview/.env
WorkingDirectory=/opt/weatherview
ExecStart=/opt/weatherview/.venv/bin/gunicorn weatherview_project.wsgi:application --bind 127.0.0.1:8000 --workers 4
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

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

## 5. Configure Nginx

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

Enable the site:

```bash
sudo ln -s /etc/nginx/sites-available/weatherview /etc/nginx/sites-enabled/
sudo rm /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl restart nginx
```

## 6. Configure HTTPS certificate

For private LAN setups, create a self-signed certificate:

```bash
sudo mkdir -p /etc/ssl/weatherview
sudo openssl req -x509 -nodes -days 3650 -newkey rsa:2048 \
  -keyout /etc/ssl/weatherview/key.pem \
  -out /etc/ssl/weatherview/cert.pem \
  -subj "/CN=<server-ip-or-hostname>" \
  -addext "subjectAltName=IP:<server-ip>"
```

Browsers will show a warning on first access. Accept the certificate for local/private usage.

## Updating after changes

After pulling updates:

```bash
# If only Python files changed
sudo systemctl restart weatherview

# If static assets changed
source /opt/weatherview/.venv/bin/activate
python manage.py collectstatic --noinput
sudo systemctl restart weatherview

sudo systemctl status weatherview
```
