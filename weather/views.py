import json
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import render
from django.core.cache import cache

from .services.weather_service import WeatherService
from .services.station_info import WeatherStationList

_STATION_CACHE_KEY = 'weather_station_list'


def _get_station_list() -> WeatherStationList:
    cached = cache.get(_STATION_CACHE_KEY)
    if cached is not None:
        return cached
    service = WeatherService()
    station_list = service.get_station_list()
    if not service.has_error:
        cache.set(_STATION_CACHE_KEY, station_list)
    return station_list

_SETTINGS_KEY = "wx_settings"
_DEFAULT_SETTINGS = {
    "current_station_id": None,
    "current_station_name": "",
    "openweathermap_api_key": "",
    "language": "fi",
}


def _get_settings(request) -> dict:
    settings = request.session.get(_SETTINGS_KEY, {})
    merged = {**_DEFAULT_SETTINGS, **settings}
    return merged


def _save_settings(request, settings: dict):
    request.session[_SETTINGS_KEY] = settings
    request.session.modified = True


def index(request):
    return render(request, "weather/index.html")


def api_stations(request):
    station_list = _get_station_list()
    return JsonResponse({"stations": station_list.get_name_list()})


def api_station_data(request, station_id: int):
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
    return JsonResponse(_get_settings(request))


@csrf_exempt
@require_http_methods(["POST"])
def api_settings_save(request):
    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    settings = _get_settings(request)
    allowed = {"current_station_id", "current_station_name", "openweathermap_api_key", "language"}
    for key in allowed:
        if key in body:
            settings[key] = body[key]
    _save_settings(request, settings)
    return JsonResponse({"ok": True})
