# weatherview-django

A browser-based road weather viewer for Finnish roads. It combines live observations from [Digitraffic](https://www.digitraffic.fi/) road weather stations with short-range forecasts from [FMI open data](https://en.ilmatieteenlaitos.fi/open-data).

Pick any of 400+ Finnish road weather stations and view current observations, FMI feels-like temperature, wind, visibility, present weather, and forecast data directly in the browser, along with the latest pictures of the weather camera closest to the selected weather station.

<img src="docs/screenshot.png" alt="Screenshot of the Tiesaa web UI" width="80%">

## Features

- More than 400 Finnish road weather stations (Digitraffic open data)
- Air temperature with FMI feels-like calculation
- Wind speed (avg / max), direction with cardinal text
- Humidity, dew point, road surface temperature, visibility, temperature rate of change, and present weather
- Forecast carousel with intra-day and multi-day outlook
- Trend history chart with configurable history window
- Finnish/Swedish/English UI toggle
- Server-driven refresh scheduling (no blind polling)
- Session-based settings and client-side MRU station list
- Built-in API rate limiting (configurable)
- Redis-backed caching in production, LocMem fallback for local single-worker development

No database is required. User preferences are stored in signed-cookie sessions.

## Quick Start

### Requirements

- Python 3.12+ (Django 6 requires 3.12+; 3.13 tested)
- Internet access (Digitraffic + FMI open data)
- Redis (optional for local development)

### Install and run

```bash
git clone https://github.com/jjankkil/weatherview-django
cd weatherview-django

python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate      # Linux / macOS

# On Raspberry Pi OS Bookworm, the default `python3` is often 3.11, which is too old for Django 6.
# Use Python 3.12 or 3.13 instead, for example:
# python3.12 -m venv .venv
# or
# python3.13 -m venv .venv

pip install -r requirements.txt
cp .env.example .env
```

Set at least this value in `.env`:

```env
WVD_SECRET_KEY=<generate with: python -c "from django.utils.crypto import get_random_string; print(get_random_string(50))">
```

Start the development server:

```bash
# Windows PowerShell
.\startup.ps1

# Windows CMD
startup.bat

# Linux / macOS / WSL
./startup.sh
```

Open <http://127.0.0.1:8000/> in your browser.

## Usage

| Element                | What it does                                                                     |
| ---------------------- | -------------------------------------------------------------------------------- |
| Station dropdown       | Pick any station. Most-recently-used 10 are grouped at the top.                  |
| Search button          | Open a search modal and filter stations by name.                                 |
| Language button        | Toggle between Finnish, Swedish, and English.                                    |
| Settings button        | Open settings (camera toggle, use-my-location toggle).                           |
| Paivita nyt button     | Force an immediate refresh.                                                      |
| Seuraava paivitys: N s | Countdown to the next automatic refresh when the server signals new data is due. |
| Camera image           | Open a lightbox and navigate images with controls, keys, or swipe.               |

## Testing

```bash
# Offline Django tests
python manage.py test weather

# Playwright browser tests
pip install -r requirements-dev.txt
playwright install chromium
pytest tests/e2e/

# Live smoke test
python scripts/smoke_test.py
```

## Documentation

- [Architecture](docs/ARCHITECTURE.md) - component design, data flow, and runtime behavior
- [Development Guide](docs/DEVELOPMENT.md) - local setup, checks, test workflows, and Doxygen usage
- [Deployment Guide](docs/DEPLOYMENT.md) - Linux production deployment with Gunicorn, systemd, and Nginx
- [Configuration Reference](docs/CONFIGURATION.md) - environment variables, defaults, and production notes
- [Troubleshooting](docs/TROUBLESHOOTING.md) - common issues and practical fixes

## Credits

- Road weather data: **Fintraffic / Digitraffic** open data, licensed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)
- Forecast data: **Finnish Meteorological Institute (FMI)** open data, licensed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)
