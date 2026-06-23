"""Django views for the weather application API and frontend.

Provides HTTP endpoints for weather data display, station listing, and user settings management.
Views handle caching of station lists, weather service requests, and session-based preferences.

@author Jari Jankkila
@date 2026
@version 1.0
"""

import json
import math
import time
from datetime import timezone

from django.conf import settings
from django.core.cache import cache
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone as dj_tz
from django.views.decorators.http import require_http_methods

from .services.station_info import WeatherStationList
from .services.weather_service import WeatherService

_STATION_CACHE_KEY = 'weather_station_list'  #!< Cache key for the FMI station list
_STATION_DATA_KEY = 'station_data:{}:{}'  #!< Per-station cache key template; formatted with station_id and lang

def _parse_rate(rate: str) -> tuple[int, int]:
    """Parse a rate string like '15/m' into (count, window_seconds)."""
    count, unit = rate.split('/')
    window = {'s': 1, 'm': 60, 'h': 3600, 'd': 86400}.get(unit, 60)
    return int(count), window

def _is_rate_limited(ip: str) -> bool:
    """Return True if the given IP has exceeded WEATHER_RATE_LIMIT.

    Stores only a (request_count, window_start) tuple rather than a full
    list of timestamps, satisfying GDPR data-minimisation (Art. 5(1)(c)).
    Uses a fixed/tumbling window: the counter resets when the window expires.
    """
    limit, window = _parse_rate(settings.WEATHER_RATE_LIMIT)
    key = f'rl:{ip}'
    now = time.time()
    stored = cache.get(key)
    if stored is not None:
        req_count, window_start = stored
        if now - window_start < window:
            if req_count >= limit:
                return True
            cache.set(key, (req_count + 1, window_start), window)
            return False
    # First request in this window (or window has expired)
    cache.set(key, (1, now), window)
    return False


def _get_station_list() -> WeatherStationList:
    """Fetch the FMI weather station list with caching.

    Retrieves the complete list of available FMI weather stations, using Django's cache
    framework to avoid repeated API requests. On first access or cache expiration, fetches
    fresh data from the FMI API via WeatherService.

    @return WeatherStationList object containing all available stations (cached or fresh).
            Returns empty list if the API request fails.
    @details
    - Uses Django cache with key 'weather_station_list'
    - Cache is populated only if the FMI API request succeeds (no error)
    - Cache duration determined by Django's cache configuration
    - Gracefully handles cache misses by fetching fresh data
    """
    cached = cache.get(_STATION_CACHE_KEY)
    if cached is not None:
        return cached
    service = WeatherService()
    station_list = service.get_station_list()
    if not service.has_error:
        cache.set(_STATION_CACHE_KEY, station_list)
    return station_list

_SETTINGS_KEY = "wx_settings"  #!< Session key for user weather settings
_DEFAULT_SETTINGS = {  #!< Default settings applied to all sessions
    "current_station_id": None,  #!< Currently selected station (FMI station ID)
    "current_station_name": "",  #!< Display name of currently selected station
    "language": "fi",  #!< Display language ("fi" for Finnish, "sv" for Swedish, "en" for English)
    "show_camera": True,  #!< Whether to display weather camera images (default: enabled)
    "follow_location": False,  #!< Whether to always use geolocation to select the nearest station
}


def _get_settings(request) -> dict:
    """Retrieve user settings from session with defaults applied.

    Fetches user preferences from the Django session, merging with default values
    to ensure all expected keys are present. This allows graceful handling of
    missing or incomplete session data.

    @param request Django request object with session attached.
    @return Dictionary containing merged settings with all keys from _DEFAULT_SETTINGS.
            User-stored values override defaults; missing keys use defaults.
    @details
    - Returns complete dict with all _DEFAULT_SETTINGS keys
    - Session values take precedence over defaults
    - Safe to access any key; missing keys won't raise KeyError
    """
    settings = request.session.get(_SETTINGS_KEY, {})
    merged = {**_DEFAULT_SETTINGS, **settings}
    return merged


def _save_settings(request, settings: dict):
    """Persist user settings to Django session.

    Stores the provided settings dictionary in the session and marks the session
    as modified so Django persists it to storage.

    @param request Django request object with session attached.
    @param settings Dictionary of settings to save (typically from _get_settings).
    @details
    - Saves to request.session[_SETTINGS_KEY]
    - Must set session.modified = True for changes to persist
    - Should validate/sanitize settings in caller before saving
    """
    request.session[_SETTINGS_KEY] = settings
    request.session.modified = True


def index(request):
    """Render the main weather application interface.

    Serves the primary HTML template for the weather application frontend,
    which contains the interactive weather display and settings UI.

    @param request Django request object.
    @return HttpResponse with rendered "weather/index.html" template.
    @details
    - Template path: weather/index.html
    - Frontend loads station list and weather data via API endpoints
    - Uses session-stored user preferences for initial display
    """
    return render(request, "weather/index.html")


