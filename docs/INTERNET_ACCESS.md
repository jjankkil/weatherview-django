# Exposing weatherview-django to the Internet — Runbook

A from-scratch guide for making this app reachable from the public internet while
keeping the server on an isolated network segment behind a home router/firewall.
The network-layer steps here are described in generic terms — the underlying
concepts (NAT port-forwarding, stateful firewall rules, split-horizon DNS) apply
broadly across consumer/prosumer router and firewall platforms, but the exact
CLI/UI syntax will differ by platform. If you keep platform- or vendor-specific
command notes for your own hardware, store them outside this repo or in a
git-ignored path (e.g. `docs/private/`) rather than committing them — router
vendor/model isn't secret information exactly, but there's no reason to hand an
attacker a head start on which platform-specific exploits to try first.

This assumes you already have (or will set up separately, not covered here):

- A router with a public IPv4 address directly on its WAN interface (not behind
  ISP CGNAT — check this first; if you're behind CGNAT, port-forwarding won't work
  and you'd need a different approach, e.g. a VPN or a relay service).
- The app server placed on its own isolated network segment, separate from your
  main LAN, with a static IP/DHCP lease. Setting up that isolation is a separate
  exercise — this guide assumes it already exists and is trusted.
- A free [DuckDNS](https://www.duckdns.org) account (or any other dynamic DNS
  provider with a similar update API and, ideally, a Certbot DNS-01 plugin).

Placeholders used throughout:

| Placeholder | Meaning |
|---|---|
| `<SERVER_IP>` | Static IP of the app server on its network segment |
| `<WAN_IFACE>` | Router's WAN-facing interface |
| `<PUBLIC_HOSTNAME>` | Your dynamic DNS hostname |
| `<DDNS_TOKEN>` | Your dynamic DNS provider's account token |

---

## 1. Django app readiness (do this first, before exposing anything)

- `WVD_DEBUG` must be `False`.
- `WVD_ALLOWED_HOSTS` must include every public hostname you'll use:
  ```env
  WVD_ALLOWED_HOSTS=localhost,127.0.0.1,<PUBLIC_HOSTNAME>
  ```
- `WVD_CSRF_TRUSTED_ORIGINS` must list the same hostname(s), scheme-qualified:
  ```env
  WVD_CSRF_TRUSTED_ORIGINS=https://<PUBLIC_HOSTNAME>
  ```
- `WVD_TRUSTED_PROXY_IPS=127.0.0.1` should already be set (required for correct
  per-IP rate limiting behind Nginx — see [`CONFIGURATION.md`](CONFIGURATION.md)).

Remember: **the live `.env` is the one at the deployment path** (e.g.
`/opt/weatherview/.env`), not a separate git checkout on another machine. Confirm
which file the running service's `EnvironmentFile=` actually points at, and restart
the service after any change:

```bash
sudo systemctl restart weatherview
```

This app has no `django.contrib.admin` or `django.contrib.auth` installed, so
there's no login/admin surface to worry about — if a future version adds one,
treat exposing it publicly as a new, separate risk to assess.

---

## 2. Dynamic DNS

Using a DNS provider independent of your router's hardware (rather than a
router-vendor DDNS service tied to a serial number) means replacing the router
later doesn't cost you your hostname, and a provider with an official Certbot
DNS-01 plugin (DuckDNS is one; several others exist) lets you issue and renew a
real certificate without ever opening port 80.

1. Register your hostname(s) with your chosen provider and note the account token.
2. Have your **router** push the periodic update (rather than the app server) —
   this keeps the server's own outbound access narrow, and the router already has
   the real public IP. Most routers can run a scheduled script/cron job that
   fetches the provider's update URL, e.g. (illustrative, adapt to your platform):
   ```bash
   curl "https://www.duckdns.org/update?domains=<PUBLIC_HOSTNAME>&token=<DDNS_TOKEN>&ip="
   ```
   run on a schedule (every few minutes is plenty).

**Verify from a genuinely external network** (mobile data with WiFi off — see the
pitfall about this in §7): confirm the hostname resolves to your real public IP
using an external DNS server, e.g. `nslookup <PUBLIC_HOSTNAME> 8.8.8.8`.

---

## 3. Router: port-forwarding and firewall rules

