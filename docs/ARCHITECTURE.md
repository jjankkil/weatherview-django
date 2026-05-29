# weatherview-django — Technical Architecture

This document describes the structure and runtime behavior of `weatherview-django` for developers. It is intended to be read alongside the source — file paths and class names below are clickable references.

---

## 1. Overview

`weatherview-django` is a Django-served single-page application that visualizes live road weather observations from **Fintraffic / Digitraffic** and an optional short-range forecast from **OpenWeatherMap (OWM)**. The server is stateless apart from:

- a **signed-cookie session** holding per-user UI preferences and the OWM API key, and
- an **in-process cache** holding the parsed station list (TTL ≈ 5 minutes).

No database is used. All observation data is fetched on demand and parsed in memory.

---

## 2. Component / Package Structure

```mermaid
flowchart LR
    subgraph Browser
        UI["index.html + app.js<br/>(vanilla JS SPA)"]
        CAM["camera.js<br/>(carousel, lightbox)"]
        CONST["constants.js<br/>(UI config)"]
        LS[("localStorage<br/>MRU list")]
        GEO[("Browser<br/>Geolocation API")]
    end

    subgraph Django["Django project: weatherview_project"]
        URLS["urls.py<br/>(root + weather)"]
        VIEWS["weather/views.py<br/>JSON endpoints"]
        SESSION[("Signed-cookie<br/>session")]
        CACHE[("LocMem cache<br/>'weather_station_list'")]
    end

    subgraph Services["weather/services/"]
        WS["WeatherService<br/>HTTP client"]
        SL["WeatherStationList<br/>WeatherStationInfo"]
        WST["WeatherStation<br/>Sensor"]
        PHY["physics.py<br/>FMI feels-like"]
        UIH["ui_helpers.py<br/>symbols, wind, names"]
        DEF["definitions.py<br/>URLs, constants"]
    end

    subgraph External
        DT[("Digitraffic<br/>road weather API")]
        DTCam[("Digitraffic<br/>weathercam API")]
        OWM[("OpenWeatherMap<br/>current + forecast")]
    end

    UI <-->|fetch JSON| VIEWS
    UI <-->|fetch JSON| DTCam
    UI --- CAM
    CAM <-->|fetch JSON + images| DTCam
    UI <--> LS
    UI -->|getCurrentPosition| GEO
    URLS --> VIEWS
    VIEWS --> SESSION
    VIEWS --> CACHE
    VIEWS --> WS
    WS --> SL
    WS --> WST
    WST --> PHY
    WST --> UIH
    SL --> UIH
    WS --> DEF
    WS -->|HTTPS| DT
    WS -->|HTTPS| OWM
```

Key source locations:

- [weather/views.py](../weather/views.py) — JSON endpoints
- [weather/urls.py](../weather/urls.py) — URL routing
- [weather/services/weather_service.py](../weather/services/weather_service.py) — outbound HTTP
- [weather/services/station_info.py](../weather/services/station_info.py) — station catalogue model
- [weather/services/weather_station.py](../weather/services/weather_station.py) — observation model + derived properties
- [weather/services/physics.py](../weather/services/physics.py) — FMI feels-like formula
- [weather/static/weather/js/app.js](../weather/static/weather/js/app.js) — SPA logic (fetch, render, settings, search, geolocation, forecast)
- [weather/static/weather/js/camera.js](../weather/static/weather/js/camera.js) — weather camera module (carousel, lightbox, station lookup)
- [weather/static/weather/js/constants.js](../weather/static/weather/js/constants.js) — UI configuration constants
- [weather/static/weather/css/style.css](../weather/static/weather/css/style.css) — UI styling and weather camera layout

---

## 3. Domain Model (UML Class Diagram)

