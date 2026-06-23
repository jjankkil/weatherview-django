# Troubleshooting

## Service fails with missing secret key

Symptom:

- systemd journal shows `KeyError: 'WVD_SECRET_KEY'`

Checks:

- Ensure `/opt/weatherview/.env` exists
- Ensure `EnvironmentFile=` path in `weatherview.service` is correct
- Ensure `.env` contains `WVD_SECRET_KEY`
- Ensure service user can read file (`chmod 640 /opt/weatherview/.env`)

## App works with one worker but not multiple

Symptom:

- Inconsistent cache behavior with multiple Gunicorn workers

Cause:

- `WVD_REDIS_URL` is not set and LocMem cache is process-local

Fix:

- Configure Redis and set `WVD_REDIS_URL`
- Restart service

## Geolocation not available in browser

Symptom:

- Browser denies location access or geolocation API is unavailable

Cause:

- Geolocation typically requires HTTPS (or localhost exception)

Fix:

- Use HTTPS in deployment
- For private LAN, use self-signed certificate and trust it in browser

## Nginx starts but app is unreachable

Checks:

- Validate Nginx config: `sudo nginx -t`
- Confirm Gunicorn is running: `sudo systemctl status weatherview`
- Confirm proxy target matches Gunicorn bind (`127.0.0.1:8000`)
- Check firewall and listen ports (80/443)

## Static files not updating

Fix:

```bash
source /opt/weatherview/.venv/bin/activate
python manage.py collectstatic --noinput
sudo systemctl restart weatherview
```

## Quick health commands

```bash
sudo systemctl status weatherview
sudo journalctl -u weatherview -n 100
sudo systemctl status nginx
sudo nginx -t
```
