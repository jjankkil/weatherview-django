"""Live smoke test — hits Digitraffic and OpenWeatherMap.

Run from the repository root:

    python scripts/smoke_test.py [station_id] [--api-key KEY]

Adapted from the original `pyweatherview/scripts/smoke_test.py` to use the
Django port's `WeatherService`. Set an OpenWeatherMap API key via the
environment variable `OWM_API_KEY` (or `--api-key`) to exercise the
forecast/symbol path.
"""

import argparse
import os
import sys
from pathlib import Path

# Make the Django project importable when running from any CWD.
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Bootstrap Django so the services module can use django.utils.timezone etc.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "weatherview_project.settings")
import django  # noqa: E402

django.setup()

from weather.services.weather_service import WeatherService  # noqa: E402
from weather.services.ui_helpers import get_station_city  # noqa: E402


def run_checks(station_id: int | None, api_key: str) -> int:
    """@brief Execute live smoke tests against Digitraffic and OpenWeatherMap.

    Fetches the station list, queries observation data for *station_id* (or the
    first alphabetical station if `None`), and — when *api_key* is provided —
    also exercises the OpenWeatherMap city-weather and forecast paths.

    @param station_id  Digitraffic station id to query, or `None` to use the
                       first station returned by the API.
    @param api_key     OpenWeatherMap API key.  Pass an empty string to skip
                       the forecast/symbol checks.
    @return 0 on success, 1 on any error.
    """
    print("== weatherview-django smoke test ==")
    service = WeatherService()

    print("Fetching station list from Digitraffic…")
    station_list = service.get_station_list()
    if service.has_error:
        print(f"  ERROR: {service.error_message}")
        return 1

    names = station_list.get_name_list()
    print(f"  Stations after filtering: {len(names)}")
    if not names:
        print("  ERROR: empty station list")
        return 1

    first = names[0]
    print(f"  First (alphabetical): id={first['id']} name={first['formatted_name']}")

    target_id = station_id or first["id"]
    print(f"Fetching observation for station {target_id}…")
    station_data = service.get_station_data(target_id)
    if service.has_error:
        print(f"  ERROR: {service.error_message}")
        return 1

    info = station_list.find_by_id(target_id)
    if info is None:
        print(f"  ERROR: station {target_id} not in list")
        return 1

    print(f"  station_name = {info.formatted_name}")
    print(f"  temperature  = {station_data.air_temperature} °C")
    print(f"  humidity     = {station_data.air_humidity} %")
    print(f"  wind         = {station_data.wind_speed} m/s")
    print(f"  visibility   = {station_data.visibility_str}")

    if not api_key:
        print("(no OpenWeatherMap key — skipping symbol & forecast)")
        print("OK")
        return 0

    print("Fetching OpenWeatherMap city + forecast…")
    city = get_station_city(info.formatted_name)
    city_data = service.get_city_weather(city, info.coordinates, api_key)
    if isinstance(city_data, dict) and "weather" in city_data:
        print(f"  current weather id = {city_data['weather'][0]['id']}")
    else:
        print(f"  city_data error: {service.error_message or 'no weather key'}")

    forecast = service.get_forecast(info.coordinates, api_key)
    if isinstance(forecast, dict) and "list" in forecast:
        print(f"  forecast slots returned = {len(forecast['list'])}")
    else:
        print(f"  forecast error: {service.error_message or 'no list key'}")

    print("Fetching full bundled response (build_full_weather_response)…")
    bundle = service.build_full_weather_response(target_id, station_list, api_key, "fi")
    if "error" in bundle:
        print(f"  ERROR: {bundle['error']}")
        return 1
    print(f"  current_symbol = {bundle['current_symbol']!r}")
    print(f"  forecast count = {len(bundle['forecast'])}")
    print(f"  next update in = {bundle['seconds_until_next_update']} s")

    print("OK")
    return 0


def main() -> int:
    """@brief Parse CLI arguments and delegate to run_checks().

    @return Exit code forwarded from run_checks() (0 = success, 1 = failure).
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "station_id",
        nargs="?",
        type=int,
        default=None,
        help="Specific station id to query (default: first in list)",
    )
    parser.add_argument(
        "--api-key",
        default=os.environ.get("OWM_API_KEY", ""),
        help="OpenWeatherMap API key (or set $OWM_API_KEY)",
    )
    args = parser.parse_args()
    return run_checks(args.station_id, args.api_key)


if __name__ == "__main__":
    raise SystemExit(main())
