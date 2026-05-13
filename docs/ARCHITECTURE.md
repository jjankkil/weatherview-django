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
        CONST["constants.js<br/>(UI config)"]
        LS[("localStorage<br/>MRU list")]
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
    UI <--> LS
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
- [weather/static/weather/js/app.js](../weather/static/weather/js/app.js) — SPA logic
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
        +wind_speed: float
        +wind_direction: int
        +visibility_str: str
        +feels_like: float
        +present_weather: tuple
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

| Method | Path                     | View                | Purpose                                           |
| ------ | ------------------------ | ------------------- | ------------------------------------------------- |
| GET    | `/`                      | `index`             | Serves the SPA shell (`index.html`)               |
| GET    | `/api/stations/`         | `api_stations`      | Returns the cached, filtered station catalogue    |
| GET    | `/api/station/<int:id>/` | `api_station_data`  | Parsed observations + optional OWM forecast       |
| GET    | `/api/settings/`         | `api_settings_get`  | Reads session settings                            |
| POST   | `/api/settings/save/`    | `api_settings_save` | Writes whitelisted session settings (CSRF-exempt) |

Session settings whitelist: `current_station_id`, `current_station_name`, `openweathermap_api_key`, `language`, `show_camera`. Anything else in the POST body is silently dropped ([views.py:228](../weather/views.py#L228)).

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
    Browser->>Django: GET /api/station/<id>/ (current or default)
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
    WS->>WS: WeatherStation.parse → derive temp/wind/feels-like/visibility
    alt api_key present
        WS->>OWM: GET /weather?q=city
        alt city lookup fails
            WS->>OWM: GET /weather?lat&lon (fallback)
        end
        OWM-->>WS: current weather (id → symbol)
        WS->>OWM: GET /forecast?lat&lon
        OWM-->>WS: 3-hour forecast list (first N items)
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

**Backend (Django):** `WeatherService._get` swallows `RequestException`, records `_status` and `_error`, and returns `{}`. Callers check `has_error`:

- Station list errors → cache is **not** populated; the next request will retry.
- Observation errors → view returns `{"error": ...}` with HTTP **502**.
- OWM errors → silently degraded: `current_symbol = ""` and `forecast = []` are returned alongside the Digitraffic data.

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
    D --> E{Has current<br/>station?}
    E -->|yes| F[GET /api/station/id]
    E -->|no| G[Wait for user]
    F --> H[Render card,<br/>show countdown]
    H --> I[Load weather camera<br/>images from Digitraffic]
    I --> J{Timer hits 0<br/>or user clicks 'Päivitä nyt'}
    J --> F
    G --> K[User picks station]
    K --> L[POST /api/settings/save/<br/>current_station_*]
    L --> M[Update MRU in localStorage]
    M --> F
    N([User toggles 🌐 / ⚙️]) --> O[POST /api/settings/save/]
    O --> F
```

---

## 9. Weather Camera Feature

The frontend displays weather camera images for each station. Camera URLs are fetched from the Digitraffic API alongside observation data.

The UI:

- Renders camera images in a carousel/gallery layout below the observation card
- Automatically scales images responsively on different screen sizes
- Refreshes camera images on the same cadence as observation data

Related code:

- [weather/static/weather/js/app.js](../weather/static/weather/js/app.js) — camera image loading and carousel logic
- [weather/static/weather/css/style.css](../weather/static/weather/css/style.css) — camera gallery styling
- [weather/views.py](../weather/views.py) — includes camera data in API response

---

## 10. Testing Surfaces

- **Unit / integration (offline)** — [weather/tests.py](../weather/tests.py). HTTP is mocked; covers helpers, FMI physics, JSON parsing, and all view endpoints. Run: `python manage.py test weather`.
- **Live smoke test** — [scripts/smoke_test.py](../scripts/smoke_test.py). Hits real Digitraffic (and OWM if a key is supplied).

---

## 11. Operational Notes

- **Sessions**: Django signed-cookie backend. No server-side session store needed; rotating `SECRET_KEY` invalidates all stored settings.
- **Cache backend**: Default is in-process `LocMemCache`. Swap to Redis/Memcached if running multiple workers and you want a single shared station list.
- **Timeouts**: All outbound HTTP uses a 10-second timeout ([weather_service.py:28](../weather/services/weather_service.py#L28)). There is no retry; a transient Digitraffic failure surfaces as a 502 to the client, which then schedules another attempt on its next refresh tick.
- **i18n**: Language is a string flag (`fi`/`en`) passed through to `WeatherStation.to_dict` and `wind_direction_as_text`. No Django `gettext` machinery is involved.
