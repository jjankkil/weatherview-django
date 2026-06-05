"""Django views for the weather application API and frontend.

Provides HTTP endpoints for weather data display, station listing, and user settings management.
Views handle caching of station lists, weather service requests, and session-based preferences.

@author Jari Jankkila
@date 2026
@version 1.0
"""

import json
import math
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import render
from django.core.cache import cache

from .services.weather_service import WeatherService
from .services.station_info import WeatherStationList

_STATION_CACHE_KEY = 'weather_station_list'  #!< Cache key for the FMI station list


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
    "openweathermap_api_key": "",  #!< OpenWeatherMap API key for additional weather data
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

    HTTP GET endpoint that retrieves comprehensive weather data combining FMI observations
    with optional OpenWeatherMap current conditions and forecast. Uses user's stored
    OpenWeatherMap API key and language preference.

    @param request Django request object with user session.
    @param station_id FMI station ID from URL path parameter.
    @return JsonResponse with aggregated weather data:
            - On success (200): complete weather dict with temperature, wind, humidity,
              current_symbol, forecast, etc. (see @ref WeatherService.build_full_weather_response)
            - On error (502): {"error": "Station {id} not found"} if the station is unknown,
              or a clean human-readable message such as "Upstream service error (HTTP 503)"
              when Digitraffic returns a 5xx response. Safe to display directly in the UI.
    @details
    - HTTP method: GET
    - User's OpenWeatherMap API key from session settings (optional)
    - Display language from session settings (default: Finnish)
    - Returns HTTP 502 (Bad Gateway) if station not found or FMI API fails
    - If no OpenWeatherMap API key: returns FMI data only (no weather symbols/forecast)
    - Forecast covers all OWM 3-hour periods up to (but not including) today + 3 days
    """
    settings = _get_settings(request)
    api_key = settings.get("openweathermap_api_key", "")
    lang = settings.get("language", "fi")

    station_list = _get_station_list()

    service = WeatherService()
    data = service.build_full_weather_response(station_id, station_list, api_key, lang)
    if "error" in data:
        return JsonResponse(data, status=502)
    return JsonResponse(data)


@require_http_methods(["GET"])
def api_settings_get(request):
    """Retrieve the current user settings.

    HTTP GET endpoint that returns all user preferences from session, merged with
    defaults to ensure complete and valid settings object.

    @param request Django request object with user session.
    @return JsonResponse containing settings dict with keys:
            - current_station_id: FMI station ID (or None)
            - current_station_name: Display name of selected station
            - openweathermap_api_key: API key for OpenWeatherMap (empty if not set)
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


@require_http_methods(["GET"])
def api_nearest_station(request):
    """Return the station closest to the given WGS84 coordinates.

    Used by the frontend geolocation feature to select the nearest station
    automatically when the user enables "Use my location" in settings or on
    first visit with no saved station.

    @param request Django request with query params:
                   - lat: WGS84 latitude in decimal degrees (required)
                   - lon: WGS84 longitude in decimal degrees (required)
    @return JsonResponse:
            - On success (200): station dict with keys id, name, formatted_name, lat, lon
            - On missing/invalid params (400): {"error": "..."}
            - On empty station list (503): {"error": "No stations available"}
    @details
    - HTTP method: GET only
    - Distance calculated using the haversine formula (great-circle distance)
    - Station list sourced from the same cache as @ref api_stations
    - Requires HTTPS (or localhost) in the browser; the Geolocation API that
      supplies the coordinates is only available in secure contexts
    """
    try:
        lat = float(request.GET['lat'])
        lon = float(request.GET['lon'])
    except (KeyError, ValueError):
        return JsonResponse({"error": "lat and lon query parameters are required"}, status=400)

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


@csrf_exempt
@require_http_methods(["POST"])
def api_settings_save(request):
    """Save or update user settings.

    HTTP POST endpoint that persists user preferences to the session. Only whitelisted
    settings keys are accepted; other keys in the request are silently ignored.
    CSRF protection is disabled for this endpoint to allow frontend SPA requests.

    @param request Django request object with JSON body containing settings to update.
    @return JsonResponse:
            - On success (200): {"ok": True}
            - On JSON parse error (400): {"error": "Invalid JSON"}
    @details
    - HTTP method: POST only
    - Request body: JSON object with setting keys and values
    - CSRF exempt: decorated with @csrf_exempt for SPA/AJAX requests
    - Allowed keys (whitelist): current_station_id, current_station_name,
      openweathermap_api_key, language, show_camera, follow_location
    - Partial updates: only provided keys are updated; others retain current values
    - Invalid JSON returns HTTP 400 Bad Request
    - All updates persisted to request.session for the current user
    @details Example request body:
    @code
    {
      "current_station_id": 101234,
      "current_station_name": "Helsinki, KPA",
      "openweathermap_api_key": "your_api_key_here",
      "language": "en",
      "show_camera": true
    }
    @endcode
    """
    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    settings = _get_settings(request)
    allowed = {"current_station_id", "current_station_name", "openweathermap_api_key", "language", "show_camera", "follow_location"}
    for key in allowed:
        if key in body:
            settings[key] = body[key]
    _save_settings(request, settings)
    return JsonResponse({"ok": True})