def api_stations(request):
    """Get the list of available weather stations (public only).

    HTTP GET endpoint that returns all publicly available FMI weather stations.
    Filtered to exclude test and special-purpose stations. Results are cached
    to minimize FMI API requests.

    @param request Django request object.
    @return JsonResponse with structure: {"stations": [station_dict, ...]}
            where each station_dict contains: id, name, formatted_name, lat, lon
    @details
    - HTTP method: GET
    - Cache key: 'weather_station_list'
    - Station list filtered by @ref ok_to_add_station (public stations only)
    - Each station includes geographic coordinates for mapping
    - Returns empty array if FMI API request fails
    """
    station_list = _get_station_list()
    return JsonResponse({"stations": station_list.get_name_list()})


def api_station_data(request, station_id: int):
    """Get current weather data for a specific station.

    HTTP GET endpoint that retrieves comprehensive weather data combining Digitraffic
    observations with FMI WFS forecast data (no API key required). Serves cached data
    when a fresh Digitraffic response is not yet expected, to minimise outbound requests.

    @param request Django request object with user session.
    @param station_id Digitraffic station ID from URL path parameter.
    @return JsonResponse with aggregated weather data:
            - On success (200): complete weather dict with temperature, wind, humidity,
              current_symbol, forecast, etc. (see @ref WeatherService.build_full_weather_response)
            - On error (502): {"error": "Station {id} not found"} if the station is unknown,
              or a clean human-readable message such as "Upstream service error (HTTP 503)"
              when Digitraffic returns a 5xx response. Safe to display directly in the UI.
    @details
    - HTTP method: GET
    - Display language from session settings (default: Finnish)
    - Returns HTTP 502 (Bad Gateway) if station not found or Digitraffic API fails
    - FMI WFS forecast is always fetched; failures degrade gracefully to empty forecast
    - Per-station response cache (key: 'station_data:{id}:{lang}'): on a cache hit the cached
      response is served immediately unless the request carries ?refresh=1 (sent by the
      frontend countdown timer when new data is due). On a miss or ?refresh=1, fresh data
      is fetched from Digitraffic and FMI and cached with a TTL derived from next_update_at
      (+30 s safety margin). seconds_until_next_update is recomputed from _next_update_at
      when serving from cache so the frontend always receives the accurate remaining wait time.
      The internal _next_update_at field is stripped before the response is sent to the client.
    """
    remote_addr = request.META.get('REMOTE_ADDR', '')
    trusted_proxies: frozenset = getattr(settings, 'TRUSTED_PROXY_IPS', frozenset())
    if trusted_proxies and remote_addr in trusted_proxies:
        ip = request.META.get('HTTP_X_FORWARDED_FOR', remote_addr).split(',')[0].strip()
    else:
        ip = remote_addr
    if _is_rate_limited(ip):
        return JsonResponse({"error": "Too many requests"}, status=429)

    user_settings = _get_settings(request)
    lang = user_settings.get("language", "fi")

    station_list = _get_station_list()

    cache_key = _STATION_DATA_KEY.format(station_id, lang)
    want_fresh = request.GET.get('refresh') == '1'
    cached = cache.get(cache_key)
    if cached is not None and not want_fresh:
        now = dj_tz.now()
        next_update_at = cached.get("_next_update_at")
        remaining = max(0, int((next_update_at - now).total_seconds())) if next_update_at else 60
        response = {k: v for k, v in cached.items() if k != "_next_update_at"}
        response["seconds_until_next_update"] = remaining
        return JsonResponse(response)

    service = WeatherService()
    data = service.build_full_weather_response(station_id, station_list, lang)
    if "error" in data:
        return JsonResponse(data, status=502)

    next_update_at = data.get("_next_update_at")
    ttl = 600
    if next_update_at is not None:
        ttl = max(10, int((next_update_at - dj_tz.now()).total_seconds()) + 30)
    cache.set(cache_key, data, ttl)

    response = {k: v for k, v in data.items() if k != "_next_update_at"}
    return JsonResponse(response)


@require_http_methods(["GET"])
def api_settings_get(request):
    """Retrieve the current user settings.

    HTTP GET endpoint that returns all user preferences from session, merged with
    defaults to ensure complete and valid settings object.

    @param request Django request object with user session.
    @return JsonResponse containing settings dict with keys:
            - current_station_id: FMI station ID (or None)
            - current_station_name: Display name of selected station
            - language: Display language code ("fi" or "en")
            - show_camera: Whether to display camera images (boolean)
            - follow_location: Whether to always use geolocation to select the nearest station (boolean)
    @details
    - HTTP method: GET only
    - Returns merged defaults + session values
    - Safe to access any key in response; all keys are guaranteed present
    - No authentication required; uses Django session
    """
    return JsonResponse(_get_settings(request))