```mermaid
classDiagram
    class WeatherService {
        -_error: str
        -_status: int
        +has_error: bool
        +error_message: str
        +get_station_list() WeatherStationList
        +get_station_data(station_id) WeatherStation
        +get_city_weather(city, coords, api_key) dict
        +get_forecast(coords, api_key) dict
        +build_full_weather_response(id, list, key, lang) dict
        -_get(url, key) dict|list
    }

    class WeatherStationList {
        -_stations: list~WeatherStationInfo~
        +parse(json) bool
        +sort_by_name()
        +find_by_id(id) WeatherStationInfo
        +find_by_name(name) WeatherStationInfo
        +get_name_list() list~dict~
    }

    class WeatherStationInfo {
        +id: int
        +name: str
        +coordinates: Coordinates
        +formatted_name: str
        +parse(json) bool
        +to_dict() dict
    }

    class Coordinates {
        +latitude: float
        +longitude: float
        +altitude: float
    }

    class WeatherStation {
        -sensors: list~Sensor~
        -_latest_time: datetime
        -_previous_time: datetime
        +parse(json) bool
        +observation_time: datetime
        +air_temperature: float
        +air_humidity: float
        +dew_point: float
        +road_temperature: float
        +wind_speed: float
        +wind_direction: int
        +visibility_str: str
        +feels_like: float
        +present_weather: tuple
        +present_weather_localized(lang) tuple
        +seconds_until_next_update: int
        +to_dict(lang) dict
    }

    class Sensor {
        +id: int
        +station_id: int
        +name: str
        +short_name: str
        +value: float
        +unit: str
        +sensor_value_description: str
        +measured_time: datetime
        +parse(json) bool
    }

    WeatherService ..> WeatherStationList : creates
    WeatherService ..> WeatherStation : creates
    WeatherStationList "1" *-- "many" WeatherStationInfo
    WeatherStationInfo *-- Coordinates
    WeatherStation "1" *-- "many" Sensor
```

---

## 4. HTTP API (Server Surface)

| Method | Path                     | View                    | Purpose                                           |
| ------ | ------------------------ | ----------------------- | ------------------------------------------------- |
| GET    | `/`                      | `index`                 | Serves the SPA shell (`index.html`)               |
| GET    | `/api/stations/`         | `api_stations`          | Returns the cached, filtered station catalogue    |
| GET    | `/api/station/<int:id>/` | `api_station_data`      | Parsed observations + optional OWM forecast       |
| GET    | `/api/settings/`         | `api_settings_get`      | Reads session settings                            |
| POST   | `/api/settings/save/`    | `api_settings_save`     | Writes whitelisted session settings (CSRF-exempt) |
| GET    | `/api/nearest-station/`  | `api_nearest_station`   | Returns the station closest to `?lat=…&lon=…`     |

Session settings whitelist: `current_station_id`, `current_station_name`, `openweathermap_api_key`, `language`, `show_camera`, `follow_location`. Anything else in the POST body is silently dropped ([views.py](../weather/views.py)).

---

## 5. Runtime Behavior

### 5.1 Initial page load

```mermaid
sequenceDiagram
    autonumber
    actor User
    participant Browser as Browser (app.js)
    participant Django
    participant Cache as LocMem cache
    participant DT as Digitraffic

    User->>Browser: open /
    Browser->>Django: GET /
    Django-->>Browser: index.html + static
    Browser->>Django: GET /api/settings/
    Django-->>Browser: {language, api_key, current_station_id, ...}
    Browser->>Django: GET /api/stations/
    Django->>Cache: get('weather_station_list')
    alt cache miss
        Django->>DT: GET /api/weather/v1/stations
        DT-->>Django: GeoJSON FeatureCollection
        Django->>Django: WeatherStationList.parse + sort
        Django->>Cache: set(list, ttl=5min)
    end
    Django-->>Browser: [{id, name, formatted_name, lat, lon}, ...]
    Browser->>Browser: render dropdown, restore MRU from localStorage
    alt follow_location enabled or no saved station
        Browser->>Browser: navigator.geolocation.getCurrentPosition()
        Browser->>Django: GET /api/nearest-station/?lat=…&lon=…
        Django-->>Browser: nearest station dict
    end
    Browser->>Django: GET /api/station/<id>/
```

### 5.2 Station observation request (backend)

