"""Weather service module for fetching and processing weather data.

This module provides the WeatherService class which handles retrieving weather station
information from Digitraffic (Fintraffic) and weather forecast data from the FMI
(Finnish Meteorological Institute) open data WFS API. It aggregates data from multiple
sources to provide comprehensive weather information for Finnish weather stations.

@author Jari Jankkila
@date 2026
@version 1.0
"""

import datetime
import xml.etree.ElementTree as ET

import requests
from requests.exceptions import RequestException

from .definitions import Constants, Urls
from .fmi_symbols import get_fmi_weather_symbol
from .station_info import WeatherStationList
from .weather_station import WeatherStation


class WeatherService:
    """Service class for weather data retrieval and processing.

    Handles HTTP requests to weather data providers (Digitraffic and FMI WFS) with
    error handling, and aggregates the responses into a unified weather information
    structure. Maintains error state across requests for diagnostic purposes.

    @details
    - Manages HTTP requests to Digitraffic station list and observation endpoints
    - Fetches 3-hourly (today) and daily (future days) forecast data from FMI WFS
    - Parses FMI WFS XML (GML simple feature format) into structured forecast items
    - Provides error tracking and reporting for failed requests
    - Maps FMI WeatherSymbol3 codes to UI emoji symbols
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

    def _get_xml(self, url: str) -> str:
        """Perform an HTTP GET request and return the response body as text.

        Used for XML-returning endpoints (FMI WFS). Applies the same error
        handling and logging as @ref _get but returns raw text instead of
        parsed JSON.

        @param url The URL endpoint to request from.
        @return Response body as a UTF-8 string, or empty string on error.
        """
        self._error = ""
        self._status = 200
        try:
            print(f"[{datetime.datetime.now().strftime('%d/%b/%Y %H:%M:%S')}] GET {url}")
            r = requests.get(url, timeout=10)
            r.raise_for_status()
            return r.text
        except RequestException as exc:
            resp = getattr(exc, "response", None)
            self._status = getattr(resp, "status_code", 0) or 0
            if self._status >= 500:
                self._error = f"Upstream service error (HTTP {self._status})"
            elif self._status >= 400:
                self._error = f"Upstream request failed (HTTP {self._status})"
            else:
                self._error = str(exc)
            return ""

    def _parse_fmi_xml(self, xml_text: str) -> dict[str, dict]:
        """Parse FMI WFS simple-feature XML into a timestamp-keyed parameter dict.

        Iterates over all `BsWfsElement` nodes in the XML, collecting the
        `ParameterName`/`ParameterValue` pairs keyed by their `Time` string.

        @param xml_text Raw XML string from a FMI WFS getFeature response.
        @return dict mapping ISO 8601 timestamp strings to inner dicts of
                {parameter_name: value_string}, e.g.
                {"2026-06-23T12:00:00Z": {"Temperature": "15.5", "WeatherSymbol3": "1"}}.
                Returns empty dict if xml_text is empty or unparseable.
        """
        if not xml_text:
            return {}
        try:
            ns = "http://xml.fmi.fi/schema/wfs/2.0"
            root = ET.fromstring(xml_text)
            result: dict[str, dict] = {}
            for el in root.iter(f"{{{ns}}}BsWfsElement"):
                time_el = el.find(f"{{{ns}}}Time")
                name_el = el.find(f"{{{ns}}}ParameterName")
                value_el = el.find(f"{{{ns}}}ParameterValue")
                if time_el is None or name_el is None or value_el is None:
                    continue
                ts = (time_el.text or "").strip()
                name = (name_el.text or "").strip()
                value = (value_el.text or "").strip()
                if ts:
                    result.setdefault(ts, {})[name] = value
            return result
        except ET.ParseError:
            return {}

    def _get_fmi_forecast(self, coordinates) -> tuple[list[dict], str]:
        """Fetch and parse the FMI WFS forecast for the given coordinates.

        Makes two requests to the FMI open data WFS:
        - A 3-hourly (timestep=180 min) request covering today (UTC).
        - A daily (timestep=1440 min) request covering tomorrow through
          today + 8 days, anchored at noon UTC for representative values.

        @param coordinates Coordinate object with latitude and longitude attributes.
        @return Tuple (forecast_list, current_symbol) where forecast_list contains
                today's 3-hourly items followed by future daily items, and
                current_symbol is the emoji from the first hourly entry (empty
                string on error or if no hourly data is available).
        @details
        - Today's 3-hourly items: {time (HH:MM), date (YYYY-MM-DD),
          temperature (rounded °C string), symbol}.
        - Future daily items: same shape plus daily=True, time="".
        - On any network or parse error, the relevant portion of the forecast
          is silently empty (graceful degradation).
        """
        today = datetime.date.today()
        tomorrow = today + datetime.timedelta(days=1)
        end_daily = today + datetime.timedelta(days=8)

        hourly_url = Urls.FMI_FORECAST_HOURLY_URL.format(
            coordinates.latitude,
            coordinates.longitude,
            f"{today.isoformat()}T00:00:00Z",
            f"{today.isoformat()}T23:59:59Z",
        )
        daily_url = Urls.FMI_FORECAST_DAILY_URL.format(
            coordinates.latitude,
            coordinates.longitude,
            f"{tomorrow.isoformat()}T12:00:00Z",
            f"{end_daily.isoformat()}T12:00:00Z",
        )

        hourly_data = self._parse_fmi_xml(self._get_xml(hourly_url))
        daily_data = self._parse_fmi_xml(self._get_xml(daily_url))

        forecasts: list[dict] = []
        current_symbol = ""
        now_utc = datetime.datetime.now(datetime.timezone.utc)

        for ts in sorted(hourly_data):
            entry = hourly_data[ts]
            try:
                temp_c = round(float(entry.get("Temperature", 0)))
            except (ValueError, TypeError):
                temp_c = 0
            symbol = get_fmi_weather_symbol(entry.get("WeatherSymbol3", ""))

            slot_start = datetime.datetime.fromisoformat(ts.replace("Z", "+00:00"))
            slot_end = slot_start + datetime.timedelta(hours=3)

            # current_symbol tracks the most recently started slot (current conditions).
            # Falls back to the first future slot if no past slot exists yet.
            if slot_start <= now_utc:
                current_symbol = symbol
            elif not current_symbol:
                current_symbol = symbol

            # Skip slots whose 3-hour window has already ended.
            if slot_end <= now_utc:
                continue

            forecasts.append({
                "time": ts[11:16],
                "date": ts[:10],
                "temperature": f"{temp_c} \u00b0C",
                "symbol": symbol,
            })

        for ts in sorted(daily_data):
            entry = daily_data[ts]
            try:
                temp_c = round(float(entry.get("Temperature", 0)))
            except (ValueError, TypeError):
                temp_c = 0
            symbol = get_fmi_weather_symbol(entry.get("WeatherSymbol3", ""))
            forecasts.append({
                "time": "",
                "date": ts[:10],
                "temperature": f"{temp_c} \u00b0C",
                "symbol": symbol,
                "daily": True,
            })

        return forecasts, current_symbol

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

    def build_full_weather_response(
        self,
        station_id: int,
        station_list: WeatherStationList,
        lang: str = "fi",
    ) -> dict:
        """Build a comprehensive weather response combining Digitraffic and FMI forecast data.

        Aggregates weather data from multiple sources into a single unified response object.
        Retrieves Digitraffic station observations and unconditionally augments them with
        FMI WFS forecast data (no API key required).

        @param station_id The Digitraffic station identifier to query.
        @param station_list WeatherStationList containing station metadata (names, coordinates).
        @param lang Language code for localized output (default: "fi" for Finnish).
        @return Dictionary containing aggregated weather data with the following keys:
                - station_id: The requested station ID
                - station_name: Formatted station name from station_list
                - current_symbol: Weather emoji from the first FMI 3-hourly forecast
                  entry for today (empty string if forecast is unavailable)
                - forecast: Mixed list of forecast objects. Today's 3-hourly entries
                  carry time (HH:MM), date (YYYY-MM-DD), temperature (rounded °C
                  string), and symbol. Future daily entries additionally carry
                  daily=True and have an empty time string.
                - _next_update_at: datetime of the next expected Digitraffic observation
                  (internal; stripped by the view before sending the JSON response)
                - Additional keys from station_data.to_dict(lang)
                Returns {"error": <clean message>} if station not found or Digitraffic
                request fails.
        @details
        - Validates station_id exists in station_list before querying Digitraffic
        - Forecast is always fetched unconditionally from FMI open data (no API key needed)
        - FMI errors degrade gracefully: current_symbol="" and forecast=[] alongside
          the Digitraffic observation data
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
        result["_next_update_at"] = station_data.next_update_at

        forecast, current_symbol = self._get_fmi_forecast(station_info.coordinates)
        result["current_symbol"] = current_symbol
        result["forecast"] = forecast

        return result
