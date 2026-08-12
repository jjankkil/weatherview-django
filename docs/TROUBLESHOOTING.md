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

## Site loads on LAN but times out / 400s from the internet

See [`INTERNET_ACCESS.md`](INTERNET_ACCESS.md) for the full runbook and a detailed
list of pitfalls specific to exposing this app publicly (DDNS, router NAT/firewall,
TLS via DNS-01). Common causes, roughly in the order to check them:

- `WVD_ALLOWED_HOSTS` in the **live** `.env` (at the deployment path, not a separate
  git checkout) doesn't include the public hostname → Django returns HTTP 400.
- The router's port-forward/firewall rules don't actually match WAN-sourced traffic,
  or a broad deny rule is unintentionally also dropping return traffic for
  already-established connections (needs `connection-state=new` to avoid this).
- A "genuinely external" test device is actually still on the LAN (confirm with
  `curl -s https://ifconfig.me` before trusting a mobile-hotspot test).
- A LAN device resolving the public hostname hits NAT hairpin and lands on the
  router's own admin page instead of the app — needs a split-horizon local DNS
  override, not a firewall change.

## DNS resolution suddenly stops working on the server

Symptom:

- `curl`/`requests` fail with resolution errors even though `/etc/resolv.conf`
  looks correct, or `getent hosts <name>` fails while `nslookup <name> <server>`
  (with an explicit server argument) succeeds.

Cause:

- These two tools use different resolution paths. `nslookup <name> <server>`
  bypasses the system resolver; `getent hosts` (and Python's
  `socket.gethostbyname`, which `requests`/Django actually use) goes through the
  real NSS/glibc chain — trust that one as reflecting what the app actually
  experiences.
- Installing `systemd-resolved`/`resolvectl` on a system that wasn't previously
  using it can silently take over `/etc/resolv.conf` and end up in a broken,
  half-started state (`resolvectl status` hanging with "Connection timed out" is
  a tell). If resolution worked before the install and the service is only needed
  for a diagnostic tool, purging it is usually the fastest fix:
  ```bash
  sudo apt purge systemd-resolved libnss-resolve
  sudo rm -f /etc/resolv.conf
  # then let your normal network manager (NetworkManager / ifupdown+dhclient)
  # regenerate it, or write it manually as a fallback:
  echo "nameserver <your-dns-server>" | sudo tee /etc/resolv.conf
  ```
- Check `/etc/NetworkManager/NetworkManager.conf` for `[ifupdown] managed=false` —
  if present, NetworkManager isn't actually managing the interface at all and
  restarting it won't regenerate `resolv.conf`; that's `ifupdown`/`dhclient`'s job
  on that system instead.

## Quick health commands

```bash
sudo systemctl status weatherview
sudo journalctl -u weatherview -n 100
sudo systemctl status nginx
sudo nginx -t
```