```mermaid
sequenceDiagram
    autonumber
    participant Browser
    participant View as api_station_data
    participant WS as WeatherService
    participant DT as Digitraffic<br/>(weather data)
    participant OWM as OpenWeatherMap

    Browser->>View: GET /api/station/23819/
    View->>View: _get_settings(request)
    View->>View: _get_station_list() (cache)
    View->>WS: build_full_weather_response(id, list, api_key, lang)
    WS->>DT: GET /stations/{id}/data
    DT-->>WS: {dataUpdatedTime, sensorValues:[...]}
    WS->>WS: WeatherStation.parse → derive temp/wind/feels-like/road-temp/visibility/dew-point/humidity
    alt api_key present
        WS->>OWM: GET /weather?q=city
        alt city lookup fails
            WS->>OWM: GET /weather?lat&lon (fallback)
        end
        OWM-->>WS: current weather (id → symbol)
        WS->>OWM: GET /forecast?lat&lon
        OWM-->>WS: 3-hour forecast list (all periods, filtered to 3-day window)
    end
    WS-->>View: dict (station_name, temperature, ..., forecast[])
    View-->>Browser: 200 JSON   (or 502 on upstream error)
    Browser->>Browser: paint card, start countdown
```

### 5.3 Weather camera image loading (frontend)

The weather camera feature is a separate, parallel fetch performed by the frontend. It does not go through the Django backend.

**Design Rationale:**

- **Performance:** Direct browser-to-CDN connection reduces latency for image delivery; Digitraffic's image CDN (`weathercam.digitraffic.fi`) is optimized for media serving.
- **Separation of Concerns:** Django handles structured data (observations, metadata, settings); the browser handles media discovery and presentation (finding closest camera, rendering carousel).
- **Resilience:** Camera failures don't impact weather observations. If Digitraffic's weathercam API is down, the observation card still renders correctly.
- **Cost & Bandwidth:** Images bypass the Django server entirely—no bandwidth charge, disk I/O, or process memory cost. Leverages Digitraffic's infrastructure already in use.
- **API Simplicity:** The `/api/station/<id>/` response stays small and fast (JSON only, no binary data). No need for server-side image caching or proxying.

The tradeoff is that frontend code (`app.js`) needs to know the Digitraffic weathercam API details (endpoints, GeoJSON structure), which is why these URLs are centralized in `constants.js`.

```mermaid
sequenceDiagram
    autonumber
    participant Browser as app.js
    participant DTCam as Digitraffic<br/>weathercam API
    participant DTImg as weathercam.digitraffic.fi<br/>(image host)

    Browser->>DTCam: GET /api/weathercam/v1/stations (cached)
    alt cache miss or refresh
        DTCam-->>Browser: GeoJSON FeatureCollection with camera locations
        Browser->>Browser: cache response in memory
    end
    Browser->>Browser: find closest camera to current station by haversine distance
    Browser->>DTCam: GET /api/weathercam/v1/stations/{cameraId}
    DTCam-->>Browser: {presets:[{id, presentationName, direction, ...}, ...]}
    Browser->>DTImg: GET {CAMERA_IMAGE_BASE}/{presetId}.jpg (for each preset)
    DTImg-->>Browser: JPEG image data
    Browser->>Browser: populate carousel with image slides
```

### 5.4 Adaptive refresh cadence

Each station has its own observation cadence. `WeatherStation` tracks two `dataUpdatedTime` values:

```mermaid
stateDiagram-v2
    [*] --> FirstFetch
    FirstFetch --> Bootstrapped: parse() sets _latest = _previous = obs_time
    Bootstrapped --> Stable: next parse() with obs_time != _previous<br/>shifts (_previous, _latest)
    Stable --> Stable: interval = |_latest - _previous|
    note right of Stable
      seconds_until_next_update =
        clamp( interval - (now - _latest) + delay, 0..600 )
      Falls back to DEFAULT_POLLING_INTERVAL_S
      while still bootstrapping.
    end note
```

This is the value the frontend uses to schedule the next `/api/station/<id>/` call — it can't refresh faster than the station actually updates ([weather_station.py:145-156](../weather/services/weather_station.py#L145-L156)).

### 5.5 Error handling

**Backend (Django):** `WeatherService._get` catches `RequestException`, records `_status` and `_error`, and returns `{}`. The error message is normalized by HTTP status range before being stored:

- **5xx from Digitraffic** → `_error = "Upstream service error (HTTP <status>)"` — clean, no raw URL noise.
- **4xx from Digitraffic** → `_error = "Upstream request failed (HTTP <status>)"`.
- **Network-level failure** (no HTTP response, e.g. connection refused) → `_error = str(exc)` (raw exception message); `_status = 0`.