@require_http_methods(["POST"])
def api_nearest_station(request):
    """Return the station closest to the given WGS84 coordinates.

    Accepts coordinates as a JSON body (POST) instead of query parameters so
    that precise geolocation data is kept out of server access logs.

    @param request Django request with JSON body:
                   - lat: WGS84 latitude in decimal degrees (required)
                   - lon: WGS84 longitude in decimal degrees (required)
    @return JsonResponse:
            - On success (200): station dict with keys id, name, formatted_name, lat, lon
            - On missing/invalid params (400): {"error": "..."}
            - On empty station list (503): {"error": "No stations available"}
    @details
    - HTTP method: POST only
    - Distance calculated using the haversine formula (great-circle distance)
    - Station list sourced from the same cache as @ref api_stations
    - Requires HTTPS (or localhost) in the browser; the Geolocation API that
      supplies the coordinates is only available in secure contexts
    """
    try:
        body = json.loads(request.body)
        lat = float(body['lat'])
        lon = float(body['lon'])
    except (json.JSONDecodeError, UnicodeDecodeError, KeyError, ValueError, TypeError):
        return JsonResponse({"error": "lat and lon are required numeric fields in the JSON body"}, status=400)

    station_list = _get_station_list()
    stations = station_list.get_name_list()
    if not stations:
        return JsonResponse({"error": "No stations available"}, status=503)

    def _dist(s):
        dlat = math.radians(s['lat'] - lat)
        dlon = math.radians(s['lon'] - lon)
        a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat)) * math.cos(math.radians(s['lat'])) * math.sin(dlon / 2) ** 2
        return math.atan2(math.sqrt(a), math.sqrt(1 - a))

    nearest = min(stations, key=_dist)
    return JsonResponse(nearest)


_VALID_LANGUAGES = {"fi", "sv", "en"}  #!< Accepted language codes for the language setting
_MAX_STATION_NAME_LEN = 200  #!< Maximum allowed length for current_station_name


def _validate_settings_body(body: dict) -> tuple[dict, str | None]:
    """Validate and sanitize settings from the request body.

    @param body Parsed JSON body from the settings save request.
    @return Tuple (cleaned_dict, error_message). cleaned_dict contains only the
            keys that were present, validated, and type-correct; error_message is
            None on success or a plain-text description of the first validation failure.
    """
    cleaned: dict = {}
    if "language" in body:
        val = body["language"]
        if val not in _VALID_LANGUAGES:
            return {}, f"Invalid language: {val!r}"
        cleaned["language"] = val
    if "show_camera" in body:
        val = body["show_camera"]
        if not isinstance(val, bool):
            return {}, "show_camera must be a boolean"
        cleaned["show_camera"] = val
    if "follow_location" in body:
        val = body["follow_location"]
        if not isinstance(val, bool):
            return {}, "follow_location must be a boolean"
        cleaned["follow_location"] = val
    if "current_station_id" in body:
        val = body["current_station_id"]
        if val is not None and (isinstance(val, bool) or not isinstance(val, int) or val <= 0):
            return {}, "current_station_id must be a positive integer or null"
        cleaned["current_station_id"] = val
    if "current_station_name" in body:
        val = body["current_station_name"]
        if not isinstance(val, str) or len(val) > _MAX_STATION_NAME_LEN:
            return {}, "current_station_name must be a string \u2264 200 characters"
        cleaned["current_station_name"] = val
    return cleaned, None


@require_http_methods(["POST"])
def api_settings_save(request):
    """Save or update user settings.

    HTTP POST endpoint that persists user preferences to the session. Only whitelisted
    settings keys are accepted and type-checked; other keys are silently ignored.

    @param request Django request object with JSON body containing settings to update.
    @return JsonResponse:
            - On success (200): {"ok": True}
            - On parse or validation error (400): {"error": "..."}
    @details
    - HTTP method: POST only
    - Request body: JSON object with setting keys and values
    - CSRF protection: requires X-CSRFToken request header (token served via
      <meta name="csrf-token"> in the page)
    - Allowed keys (whitelist): current_station_id, current_station_name,
      language, show_camera, follow_location
    - Partial updates: only provided keys are updated; others retain current values
    - Values are type-checked; invalid types or values return HTTP 400
    - All updates persisted to request.session for the current user
    @details Example request body:
    @code
    {
      "current_station_id": 101234,
      "current_station_name": "Helsinki, KPA",
      "language": "en",
      "show_camera": true
    }
    @endcode
    """
    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    if not isinstance(body, dict):
        return JsonResponse({"error": "Request body must be a JSON object"}, status=400)

    cleaned, error = _validate_settings_body(body)
    if error:
        return JsonResponse({"error": error}, status=400)

    settings = _get_settings(request)
    settings.update(cleaned)
    _save_settings(request, settings)
    return JsonResponse({"ok": True})
