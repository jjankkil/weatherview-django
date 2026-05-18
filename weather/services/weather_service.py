"""Weather service module for fetching and processing weather data.

This module provides the WeatherService class which handles retrieving weather station
information from FMI (Finnish Meteorological Institute) and current weather/forecast data
from OpenWeatherMap API. It aggregates data from multiple sources to provide comprehensive
weather information for Finnish weather stations.

@author Jari Jankkila
@date 2026
@version 1.0
"""

import requests
from requests.exceptions import RequestException

from .definitions import Urls
from .station_info import WeatherStationList
from .weather_station import WeatherStation
from .ui_helpers import get_weather_symbol, get_station_city
from .definitions import Constants


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

        Internal method for making authenticated HTTP requests. Handles RequestException
        and extracts JSON data with optional key filtering.

        @param url The URL endpoint to request from.
        @param key Optional JSON key to extract from response. If provided, returns the value
                   at response[key]. If not provided, returns the entire response.
        @return Dictionary or list from the JSON response, or empty dict on error.
        @details
        - Sets HTTP timeout to 10 seconds
        - Captures HTTP status code and exception message on failure
        - Filters response by key if provided (returns empty dict if key not found)
        """
        self._error = ""
        self._status = 200
        try:
            r = requests.get(url, timeout=10)
            r.raise_for_status()
            data = r.json()
            return data.get(key, {}) if key else data
        except RequestException as exc:
            self._status = getattr(getattr(exc, "response", None), "status_code", 0) or 0
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

    def get_city_weather(self, city: str, coordinates, api_key: str) -> dict:
        """Fetch current weather data from OpenWeatherMap for a city or location.

        Attempts to fetch weather data by city name first. If that fails, falls back to
        fetching by geographic coordinates (latitude/longitude).

        @param city The city name to query (e.g., "Helsinki").
        @param coordinates Coordinate object with latitude and longitude attributes.
        @param api_key The OpenWeatherMap API key for authentication.
        @return Dictionary containing OpenWeatherMap current weather response.
                Returns empty dict if both requests fail or if @ref has_error is True.
        @details
        - Primary query uses city name for faster lookups
        - Fallback uses coordinates for ambiguous city names or failures
        - API key is required; omitting it will result in authentication errors
        """
        url = Urls.OPENWEATHERMAP_CITY_URL.format(city, api_key)
        data = self._get(url)
        if self.has_error:
            url = Urls.OPENWEATHERMAP_LOCATION_URL.format(
                coordinates.latitude, coordinates.longitude, api_key
            )
            data = self._get(url)
        return data

    def get_forecast(self, coordinates, api_key: str) -> dict:
        """Fetch weather forecast data from OpenWeatherMap for given coordinates.

        Retrieves a multi-day weather forecast (5-day / 3-hour forecast by default)
        from OpenWeatherMap for the specified location.

        @param coordinates Coordinate object with latitude and longitude attributes.
        @param api_key The OpenWeatherMap API key for authentication.
        @return Dictionary containing OpenWeatherMap forecast response with a "list" key
                containing forecast entries. Returns empty dict on error or if @ref has_error is True.
        """
        url = Urls.OPENWEATHERMAP_FORECAST_URL.format(
            coordinates.latitude, coordinates.longitude, api_key
        )
        return self._get(url)

    def build_full_weather_response(
        self,
        station_id: int,
        station_list: WeatherStationList,
        api_key: str,
        lang: str = "fi",
    ) -> dict:
        """Build a comprehensive weather response combining FMI and OpenWeatherMap data.

        Aggregates weather data from multiple sources into a single unified response object.
        Retrieves FMI station data (temperature, humidity, wind, etc.) and optionally
        augments it with OpenWeatherMap current weather symbols and multi-day forecast.

        @param station_id The FMI station identifier to query.
        @param station_list WeatherStationList containing station metadata (names, coordinates).
        @param api_key OpenWeatherMap API key. If empty, only FMI data is returned.
        @param lang Language code for localized output (default: "fi" for Finnish).
        @return Dictionary containing aggregated weather data with the following keys:
                - station_id: The requested station ID
                - station_name: Formatted station name from station_list
                - current_symbol: Weather condition symbol (empty if no OpenWeatherMap data)
                - forecast: Array of forecast objects with time, temperature, and symbol
                - Additional keys from station_data.to_dict(lang)
                Returns error dict if station not found or FMI request fails.
        @details
        - Validates station_id exists in station_list before querying FMI
        - Current weather symbol requires valid api_key and OpenWeatherMap API access
        - Forecast includes up to Constants.FORECAST_CNT entries from OpenWeatherMap
        - Temperature is converted from Kelvin to Celsius (rounded to 1 decimal place)
        - Time is extracted as HH:MM from ISO 8601 datetime string
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

        if api_key:
            city = get_station_city(station_info.formatted_name)
            city_data = self.get_city_weather(city, station_info.coordinates, api_key)
            if city_data and "weather" in city_data:
                weather_id = city_data["weather"][0]["id"]
                result["current_symbol"] = get_weather_symbol(weather_id)

            forecast_data = self.get_forecast(station_info.coordinates, api_key)
            forecasts = []
            for item in forecast_data.get("list", [])[:Constants.FORECAST_CNT]:
                dt_txt = item.get("dt_txt", "")
                time_part = dt_txt[11:16] if len(dt_txt) >= 16 else ""
                temp_k = item.get("main", {}).get("temp", 0)
                temp_c = round(temp_k - 273.15)
                weather_id = item.get("weather", [{}])[0].get("id", 0)
                forecasts.append({
                    "time": time_part,
                    "temperature": f"{temp_c} °C",
                    "symbol": get_weather_symbol(weather_id),
                })
            result["forecast"] = forecasts

        return result