Callers check `has_error`:

- Station list errors → cache is **not** populated; the next request will retry.
- Observation errors → view returns `{"error": <clean message>}` with HTTP **502**.
- OWM errors → silently degraded: `current_symbol = ""` and `forecast = []` are returned alongside the Digitraffic data.

**Frontend (JS):** `fetchWeather` handles all non-2xx responses before attempting `r.json()`:

- `r.ok` is false → try to parse JSON; show `data.error` if present (the clean backend message).
- If JSON parsing fails (e.g. Django debug HTML 500 page) → fall back to the localized `serviceError` label, including the HTTP status code.
- `fetch()` throws (network-level failure, e.g. no connectivity) → show the localized `networkError` label.
- In all error cases `scheduleRefresh(60)` fires so the UI retries automatically after 60 seconds.

**Frontend (camera):** Weather camera image loading failures are gracefully handled:

- Weathercam API fetch fails → camera panel is hidden; observation card remains visible.
- Individual preset images fail to load → spinner is left visible; user can retry or dismiss.
- No impact on observation data or other UI elements.

---

## 6. State & Persistence

```mermaid
flowchart TB
    subgraph Server-side
        S1[("Signed-cookie session<br/>wx_settings")]
        S2[("django.core.cache (locmem)<br/>weather_station_list, TTL≈5min")]
    end
    subgraph Client-side
        C1[("localStorage<br/>MRU station list, max 5")]
        C2[("In-memory JS state<br/>current station, timer")]
        C3[("In-memory JS cache<br/>weathercam stations")]
    end

    S1 -.holds.-> K1["openweathermap_api_key"]
    S1 -.holds.-> K2["language (fi|en)"]
    S1 -.holds.-> K3["current_station_id / _name"]
    S1 -.holds.-> K6["show_camera (boolean)"]
    S1 -.holds.-> K8["follow_location (boolean)"]
    S2 -.holds.-> K4["parsed WeatherStationList"]
    C1 -.holds.-> K5["recently selected stations"]
    C3 -.holds.-> K7["GeoJSON camera stations<br/>from Digitraffic weathercam API"]
```

- The OWM API key never touches a database or log file; it lives only in the signed-cookie session.
- The station list is cached per-process. With multiple worker processes, each warms its own copy on first hit.
- Weathercam station data is cached in-memory on the client; it persists for the page lifetime and is refreshed on browser reload.

---

## 7. Internal Block Diagram (SysML IBD)

A SysML-flavored Internal Block Diagram of a single request showing data flow across ports:

```mermaid
flowchart LR
    subgraph req["«block» api_station_data"]
        direction LR
        in1[/"in: HttpRequest"/]
        out1[/"out: JsonResponse"/]
        in1 -->|station_id| L1[_get_settings]
        in1 --> L2[_get_station_list]
        L1 -->|api_key, lang| L3[build_full_weather_response]
        L2 -->|WeatherStationList| L3
        L3 --> out1
    end

    subgraph svc["«block» WeatherService"]
        direction TB
        P1[[get_station_data]]
        P2[[get_city_weather]]
        P3[[get_forecast]]
    end

    L3 --> P1
    L3 -.optional.-> P2
    L3 -.optional.-> P3

    P1 -->|HTTPS| ED[("Digitraffic")]
    P2 -->|HTTPS| EO[("OpenWeatherMap /weather")]
    P3 -->|HTTPS| EF[("OpenWeatherMap /forecast")]
```

---

## 8. Frontend Lifecycle (Activity Diagram)

