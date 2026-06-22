"""Weather service module for fetching and processing weather data.

This module provides the WeatherService class which handles retrieving weather station
information from FMI (Finnish Meteorological Institute) and current weather/forecast data
from OpenWeatherMap API. It aggregates data from multiple sources to provide comprehensive
weather information for Finnish weather stations.

@author Jari Jankkila
@date 2026
@version 1.0
"""

import datetime

import requests
from django.conf import settings
from requests.exceptions import RequestException

from .definitions import Constants, Urls
from .station_info import WeatherStationList
from .ui_helpers import get_station_city, get_weather_symbol
from .weather_station import WeatherStation


class WeatherService:
    """Service class for weather data retrieval and processing.

    Handles HTTP requests to weather data providers (FMI and OpenWeatherMap) with
    error handling, and aggregates the responses into a unified weather information
    structure. Maintains error state across requests for diagnostic purposes.

    @details
    - Manages HTTP requests to FMI station list and weather station endpoints
    - Fetches current weather and forecast data from OpenWeatherMap
    - Provides error tracking and reporting for failed requests
    - Converts temperature units from Kelvin to Celsius
    - Maps weather condition IDs to UI weather symbols
    """
    def __init__(self):
        """Initialize a new WeatherService instance.

        Sets up initial error state with no errors and a successful HTTP status code.
        """
        self._error = ""
        self._status = 200

    @property
    def has_error(self) -> bool:
        """Check if an error occurred during the last request.

        @return True if the last request failed (non-200 status code or exception), False otherwise.
        """
        return self._status != 200 or bool(self._error)

    @property
    def error_message(self) -> str:
        """Get the error message from the last failed request.

        @return The exception message if a request failed, empty string otherwise.
        """
        return self._error

    def _get(self, url: str, key: str = "") -> dict | list:
        """Perform an HTTP GET request with error handling and JSON parsing.

        Internal method for making outbound HTTP requests. Catches RequestException
        and normalizes the error message by HTTP status range before storing it,
        so callers always receive a clean, user-displayable string rather than a
        raw exception with embedded URLs.

        @param url The URL endpoint to request from.
        @param key Optional JSON key to extract from response. If provided, returns the value
                   at response[key]. If not provided, returns the entire response.
        @return Dictionary or list from the JSON response, or empty dict on error.
        @details
        - Sets HTTP timeout to 10 seconds
        - On HTTP 5xx: sets _error to "Upstream service error (HTTP <status>)"
        - On HTTP 4xx: sets _error to "Upstream request failed (HTTP <status>)"
        - On network-level failure (no HTTP response): sets _error to str(exc), _status to 0
        - Filters response by key if provided (returns empty dict if key not found)
        """
        self._error = ""
        self._status = 200
        try:
            display_url = url.split("appid=")[0].rstrip("&?") + "..." if "appid=" in url else url
            print(f"[{datetime.datetime.now().strftime('%d/%b/%Y %H:%M:%S')}] GET {display_url}")
            r = requests.get(url, timeout=10)
            r.raise_for_status()
            data = r.json()
            return data.get(key, {}) if key else data
        except RequestException as exc:
            resp = getattr(exc, "response", None)
            self._status = getattr(resp, "status_code", 0) or 0
            if self._status >= 500:
                self._error = f"Upstream service error (HTTP {self._status})"
            elif self._status >= 400:
                self._error = f"Upstream request failed (HTTP {self._status})"
            else:
                self._error = str(exc)
            return {}

    def get_station_list(self) -> WeatherStationList:
        """Fetch and parse the list of available weather stations from FMI.

        Retrieves the GeoJSON feature collection from FMI's station list endpoint,
        parses the raw data into WeatherStationList objects, and sorts them alphabetically.

        @return WeatherStationList object containing all available weather stations.
                Returns an empty list if the request fails or if @ref has_error is True.
        """
        raw = self._get(Urls.STATION_LIST_URL, "features")
        station_list = WeatherStationList()
        if raw:
            station_list.parse(raw)
            station_list.sort_by_name()
        return station_list

    def get_station_data(self, station_id: int) -> WeatherStation:
        """Fetch weather data for a specific station from FMI.

        Retrieves current weather observations for the specified station ID and parses
        the response into a WeatherStation object.

        @param station_id The unique FMI station identifier.
        @return WeatherStation object containing current weather data for the station.
                Returns an empty station object if the request fails or if @ref has_error is True.
        """
        url = Urls.WEATHER_STATION_URL.format(station_id)
        raw = self._get(url)
        station = WeatherStation()
        if raw:
            station.parse(raw)
        return station

    def get_city_weather(self, city: str, coordinates) -> dict:
        """Fetch current weather data from OpenWeatherMap for a city or location.

        Attempts to fetch weather data by city name first. If that fails, falls back to
        fetching by geographic coordinates (latitude/longitude).

        @param city The city name to query (e.g., "Helsinki").
        @param coordinates Coordinate object with latitude and longitude attributes.
        @return Dictionary containing OpenWeatherMap current weather response.
                Returns empty dict if both requests fail or if @ref has_error is True.
        @details
        - Primary query uses city name for faster lookups
        - Fallback uses coordinates for ambiguous city names or failures
        - API key is read from Django settings (OPENWEATHER_API_KEY)
        """
        api_key = settings.OPENWEATHER_API_KEY
        url = Urls.OPENWEATHERMAP_CITY_URL.format(city, api_key)
        data = self._get(url)
        if self.has_error:
            url = Urls.OPENWEATHERMAP_LOCATION_URL.format(
                coordinates.latitude, coordinates.longitude, api_key
            )
            data = self._get(url)
        return data

    def get_forecast(self, coordinates) -> dict:
        """Fetch weather forecast data from OpenWeatherMap for given coordinates.

        Retrieves a multi-day weather forecast (5-day / 3-hour forecast by default)
        from OpenWeatherMap for the specified location.

        @param coordinates Coordinate object with latitude and longitude attributes.
        @return Dictionary containing OpenWeatherMap forecast response with a "list" key
                containing forecast entries. Returns empty dict on error or if @ref has_error is True.
        """
        api_key = settings.OPENWEATHER_API_KEY
        url = Urls.OPENWEATHERMAP_FORECAST_URL.format(
            coordinates.latitude, coordinates.longitude, api_key
        )
        return self._get(url)

    def build_full_weather_response(
        self,
        station_id: int,
        station_list: WeatherStationList,
        lang: str = "fi",
    ) -> dict:
        """Build a comprehensive weather response combining FMI and OpenWeatherMap data.

        Aggregates weather data from multiple sources into a single unified response object.
        Retrieves FMI station data (temperature, humidity, wind, etc.) and optionally
        augments it with OpenWeatherMap current weather symbols and multi-day forecast.

        @param station_id The FMI station identifier to query.
        @param station_list WeatherStationList containing station metadata (names, coordinates).
        @param lang Language code for localized output (default: "fi" for Finnish).
        @return Dictionary containing aggregated weather data with the following keys:
                - station_id: The requested station ID
                - station_name: Formatted station name from station_list
                - current_symbol: Weather condition symbol (empty if no OpenWeatherMap data)
                - forecast: Array of forecast objects. Objects for today carry
                  time (HH:MM), date (YYYY-MM-DD), temperature (rounded °C string), and symbol.
                  Objects for future days additionally carry daily (True) and have an empty
                  time string; they represent a single daily summary (midday slot preferred).
                - _next_update_at: datetime of the next expected Digitraffic observation
                  (internal; stripped by the view before sending the JSON response)
                - Additional keys from station_data.to_dict(lang)
                Returns {"error": <clean message>} if station not found or Digitraffic request
                fails. The error message is human-readable (e.g. "Upstream service error
                (HTTP 503)") and safe to display directly in the UI.
        @details
        - Validates station_id exists in station_list before querying FMI
        - Current weather symbol requires OPENWEATHER_API_KEY to be set in Django settings
        - Forecast is built in two phases from the OWM 5-day/3-hour response:
          1. Today's 3-hourly items: all entries where dt_txt date equals today, each
             represented individually with their HH:MM time slot.
          2. Future daily items: remaining dates (tomorrow onwards) are grouped by calendar
             date; the 12:00 entry is chosen as the representative (first available entry
             is used as fallback). Each group produces one item with daily=True.
        - Items with a malformed or missing dt_txt are skipped
        - Temperature is converted from Kelvin to Celsius (rounded to nearest integer)
        - Time is extracted as HH:MM from the ISO 8601 dt_txt field
        - Gracefully handles missing OpenWeatherMap data by returning FMI-only response
        """
        station_info = station_list.find_by_id(station_id)
        if station_info is None:
            return {"error": f"Station {station_id} not found"}

        station_data = self.get_station_data(station_id)
        if self.has_error:
            return {"error": self.error_message}

        result = station_data.to_dict(lang)
        result["station_id"] = station_id
        result["station_name"] = station_info.formatted_name
        result["current_symbol"] = ""
        result["forecast"] = []
        result["_next_update_at"] = station_data.next_update_at

        if settings.OPENWEATHER_API_KEY:
            city = get_station_city(station_info.formatted_name)
            city_data = self.get_city_weather(city, station_info.coordinates)
            if city_data and "weather" in city_data:
                weather_id = city_data["weather"][0]["id"]
                result["current_symbol"] = get_weather_symbol(weather_id)

            forecast_data = self.get_forecast(station_info.coordinates)
            forecasts = []
            today = datetime.date.today()
            future_days: dict[str, list] = {}
            for item in forecast_data.get("list", []):
                dt_txt = item.get("dt_txt", "")
                if len(dt_txt) < 10:
                    continue
                item_date = datetime.date.fromisoformat(dt_txt[:10])
                time_part = dt_txt[11:16] if len(dt_txt) >= 16 else ""
                temp_k = item.get("main", {}).get("temp", 0)
                temp_c = round(temp_k - 273.15)
                weather_id = item.get("weather", [{}])[0].get("id", 0)
                if item_date == today:
                    forecasts.append({
                        "time": time_part,
                        "date": dt_txt[:10],
                        "temperature": f"{temp_c} °C",
                        "symbol": get_weather_symbol(weather_id),
                    })
                elif item_date > today:
                    date_str = dt_txt[:10]
                    future_days.setdefault(date_str, []).append({
                        "time": time_part,
                        "temp_c": temp_c,
                        "weather_id": weather_id,
                    })
            for date_str in sorted(future_days):
                day_items = future_days[date_str]
                rep = next((x for x in day_items if x["time"] == "12:00"), day_items[0])
                forecasts.append({
                    "time": "",
                    "date": date_str,
                    "temperature": f"{rep['temp_c']} °C",
                    "symbol": get_weather_symbol(rep["weather_id"]),
                    "daily": True,
                })
            result["forecast"] = forecasts

        return result
