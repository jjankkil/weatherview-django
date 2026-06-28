"""Weather service module for fetching and processing weather data.

This module provides focused classes for HTTP transport, FMI XML parsing,
FMI forecast assembly, and top-level orchestration. The public API entry
point is WeatherService.build_full_weather_response().

Classes:
    HttpClient         -- Shared HTTP transport with error normalisation.
    FmiXmlParser       -- Stateless FMI WFS XML parser.
    FmiForecastService -- FMI forecast assembly (hourly + daily).
    WeatherService     -- Top-level orchestrator; public API.

@author Jari Jankkila
@date 2026
@version 1.0
"""

import datetime
import logging
import xml.etree.ElementTree as ET

import requests
from requests.exceptions import RequestException

from .definitions import Constants, Formats, Urls
from .fmi_symbols import get_fmi_weather_symbol
from .station_info import WeatherStationList
from .weather_station import WeatherStation

logger = logging.getLogger(__name__)


class HttpClient:
    """Shared HTTP transport layer with error normalisation.

    Maintains error state (_error, _status) after each request so callers can
    inspect has_error / error_message without catching exceptions themselves.

    @details
    - JSON GET via _get(url, key)
    - Plain-text GET via _get_xml(url)
    - On HTTP 5xx: error "Upstream service error (HTTP <n>)"
    - On HTTP 4xx: error "Upstream request failed (HTTP <n>)"
    - On network failure: error = str(exc), status = 0
    """

    def __init__(self) -> None:
        self._error: str = ""
        self._status: int = 200

    @property
    def has_error(self) -> bool:
        """@return True if the last request failed."""
        return self._status != 200 or bool(self._error)

    @property
    def error_message(self) -> str:
        """@return Human-readable error string from the last failed request."""
        return self._error

    def _normalise_error(self, exc: RequestException) -> None:
        resp = getattr(exc, "response", None)
        self._status = getattr(resp, "status_code", 0) or 0
        if self._status >= 500:
            self._error = f"Upstream service error (HTTP {self._status})"
        elif self._status >= 400:
            self._error = f"Upstream request failed (HTTP {self._status})"
        else:
            self._error = str(exc)

    def _get(self, url: str, key: str = "") -> dict | list:
        """HTTP GET → parsed JSON.

        @param url  Endpoint URL.
        @param key  If given, return response[key] instead of the full object.
        @return dict or list on success; empty dict on error.
        """
        self._error = ""
        self._status = 200
        try:
            display_url = url.split("appid=")[0].rstrip("&?") + "..." if "appid=" in url else url
            logger.debug("GET %s", display_url)
            r = requests.get(url, timeout=10)
            r.raise_for_status()
            data = r.json()
            return data.get(key, {}) if key else data
        except RequestException as exc:
            self._normalise_error(exc)
            return {}

    def _get_xml(self, url: str) -> str:
        """HTTP GET → response text (for XML endpoints).

        @param url  Endpoint URL.
        @return Response body as a string; empty string on error.
        """
        self._error = ""
        self._status = 200
        try:
            logger.debug("GET %s", url)
            r = requests.get(url, timeout=10)
            r.raise_for_status()
            return r.text
        except RequestException as exc:
            self._normalise_error(exc)
            return ""


class FmiXmlParser:
    """Stateless parser for FMI WFS BsWfs simple-feature XML.

    @details
    Iterates over BsWfsElement nodes and returns a dict keyed by ISO 8601
    timestamp, where each value is a dict of {ParameterName: ParameterValue}.
    """

    _NS = "http://xml.fmi.fi/schema/wfs/2.0"

    @classmethod
    def parse(cls, xml_text: str) -> dict[str, dict]:
        """Parse FMI WFS XML into a timestamp-keyed parameter dict.

        @param xml_text  Raw XML string from a FMI WFS getFeature response.
        @return dict mapping ISO 8601 timestamps to {param_name: value_str}.
                Returns empty dict if xml_text is empty or unparseable.
        """
        if not xml_text:
            return {}
        try:
            ns = cls._NS
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