```mermaid
flowchart TD
    A([Page load]) --> B[GET /api/settings/]
    B --> C[GET /api/stations/]
    C --> D[Populate dropdown<br/>+ MRU group from localStorage]
    D --> E{follow_location<br/>enabled?}
    E -->|yes| GEO[selectNearestByGeolocation]
    E -->|no| E2{Has saved<br/>station?}
    E2 -->|yes| F[GET /api/station/id]
    E2 -->|no| GEO
    GEO -->|position obtained| NS[GET /api/nearest-station/]
    GEO -->|denied / unavailable| F1["Use stations[0]"]
    NS --> F
    F1 --> F
    F --> H[Render card, forecast carousel,<br/>show countdown]
    H --> I[Load weather camera<br/>images from Digitraffic]
    H -.-> G[Wait for user]
    I --> J{Timer hits 0<br/>or user clicks 'Päivitä nyt'}
    J --> F
    G --> K[User picks station]
    K --> L[POST /api/settings/save/<br/>current_station_*]
    L --> M[Update MRU in localStorage]
    M --> F
    N([User toggles lang / settings]) --> O[POST /api/settings/save/]
    O --> F
    P([User clicks search]) --> Q[Open station search modal]
    Q --> R{User selects result}
    R -->|station chosen| L
    R -->|dismissed| G
    S([User clicks camera image]) --> T[Open lightbox]
    T --> U[Navigate prev/next or toggle fullscreen]
    U --> V[Close lightbox]
    V --> H
```

### 8.1 Forecast carousel

The forecast section renders a paginated carousel of 3-hour OWM forecast items:

- **Data**: The backend returns all OWM 3-hour periods with `dt_txt` falling within the next 3 calendar days (today up to, but not including, today + 3). Each item carries `time` (HH:MM), `date` (YYYY-MM-DD), `temperature` (rounded °C string), and `symbol`.
- **Page size**: 3 items per page (`FORECAST_PAGE_SIZE = 3` in `app.js`).
- **Navigation**: `‹` / `›` buttons call `forecastGoTo(i)`, which slices `forecastCarousel.items` and re-renders the visible page. Buttons are disabled at the first and last page respectively.
- **Day label**: Each item's time label is prefixed with a localized weekday abbreviation (e.g. "Ma 15:00") derived from the `date` field, so users can see which day a period belongs to.
- **Reset on refresh**: `forecastCarousel.index` resets to 0 whenever new station data arrives.

Related code: [weather/static/weather/js/app.js](../weather/static/weather/js/app.js) (`forecastGoTo`, `forecastCarousel`, `FORECAST_PAGE_SIZE`) · [weather/static/weather/css/style.css](../weather/static/weather/css/style.css) (`.forecast-carousel`, `.forecast-nav-btn`) · [weather/services/weather_service.py](../weather/services/weather_service.py) (`build_full_weather_response`).

---

## 9. Weather Camera Feature

The frontend displays weather camera images for each station. Camera logic lives in its own ES module (`camera.js`) and is imported by `app.js`. The module is initialised once on page load via `initCamera(state, dom, labels, setVisible)`, which injects the shared state and DOM references it needs.

### 9.1 Module structure

| Export | Description |
|---|---|
| `initCamera(state, dom, labels, setVisible)` | One-time setup; stores injected deps |
| `showCameraForStation(lat, lon)` | Finds the nearest camera, fetches its presets, renders the carousel |
| `carousel` | `{ index, slides }` — current carousel state |
| `lightbox` | `{ index }` — current lightbox state |
| `carouselGoTo(i)` | Navigate the carousel to slide `i` |
| `lightboxGoTo(i)` | Navigate the lightbox to slide `i` |
| `openLightbox(i)` | Open the lightbox at slide `i` |
| `closeLightbox()` | Close the lightbox |

### 9.2 Camera carousel

- Renders camera images in a carousel/gallery layout below the observation card
- Automatically scales images responsively on different screen sizes
- Refreshes camera images on the same cadence as observation data (triggered by `app.js` after each weather fetch)

### 9.3 Lightbox

Clicking any camera image opens a fullscreen-capable lightbox:

- **Navigation** — prev/next buttons, left/right arrow keys, or touch swipe (threshold: 40 px)
- **Direction label** — each slide shows the camera's `presentationName` (e.g. "Pohjoinen") as an overlay
- **Fullscreen** — the ⛶ button calls `element.requestFullscreen()`; the `fullscreenchange` event updates layout variables (`--fs-w`, `--fs-h`) so slides fill the screen correctly
- **Dismiss** — Escape key, close button, or clicking outside the slide

### 9.4 Station search modal

A 🔍 search button next to the station dropdown opens a modal with a text input. Typing filters the full station list client-side (case-insensitive substring match on formatted name). Selecting a result closes the modal and triggers the same station-selection flow as the dropdown (POST settings, update MRU, fetch observations). This logic lives in `app.js`.