These are the network-layer requirements; translate them into your specific
router/firewall's rule syntax.

### 3.1 Port-forward (NAT) to the app server

Forward WAN ports 80 and 443 to `<SERVER_IP>` ports 80 and 443 respectively.
Illustrative `iptables`-equivalent form, for routers that expose a Linux
netfilter-based firewall directly:

```bash
iptables -t nat -A PREROUTING -i <WAN_IFACE> -p tcp --dport 443 -j DNAT --to-destination <SERVER_IP>:443
iptables -t nat -A PREROUTING -i <WAN_IFACE> -p tcp --dport 80  -j DNAT --to-destination <SERVER_IP>:80
```

### 3.2 Explicit accept for the forwarded flow

Many routers default to "accept" for forwarded traffic once a NAT rule matches,
but some don't — check that traffic reaching `<SERVER_IP>` on 80/443 from the WAN
side is explicitly allowed by your firewall's forward chain, not just relying on
an implicit default (see the first pitfall in §7).

### 3.3 Narrow LAN → server access to only the ports it needs

If your main LAN is allowed to reach the isolated server, restrict that rule to
the ports actually needed (e.g. 22/80/443) rather than leaving it open to
everything.

### 3.4 Lock down the server's own outbound (egress) traffic

Once the server is internet-facing, restrict what it can initiate outbound —
defense in depth if it's ever compromised. Identify what the app actually needs
from its own source code (don't guess a plausible-looking domain — see §7), and
check whether it does its own NTP time sync directly to the internet
(`timedatectl timesync-status` on the server), which needs UDP 123 in addition to
HTTPS (443).

**Important**: any deny rule blocking the server's *new* outbound connections must
be scoped to new connections only (e.g. `--ctstate NEW` in iptables terms, or your
firewall's equivalent connection-state match). Without that scoping, the same rule
will also drop *return* traffic for connections that external visitors initiated
inbound to your server — see §7 for why this is easy to miss.

### 3.5 Split-horizon DNS for local/LAN access

Devices on your own LAN resolving the public hostname and connecting to your own
public IP will often hit a routing quirk (NAT hairpinning): the router may treat
that traffic as destined for itself rather than forwarding it on, since the
LAN-sourced packet doesn't arrive via the WAN interface. Symptom: your router's
own admin login page appears instead of the app. The simplest fix is a local DNS
override on your router/DNS server, mapping the public hostname directly to
`<SERVER_IP>` for LAN clients, so they skip the round-trip through the public IP
entirely. The browser's TLS handshake still uses the hostname (SNI), so the
certificate still matches correctly even though the name resolves to a private
address locally.

---

## 4. TLS certificate (Let's Encrypt, DNS-01)

DNS-01 avoids ever needing port 80 open for certificate issuance or renewal — the
challenge is answered as a DNS record, not an HTTP request. Example using DuckDNS's
plugin (substitute your own provider's plugin if different):

```bash
sudo apt install -y pipx
pipx install certbot
pipx inject certbot certbot-dns-duckdns

sudo mkdir -p /etc/letsencrypt
printf 'dns_duckdns_token = <DDNS_TOKEN>\n' | sudo tee /etc/letsencrypt/duckdns.ini
sudo chmod 600 /etc/letsencrypt/duckdns.ini

sudo ~/.local/bin/certbot certonly \
  --authenticator dns-duckdns \
  --dns-duckdns-credentials /etc/letsencrypt/duckdns.ini \
  --dns-duckdns-propagation-seconds 60 \
  -d <PUBLIC_HOSTNAME>
```

Certbot's own systemd timer handles renewal automatically. Verify the cert exists
before touching Nginx config:

```bash
sudo ls -l /etc/letsencrypt/live/<PUBLIC_HOSTNAME>/
```

**Order matters**: issue the cert *before* pointing Nginx at its file paths —
`nginx -t` will fail with a clear "no such file" error otherwise. That failure is
a useful sanity check, but it does mean the two steps have to be done in this
order.

---

## 5. Nginx

Update the TLS server block to point at the real certificate and list the public
hostname (the `location` blocks proxying to Gunicorn/static files don't change):

```nginx
server {
    listen 443 ssl;
    server_name <PUBLIC_HOSTNAME> <SERVER_IP> <your-local-hostnames>;
    ssl_certificate     /etc/letsencrypt/live/<PUBLIC_HOSTNAME>/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/<PUBLIC_HOSTNAME>/privkey.pem;
    # ... location blocks unchanged from DEPLOYMENT.md ...
}
```

Before assuming which file to edit, confirm what's actually enabled — files in
`sites-available/` that aren't symlinked into `sites-enabled/` are never loaded,
which is easy to mistake for a routing bug that isn't actually there:

```bash
ls -la /etc/nginx/sites-available/ /etc/nginx/sites-enabled/
grep -l "proxy_pass" /etc/nginx/sites-available/*
```

Then:

```bash
sudo nginx -t
sudo systemctl reload nginx
```

---

## 6. Verification checklist

Run through all of these — don't stop at the first thing that seems to work.

1. **Genuinely external reachability.** Confirm your test device is actually off
   your own network (`curl -s https://ifconfig.me`, compare against your real home
   WAN IP) before trusting a "mobile hotspot" test — phones can stay on WiFi
   without it being obvious.
   ```bash
   curl -v https://<PUBLIC_HOSTNAME>
   ```
2. **Certificate correctness**:
   ```bash
   openssl s_client -connect <PUBLIC_HOSTNAME>:443 -servername <PUBLIC_HOSTNAME> </dev/null 2>/dev/null | openssl x509 -noout -dates -issuer -subject
   ```
3. **HSTS present** (confirms `DEBUG=False` is actually live, not just in a `.env`
   file somewhere):
   ```bash
   curl -sI https://<PUBLIC_HOSTNAME> | grep -i strict-transport
   ```
4. **Only the intended ports are reachable from WAN**:
   ```bash
   nc -zv -w3 <PUBLIC_HOSTNAME> 22
   nc -zv -w3 <PUBLIC_HOSTNAME> 8000
   ```
   Both should time out/refuse.
5. **Server egress is actually restricted** (on the server):
   ```bash
   curl -m5 https://<a real API domain the app calls>   # should succeed
   curl -m5 http://example.com                            # should time out
   timedatectl timesync-status                            # should still show recent sync
   ```
6. **LAN access still works** (via the split-horizon override).

---

## 7. Pitfalls and misleading failure modes

Several of the failure modes in this setup present symptoms that point at the
wrong layer — a firewall problem that looks like a DNS problem, a routing quirk
that looks like a certificate error. Work through these before concluding that a
step failed for the reason it appears to have failed.

- **Don't assume a rule is doing something just because nothing complained.**
  Router/firewall CLIs can silently no-op an edit that references something (like
  a rule name/comment) that doesn't match exactly. After any rule change, print
  the current ruleset back out and check the actual fields — don't trust a clean
  return code alone.
- **Many firewalls default to accept for traffic nothing else matches.** Narrowing
  an *allow* rule's ports doesn't block anything by itself if there's no
  corresponding explicit *deny* — you need both the narrowed allow and an explicit
  deny for it to actually be a restriction.
- **A deny rule for "new outbound connections" needs to be scoped to new
  connections only, or it also drops return traffic for connections initiated in
  the other direction.** Response packets from your server back to an
  externally-initiated (forwarded) connection share the same source
  address/interface as genuinely new outbound connections the server might
  initiate itself — an unscoped deny rule placed ahead of the established/related
  accept rules will break inbound connections' replies, not just outbound egress.
- **NAT hairpin**: a LAN device resolving your public hostname and connecting to
  your own public IP does not automatically get redirected to the internal server.
  Symptom: your router's own admin login page appears instead of the app,
  sometimes with a certificate warning. Fix: split-horizon local DNS (§3.5), not a
  NAT rule change.
- **A "mobile hotspot" test device can silently still be on your home WiFi.**
  Always confirm with `curl -s https://ifconfig.me` before trusting a test as
  "external."
- **`getent hosts <name>` and `nslookup <name> <server>` can give different
  answers.** `nslookup` with an explicit server argument bypasses the normal
  system resolver path entirely. `getent hosts` (and Python's
  `socket.gethostbyname`, which `requests`/Django actually use) goes through the
  real resolver chain — trust that one as reflecting what the app actually
  experiences.
