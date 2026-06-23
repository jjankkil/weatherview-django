# Configuration Reference

The application reads configuration from environment variables.

## Required

- `WVD_SECRET_KEY`
  - Required for startup.
  - Generate example:

```bash
python -c "from django.utils.crypto import get_random_string; print(get_random_string(50))"
```

## Recommended for production

- `WVD_ALLOWED_HOSTS`
  - Comma-separated hostnames/IPs allowed by Django.
  - Example: `WVD_ALLOWED_HOSTS=weather.local,192.168.1.10,localhost`

## Optional runtime settings

- `WEATHER_RATE_LIMIT`
  - Per-IP API limit for weather endpoint.
  - Example default used in docs: `15/m`

- `WVD_TRUSTED_PROXY_IPS`
  - Comma-separated list of reverse-proxy IP addresses whose `X-Forwarded-For` header is trusted for per-IP rate limiting.
  - **Required in production when behind Nginx or any reverse proxy** — without this, all users share one rate-limit bucket (the proxy's IP).
  - Example: `WVD_TRUSTED_PROXY_IPS=127.0.0.1`
  - Default: empty (no proxy trusted; `REMOTE_ADDR` is used directly).

- `WVD_SESSION_COOKIE_AGE`
  - Session cookie lifetime in seconds.
  - Default: `604800` (7 days)

- `WVD_SECURE_HSTS_SECONDS`
  - HSTS duration in seconds.
  - Example: `31536000`

- `WVD_REDIS_URL`
  - Redis cache URL.
  - Example: `redis://localhost:6379/0`
  - If omitted, application uses Django LocMem cache.

## Cache behavior

- Production multi-worker deployments should use Redis.
- Without `WVD_REDIS_URL`, run single-worker app instances to avoid process-local cache divergence.

## Example .env

```env
WVD_SECRET_KEY=<your-secret>
WVD_ALLOWED_HOSTS=localhost,127.0.0.1
WEATHER_RATE_LIMIT=15/m
WVD_SESSION_COOKIE_AGE=604800
WVD_SECURE_HSTS_SECONDS=31536000
WVD_TRUSTED_PROXY_IPS=127.0.0.1
# WVD_REDIS_URL=redis://localhost:6379/0
```
