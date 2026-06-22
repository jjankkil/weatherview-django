# weatherview-django

A browser-based road weather viewer for Finnish roads. Displays live observations from [Digitraffic](https://www.digitraffic.fi/) road weather stations together with an optional short-range forecast from [OpenWeatherMap](https://openweathermap.org/).

Pick any of 400+ Finnish road weather stations and see current observations, FMI feels-like temperature, wind, visibility, present weather and an optional short-range forecast — all in the browser.

<img src="docs/screenshot.png" alt="Screenshot of the Tiesää web UI" width="80%">

---

## Features

- 🛣️ More than 400 Finnish road weather stations (Digitraffic open data)
- 🌡️ Air temperature with FMI feels-like calculation
- 💨 Wind speed (avg / max), direction with cardinal text
- 💧 Humidity, dew point, road surface temperature, visibility, temperature rate of change, present weather
- 🌦️ Forecast carousel: 3-hourly slots for the rest of today (labeled e.g. _Ma 9–12_), followed by one daily summary per future day (up to 5 days from OWM); paginated in groups of three + current weather symbol
- FI/SV/EN Finnish/Swedish/English UI toggle
- 🔄 Server-driven auto-refresh: the frontend schedules its next fetch only when the server signals new data is due; no blind fallback polling
- ⭐ 5-item MRU station list, persisted in browser `localStorage`
- ⏳ Wait cursor + dimmed card while loading
- 📍 Automatic nearest-station selection using the browser Geolocation API (on first visit or when "Use my location" is enabled in Settings)
- 💾 Session-based settings (current station, language, camera visibility, follow-location)
- 🔒 Application-level OpenWeatherMap API key — no per-user key required
- 🚦 Built-in IP-based rate limiting on the weather API endpoint (configurable)
- 🚀 In-memory station-list cache (5 min) — no repeated 447-row downloads
- ⚡ Per-station observation cache — Digitraffic is only queried by the scheduled auto-refresh; manual refreshes and page reloads are served from cache

No database required. Settings live in signed-cookie sessions; observation data is cached per station and refreshed only when new data is expected.

---

## Quick start

### Requirements

- Python **3.11+** (tested on 3.13)
- Internet access (Digitraffic + OpenWeatherMap)

### Install & run

```bash
git clone https://github.com/jjankkil/weatherview-django
cd weatherview-django

python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # Linux / macOS

pip install -r requirements.txt
```

Copy `.env.example` to `.env` and fill in the required values:

```bash
cp .env.example .env
```

```env
WVD_SECRET_KEY=<generate with: python -c "from django.utils.crypto import get_random_string; print(get_random_string(50))">
OPENWEATHER_API_KEY=<your OpenWeatherMap API key>
```

Then start the development server:

```bash
# Windows PowerShell
.\startup.ps1

# Windows CMD
startup.bat

# Linux / macOS / WSL
./startup.sh
```

Or manually:

```bash
WVD_SECRET_KEY=... OPENWEATHER_API_KEY=... python manage.py runserver
```

Then open <http://127.0.0.1:8000/> in your browser.

### OpenWeatherMap API key

Weather symbols and forecast data require an OpenWeatherMap API key. The key is configured once by the application operator (in `.env` or the server environment) — users do not need their own key.

Register a free account at <https://openweathermap.org/> to obtain a key.

---

## Deployment on Linux

This section describes deploying the app on a Linux server (tested on Raspberry Pi 3, Debian Bookworm). The stack is **Gunicorn** behind **Nginx**.

### 1. Install system dependencies

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3 python3-venv git nginx
```

### 2. Clone and install

```bash
cd /opt
sudo mkdir weatherview && sudo chown $USER:$USER weatherview
git clone https://github.com/jjankkil/weatherview-django weatherview
cd weatherview

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Configure environment

The app **will not start** without `WVD_SECRET_KEY` and `OPENWEATHER_API_KEY` set. Create `/opt/weatherview/.env` from the provided template:

```bash
cp /opt/weatherview/.env.example /opt/weatherview/.env
```

Then edit `/opt/weatherview/.env` and fill in the required values:

```env
# Required — the service will crash on startup if either of these is missing or left as the placeholder
WVD_SECRET_KEY=<generate with: python3 -c "from django.utils.crypto import get_random_string; print(get_random_string(50))">
OPENWEATHER_API_KEY=<your OpenWeatherMap API key>

# Recommended — restrict which hostnames Django accepts
WVD_ALLOWED_HOSTS=<hostname-or-ip>,localhost

# Optional — shown with defaults
WEATHER_RATE_LIMIT=15/m
WVD_SESSION_COOKIE_AGE=1209600
WVD_SECURE_HSTS_SECONDS=31536000
```

Restrict permissions so the key is not world-readable:

```bash
chmod 640 /opt/weatherview/.env
```

Collect static files (run with venv active):

```bash
source .venv/bin/activate
python manage.py collectstatic --noinput
```

### 4. Systemd service

Create `/etc/systemd/system/weatherview.service`:

```ini
[Unit]
Description=WeatherView Django app
After=network.target

[Service]
User=pi
EnvironmentFile=/opt/weatherview/.env
WorkingDirectory=/opt/weatherview
ExecStart=/opt/weatherview/.venv/bin/gunicorn weatherview_project.wsgi:application --bind 127.0.0.1:8000 --workers 1
; Single worker required: the station list cache and IP rate limiter use LocMemCache,
; which is not shared across processes. Scale with multiple instances behind a load
; balancer, or swap to Redis if you need multiple workers.
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now weatherview
```

Check that the service started without errors:

```bash
sudo systemctl status weatherview
sudo journalctl -u weatherview -n 50
```

If you see `KeyError: 'WVD_SECRET_KEY'` in the journal, the `.env` file is missing, has wrong permissions, or the `EnvironmentFile=` path is incorrect.

### 5. Nginx

Nginx handles the HTTP→HTTPS redirect and terminates TLS. Django is configured to trust Nginx's `X-Forwarded-Proto` header, so no changes to `settings.py` are needed.

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

```bash
sudo ln -s /etc/nginx/sites-available/weatherview /etc/nginx/sites-enabled/
sudo rm /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl restart nginx
```

### 6. HTTPS with a self-signed certificate

HTTPS is required for the browser Geolocation API. For a private LAN, a self-signed certificate is sufficient.

```bash
sudo mkdir -p /etc/ssl/weatherview
sudo openssl req -x509 -nodes -days 3650 -newkey rsa:2048 \
  -keyout /etc/ssl/weatherview/key.pem \
  -out /etc/ssl/weatherview/cert.pem \
  -subj "/CN=<server-ip-or-hostname>" \
  -addext "subjectAltName=IP:<server-ip>"
```

On first visit the browser will warn about the self-signed certificate — click **Advanced → Proceed** to accept it.

### Updating

After a `git pull`:

```bash
# If only Python files changed:
sudo systemctl restart weatherview

# If static files (CSS/JS) also changed:
source /opt/weatherview/.venv/bin/activate
python manage.py collectstatic --noinput
sudo systemctl restart weatherview
```

---

## Usage

| Element                  | What it does                                                                                                                   |
| ------------------------ | ------------------------------------------------------------------------------------------------------------------------------ |
| Station dropdown         | Pick any station. Most-recently-used 5 are grouped at the top.                                                                 |
| 🔍 Search button         | Open a search modal — type any part of a station name to filter and select it.                                                 |
| 🌐 Top-right button      | Toggle between Finnish, Swedish, and English. Labels, wind direction, and weather condition values all switch language.        |
| ⚙️ Top-right button      | Open settings (camera toggle, use-my-location toggle).                                                                         |
| **Päivitä nyt** button   | Force an immediate refresh.                                                                                                    |
| _Seuraava päivitys: N s_ | Countdown to the next automatic refresh (shown only when the server signals new data is due).                                  |
| Camera image             | Click to open a lightbox. Navigate with prev/next buttons, arrow keys, or swipe. Toggle fullscreen with the fullscreen button. |

---

## Architecture

For a detailed technical architecture including component diagrams, sequence diagrams, domain models, and runtime behavior, see [ARCHITECTURE.md](docs/ARCHITECTURE.md).

### Directory structure

```text
weatherview-django/
├── manage.py
├── requirements.txt
├── weatherview_project/        # Django project (settings, root URLs)
└── weather/
    ├── views.py                # JSON API endpoints
    ├── urls.py
    ├── services/               # Domain logic (parsing, formulas, HTTP clients)
    │   ├── definitions.py      # Constants, API URLs
    │   ├── weather_service.py  # Digitraffic + OpenWeatherMap HTTP client
    │   ├── station_info.py     # Station metadata model
    │   ├── weather_station.py  # Observation parsing + derived properties
    │   ├── physics.py          # FMI feels-like temperature formula
    │   ├── helpers.py          # Test-station filter
    │   └── ui_helpers.py       # Symbols, wind direction, name formatting
    ├── templates/weather/
    │   └── index.html
    ├── static/weather/
    │   ├── css/style.css
    │   ├── js/app.js           # Vanilla JS frontend (SPA logic, UI)
    │   ├── js/camera.js        # Weather camera module (carousel, lightbox)
    │   └── js/constants.js     # UI configuration constants
    └── tests.py                # Offline test suite (mocked HTTP)
scripts/
└── smoke_test.py               # Live smoke test (hits real APIs)
```

### Data sources

- **Digitraffic** road weather API (no key required)
  - `GET /api/weather/v1/stations` — station list
  - `GET /api/weather/v1/stations/{id}/data` — sensor observations
- **OpenWeatherMap** (free tier)
  - Current weather (by city + lat/lon fallback)
  - 5-day / 3-hour forecast

### HTTP endpoints (server-side)

| Method | Path                     | Purpose                                     |
| ------ | ------------------------ | ------------------------------------------- |
| GET    | `/`                      | Single-page app                             |
| GET    | `/api/stations/`         | Cached station list                         |
| GET    | `/api/station/<int:id>/` | Parsed observation + forecast for a station |
| GET    | `/api/settings/`         | Read session settings                       |
| POST   | `/api/settings/save/`    | Save session settings                       |
| GET    | `/api/nearest-station/`  | Nearest station to `?lat=…&lon=…`           |

### Stack

- **Backend** — Django 6, `requests`, `python-dateutil`
- **Frontend** — Plain HTML + CSS + vanilla JS (no build step, no framework)
- **Storage** — None. Signed-cookie sessions for user prefs, in-memory cache
  for the station list. `localStorage` for the client-side MRU list.

---

## Development

System check:

```bash
python manage.py check
```

The dev server reloads automatically on file changes.

### Documentation

Generate HTML documentation from source code comments:

```bash
doxygen Doxyfile
```

This generates HTML documentation in `docs/doxygen/html/`. Open `docs/doxygen/html/index.html` in your browser to view it.

**Requirements:** Doxygen must be installed. On Windows, install via [Doxygen](https://www.doxygen.nl/download.html) or via package manager. On macOS: `brew install doxygen`. On Linux or WSL: `apt-get install doxygen` (Debian/Ubuntu) or equivalent.

---

### Testing

Two test surfaces ship with the project:

**Offline Django tests** — 44 tests covering helpers, FMI physics, JSON parsing, forecast date filtering, upstream error handling (5xx / 4xx / network failures), per-station caching logic, and all HTTP endpoints (mocked):

```bash
python manage.py test weather
```

These run in well under a second and require no network access.

**Live smoke test** — hits Digitraffic and (optionally) OpenWeatherMap end-to-end:

```bash
python scripts/smoke_test.py                  # quick check (no forecast)
python scripts/smoke_test.py 23819            # specific station id
python scripts/smoke_test.py --api-key XXXX   # exercise OWM symbol + forecast
# or pass it via env var:
set OWM_API_KEY=XXXX && python scripts/smoke_test.py
```

---

## Credits

- Road weather data: **Fintraffic / Digitraffic** open data, licensed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
- Forecast data: **OpenWeatherMap**.
