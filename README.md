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
- 🌦️ Optional 3-period 3-hour forecast + current weather symbol (requires defining an OpenWeatherMap API key)
- FI/EN Finnish/English UI toggle
- 🔄 Smart auto-refresh based on each station's observation cadence
- ⭐ 5-item MRU station list, persisted in browser `localStorage`
- ⏳ Wait cursor + dimmed card while loading
- 📍 Automatic nearest-station selection using the browser Geolocation API (on first visit or when "Use my location" is enabled in Settings)
- 💾 Session-based settings (API key, current station, language, camera visibility, follow-location)
- 🚀 In-memory station-list cache (5 min) — no repeated 447-row downloads

No database required. Settings live in signed-cookie sessions; weather data is fetched live on each request.

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
python manage.py runserver
```

Then open <http://127.0.0.1:8000/> in your browser.

### Optional: OpenWeatherMap API key

The weather symbol and forecast are only shown when an OpenWeatherMap API key is configured.

1. Register a free account at <https://openweathermap.org/>.
2. Copy your API key.
3. Open the app, click **⚙️** in the top-right, paste the key, click
   **Tallenna / Save**.

The key is stored in the browser session (signed cookie). It is never persisted server-side.

---

## Usage

| Element                  | What it does                                                                                                    |
| ------------------------ | --------------------------------------------------------------------------------------------------------------- |
| Station dropdown         | Pick any station. Most-recently-used 5 are grouped at the top.                                                  |
| 🔍 Search button         | Open a search modal — type any part of a station name to filter and select it.                                  |
| 🌐 Top-right button      | Toggle between Finnish and English labels.                                                                      |
| ⚙️ Top-right button      | Open settings (OpenWeatherMap API key, camera toggle, use-my-location toggle).                                  |
| **Päivitä nyt** button   | Force an immediate refresh.                                                                                     |
| _Seuraava päivitys: N s_ | Countdown to the next automatic refresh.                                                                        |
| Camera image             | Click to open a lightbox. Navigate with ←/→ buttons, arrow keys, or swipe. Toggle fullscreen with the ⛶ button. |

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
    │   ├── js/app.js           # Vanilla JS frontend
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

**Offline Django tests** — 20 tests covering helpers, FMI physics, JSON parsing, and all HTTP endpoints (mocked):

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