class FmiForecastService:
    """Assembles FMI WFS hourly + daily forecast data for a given location.

    Delegates HTTP transport to an HttpClient instance and XML parsing to
    FmiXmlParser so each concern is independently testable.

    @param http_client  HttpClient used for outbound requests.
    """

    def __init__(self, http_client: HttpClient) -> None:
        self._http = http_client
        self._parser = FmiXmlParser()

    def get_forecast(self, coordinates) -> tuple[list[dict], str]:
        """Fetch and assemble FMI WFS hourly + daily forecast.

        Makes two WFS requests:
        - 3-hourly (timestep=180 min) covering today (UTC).
        - Daily (timestep=1440 min) covering tomorrow through today + 8 days.

        @param coordinates  Object with .latitude and .longitude attributes.
        @return Tuple (forecast_list, current_symbol).
                forecast_list: today's 3-hourly items then future daily items.
                current_symbol: emoji for the most recently started 3-h slot
                                (empty string if no hourly data).
        @details
        - Hourly items: {time (HH:MM), date (YYYY-MM-DD), temperature, symbol}.
        - Daily items: same shape plus daily=True and time="".
        - FMI errors degrade gracefully to empty lists (no exception raised).
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

        hourly_data = FmiXmlParser.parse(self._http._get_xml(hourly_url))
        daily_data = FmiXmlParser.parse(self._http._get_xml(daily_url))

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

            # current_symbol: use most-recently-started slot; fall back to first future slot.
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


class WeatherService(HttpClient):
    """Top-level orchestrator for weather data retrieval.

    Extends HttpClient so that has_error / error_message from Digitraffic
    requests are directly accessible on the service instance (preserving the
    existing public API).  Delegates FMI forecast assembly to FmiForecastService.

    Public API (unchanged):
        get_station_list()
        get_station_data(station_id)
        build_full_weather_response(station_id, station_list, lang)
        has_error
        error_message
    """

    def __init__(self) -> None:
        super().__init__()
        self._forecast_service = FmiForecastService(self)

    def get_station_list(self) -> WeatherStationList:
        """Fetch and parse the Digitraffic weather station list.

        @return WeatherStationList sorted alphabetically.
                Empty list if the request fails.
        """
        raw = self._get(Urls.STATION_LIST_URL, "features")
        station_list = WeatherStationList()
        if raw:
            station_list.parse(raw)
            station_list.sort_by_name()
        return station_list

    def get_station_data(self, station_id: int) -> WeatherStation:
        """Fetch current observations for a specific Digitraffic station.

        @param station_id  Digitraffic station identifier.
        @return WeatherStation populated with sensor values.
                Empty station if the request fails.
        """
        url = Urls.WEATHER_STATION_URL.format(station_id)
        raw = self._get(url)
        station = WeatherStation()
        if raw:
            station.parse(raw)
        return station

    _HISTORY_SENSOR_TEMP = 1     #!< Sensor ID for air temperature (ILMA, °C)
    _HISTORY_SENSOR_PRECIP = 23  #!< Sensor ID for precipitation intensity (SADE_INTENSITEETTI, mm/h)
    _TEMP_BUCKET_MINUTES = 10    #!< Temperature bucket size in minutes (fine-grained curve)

    def get_station_history(self, station_id: int, hours: int = 24) -> dict:
        """Fetch and bucket sensor history for temperature and precipitation.

        Queries the Digitraffic history endpoint for up to @p hours of sensor data.
        Temperature is bucketed at @ref _TEMP_BUCKET_MINUTES (10 min) for a smooth line;
        precipitation is bucketed hourly so the chart renders exactly one bar per hour.

        @param station_id  Digitraffic station identifier.
        @param hours       Window length in hours (1–24; clamped internally).
        @return dict with keys:
                - temp_series:  list of {time (ISO 8601 UTC), temperature (float|None)}
                - precip_series: list of {time (ISO 8601 UTC), precipitation (float|None)}
                - has_precipitation: True if the station has a precipitation sensor
                  (regardless of whether it rained during the window)
        @details
        - Temperature sensor: ID 1 (ILMA, °C), averaged per 10-minute bucket.
        - Precipitation sensor: ID 23 (SADE_INTENSITEETTI, mm/h), averaged per hourly bucket.
        - Missing or invalid sensor values (≤ Constants.INVALID_VALUE) are excluded.
        - Returns empty series on HTTP error; has_error/error_message reflect the failure.
        """
        hours = max(1, min(24, hours))
        now = datetime.datetime.now(datetime.timezone.utc)
        from_dt = now - datetime.timedelta(hours=hours)
        url = (
            Urls.WEATHER_STATION_HISTORY_URL.format(station_id)
            + f"?from={from_dt.strftime(Formats.UTC_TIMESTAMP_FORMAT)}"
            + f"&to={now.strftime(Formats.UTC_TIMESTAMP_FORMAT)}"
        )
        raw = self._get(url)
        if self.has_error or not raw:
            return {"temp_series": [], "precip_series": [], "has_precipitation": False}

        temp_sums: dict[str, float] = {}
        temp_counts: dict[str, int] = {}
        precip_sums: dict[str, float] = {}
        precip_counts: dict[str, int] = {}

        for v in raw.get("values", []):
            sensor_id = v.get("id")
            if sensor_id not in (self._HISTORY_SENSOR_TEMP, self._HISTORY_SENSOR_PRECIP):
                continue
            val = v.get("value")
            if val is None or val <= Constants.INVALID_VALUE:
                continue
            try:
                t = datetime.datetime.fromisoformat(v["measuredTime"].replace("Z", "+00:00"))
            except (KeyError, ValueError):
                continue
            if t < from_dt:
                continue
            if sensor_id == self._HISTORY_SENSOR_TEMP:
                m = (t.minute // self._TEMP_BUCKET_MINUTES) * self._TEMP_BUCKET_MINUTES
                bucket = t.replace(minute=m, second=0, microsecond=0).strftime(Formats.UTC_TIMESTAMP_FORMAT)
                temp_sums[bucket] = temp_sums.get(bucket, 0.0) + val
                temp_counts[bucket] = temp_counts.get(bucket, 0) + 1
            else:
                bucket = t.replace(minute=0, second=0, microsecond=0).strftime(Formats.UTC_TIMESTAMP_FORMAT)
                precip_sums[bucket] = precip_sums.get(bucket, 0.0) + val
                precip_counts[bucket] = precip_counts.get(bucket, 0) + 1

        # Ceil from_dt to the next complete hour so both series start at a clean
        # hour boundary with no empty leading stub (e.g. from_dt=03:35 → start=04:00).
        hour_start = from_dt.replace(minute=0, second=0, microsecond=0)
        if from_dt.minute or from_dt.second or from_dt.microsecond:
            hour_start += datetime.timedelta(hours=1)

        # Build temperature series at 10-minute resolution
        temp_series: list[dict] = []
        step = datetime.timedelta(minutes=self._TEMP_BUCKET_MINUTES)
        current = hour_start
        while current <= now:
            bucket = current.strftime(Formats.UTC_TIMESTAMP_FORMAT)
            temp = round(temp_sums[bucket] / temp_counts[bucket], 1) if bucket in temp_counts else None
            temp_series.append({"time": bucket, "temperature": temp})
            current += step

        # Build precipitation series at hourly resolution
        precip_series: list[dict] = []
        current = hour_start
        while current <= now:
            bucket = current.strftime(Formats.UTC_TIMESTAMP_FORMAT)
            precip = round(precip_sums[bucket] / precip_counts[bucket], 2) if bucket in precip_counts else None
            precip_series.append({"time": bucket, "precipitation": precip})
            current += datetime.timedelta(hours=1)

        has_precipitation = bool(precip_counts)  # True whenever the station has a precip sensor
        return {
            "temp_series": temp_series,
            "precip_series": precip_series,
            "has_precipitation": has_precipitation,
        }

    def build_full_weather_response(        self,
        station_id: int,
        station_list: WeatherStationList,
        lang: str = "fi",
    ) -> dict:
        """Build a comprehensive weather response combining Digitraffic and FMI data.

        @param station_id   Digitraffic station ID to query.
        @param station_list WeatherStationList with station metadata.
        @param lang         Language code for localised output (default: "fi").
        @return dict with weather data keys including station_id, station_name,
                current_symbol, forecast, _next_update_at, and sensor fields
                from station_data.to_dict(lang).
                Returns {"error": <message>} if the station is not found or
                the Digitraffic request fails.
        @details
        - FMI forecast is always fetched; errors degrade gracefully (empty list).
        - _next_update_at is internal and stripped by the view before sending JSON.
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

        forecast, current_symbol = self._forecast_service.get_forecast(station_info.coordinates)
        result["current_symbol"] = current_symbol
        result["forecast"] = forecast

        return result