Related code:

- [weather/static/weather/js/camera.js](../weather/static/weather/js/camera.js) — camera module (station lookup, carousel, lightbox)
- [weather/static/weather/js/app.js](../weather/static/weather/js/app.js) — imports camera module; handles station search modal
- [weather/static/weather/css/style.css](../weather/static/weather/css/style.css) — camera gallery, lightbox, and modal styling
- [weather/views.py](../weather/views.py) — includes camera data in API response

---

## 10. Geolocation Feature

### 10.1 Overview

On page load, `app.js` checks the `follow_location` session setting. If it is `true`, or if no station has been saved yet, `selectNearestByGeolocation()` is called. This function:

1. Calls `navigator.geolocation.getCurrentPosition()` (8-second timeout).
2. On success, sends `GET /api/nearest-station/?lat=…&lon=…` to the Django backend.
3. The backend computes haversine distance from the supplied coordinates to every station in the cached list and returns the closest one.
4. The frontend selects that station in the dropdown and fetches its weather data.

If geolocation fails for any reason (permission denied, timeout, API error, or non-secure context), the function falls back to the first alphabetically sorted station and logs a timestamped `console.warn`.

### 10.2 Sequence diagram

```mermaid
sequenceDiagram
    autonumber
    actor User
    participant Browser as app.js
    participant Geo as Browser Geolocation API
    participant Django

    Browser->>Geo: getCurrentPosition() (timeout 8s)
    alt permission granted
        Geo-->>Browser: {latitude, longitude}
        Browser->>Django: GET /api/nearest-station/?lat=…&lon=…
        Django->>Django: haversine distance over cached station list
        Django-->>Browser: {id, name, formatted_name, lat, lon}
        Browser->>Browser: select station, fetchWeather(id)
    else denied / unavailable / non-secure context
        Geo-->>Browser: PositionError
        Browser->>Browser: console.warn + fallback to stations[0]
    end
```

### 10.3 Settings integration

The **"Use my location"** checkbox in the ⚙️ Settings modal maps to the `follow_location` boolean in the session. When enabled, geolocation runs on every page load regardless of whether a station was previously saved. When disabled, geolocation still runs once on first visit (no saved station), and subsequent visits restore the manually selected station.

### 10.4 Secure context requirement

The browser Geolocation API is only available in **secure contexts** (HTTPS or `localhost`). On a plain HTTP connection the API object is unavailable and the fallback fires immediately. For local development, access the server via `http://localhost:8000` to satisfy the secure-context requirement without needing a certificate.

---

## 11. Testing Surfaces

- **Unit / integration (offline)** — [weather/tests.py](../weather/tests.py). HTTP is mocked; covers helpers, FMI physics, JSON parsing, forecast date filtering, and all view endpoints. Run: `python manage.py test weather`.
- **Live smoke test** — [scripts/smoke_test.py](../scripts/smoke_test.py). Hits real Digitraffic (and OWM if a key is supplied).

---

## 12. Operational Notes

- **Sessions**: Django signed-cookie backend. No server-side session store needed; rotating `SECRET_KEY` invalidates all stored settings.
- **Cache backend**: Default is in-process `LocMemCache`. Swap to Redis/Memcached if running multiple workers and you want a single shared station list.
- **Timeouts**: All outbound HTTP uses a 10-second timeout ([weather_service.py:28](../weather/services/weather_service.py#L28)). There is no server-side retry; a transient Digitraffic failure (including 5xx responses) surfaces as a HTTP 502 to the client with a clean `{"error": "Upstream service error (HTTP <status>)"}` body. The frontend displays this in the error banner and schedules an automatic retry after 60 seconds.
- **i18n**: Language is a string flag (`fi`/`en`) passed through to `WeatherStation.to_dict`, which calls `wind_direction_as_text` and `present_weather_localized` for server-side translation. Present weather labels ("Säätila:" / "Weather:", "Sade:" / "Precipitation:") and Digitraffic SADE sensor condition strings (e.g. "Pouta" → "Dry") are translated via a lookup table in `WeatherStation`. No Django `gettext` machinery is involved.
