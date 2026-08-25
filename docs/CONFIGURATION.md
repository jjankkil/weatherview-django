# Configuration Reference

The application reads configuration from environment variables, which are typically defined in a `.env` file at the project root (see `.env.example` for a template).

## Required

- `WVD_SECRET_KEY`
  - Required for startup.
  - Generate example:

```bash
python -c "from django.utils.crypto import get_random_string; print(get_random_string(50))"
```

## Recommended for production

- `WVD_DEBUG`
  - Enables Django debug mode when set to `True`.
  - Default: `False`
  - Must be `False` in production — never enable this on a deployment reachable by anyone but you.

- `WVD_ALLOWED_HOSTS`
  - Comma-separated hostnames/IPs allowed by Django.
  - Default: `localhost,127.0.0.1`
  - Example: `WVD_ALLOWED_HOSTS=weather.local,192.168.1.10,localhost`
  - If the app is reachable from the internet, this must include every public
    hostname used to reach it (e.g. a DDNS name), not just LAN names/IPs.

- `WVD_CSRF_TRUSTED_ORIGINS`
  - Comma-separated, scheme-qualified origins trusted for CSRF-checked (unsafe)
    requests, e.g. `WVD_CSRF_TRUSTED_ORIGINS=https://weather.example.com`.
  - Empty by default (fine for LAN-only deployments). Set this once the app is
    reachable over HTTPS through a public hostname, especially if TLS terminates
    at a reverse proxy — it's cheap insurance against proxy header quirks tripping
    the CSRF referer check on the app's one POST endpoint (`/api/settings/save/`).

## Optional runtime settings

- `WEATHER_RATE_LIMIT`
  - Per-IP API limit for weather endpoint.
  - Default: `15/m`

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
  - Default: `0` when `WVD_DEBUG=True`, `31536000` otherwise.

- `WVD_REDIS_URL`
  - Redis cache URL.
  - Example: `redis://localhost:6379/0`
  - If omitted, application uses Django LocMem cache.

- `WVD_DIGITRAFFIC_BASE_URL`
  - Base URL for the Digitraffic road-weather API (station list, station data, station history).
  - Default: `https://tie.digitraffic.fi/api/weather/v1`
  - Test-only — lets the Robot Framework E2E suite point the app at a local
    fixture server instead of the real API (see `tests/robot/fixtures/fixture_server.py`).
    Not meant to be set in normal development or production `.env` files.

## Cache behavior

- Production multi-worker deployments should use Redis.
- Without `WVD_REDIS_URL`, run single-worker app instances to avoid process-local cache divergence.

## Session settings

The app also stores a small set of user preferences in signed-cookie sessions:

- `language` (`fi`, `sv`, or `en`)
- `show_camera` (boolean)
- `show_history` (boolean)
- `history_hours` (integer from 1 to 24)
- `current_station_id` / `current_station_name`

## Example .env

```env
WVD_SECRET_KEY=<your-secret>
WVD_DEBUG=False
WVD_ALLOWED_HOSTS=localhost,127.0.0.1
# WVD_CSRF_TRUSTED_ORIGINS=https://weather.example.com  # set once reachable over public HTTPS
WEATHER_RATE_LIMIT=15/m
WVD_SESSION_COOKIE_AGE=604800
WVD_SECURE_HSTS_SECONDS=31536000
WVD_TRUSTED_PROXY_IPS=127.0.0.1
# WVD_REDIS_URL=redis://localhost:6379/0
```

## Exposing the app to the internet

If you're making this deployment reachable from outside your LAN (port-forwarding,
DDNS, a public certificate, firewall hardening on the router side, etc.), see
[`INTERNET_ACCESS.md`](INTERNET_ACCESS.md) for the full runbook — it covers the
DNS, TLS, and network-level steps that are out of scope for this file.
