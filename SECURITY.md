# Security Policy

## Reporting a vulnerability

Please report security issues privately through GitHub, **not** as a public issue:

1. Go to the [Security tab](https://github.com/jjankkil/weatherview-django/security)
2. Click **Report a vulnerability**
3. Describe the issue and, if possible, how to reproduce it

This opens a private advisory visible only to you and the maintainer.

This is a personal hobby project maintained in spare time, so there is no
guaranteed response window — expect a reply within a couple of weeks. There is no
bug bounty.

## Scope

WeatherView is a self-hosted Django application. Reports are in scope if they
concern the application code, its default configuration, or the deployment
guidance in [docs/](docs/) — for example authentication or CSRF weaknesses, injection
flaws, secrets exposure, or advice in
[docs/INTERNET_ACCESS.md](docs/INTERNET_ACCESS.md) that would leave an exposed
instance insecure.

Out of scope:

- Vulnerabilities in upstream dependencies — report those to the project
  concerned; Dependabot alerts cover them here
- Issues in the third-party weather APIs (FMI, Digitraffic, OpenWeatherMap)
- Findings that require an already-compromised host or an attacker-supplied
  `WVD_SECRET_KEY`
- Missing hardening on a deployment that ignores [docs/INTERNET_ACCESS.md](docs/INTERNET_ACCESS.md)

## Deploying safely

If you run this on the public internet, follow
[docs/INTERNET_ACCESS.md](docs/INTERNET_ACCESS.md). At minimum: set a strong
`WVD_SECRET_KEY`, set `WVD_ALLOWED_HOSTS` and `WVD_CSRF_TRUSTED_ORIGINS` to your
own hostname, terminate TLS at a reverse proxy, and set `WVD_TRUSTED_PROXY_IPS`
so client IPs are only read from `X-Forwarded-For` when that proxy is in front.
