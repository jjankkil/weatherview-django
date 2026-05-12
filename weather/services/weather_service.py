import requests
from requests.exceptions import RequestException

from .definitions import Urls
from .station_info import WeatherStationList
from .weather_station import WeatherStation
from .ui_helpers import get_weather_symbol, get_station_city
from .definitions import Constants


class WeatherService:
    def __init__(self):
        self._error = ""
        self._status = 200

    @property
    def has_error(self) -> bool:
        return self._status != 200 or bool(self._error)

    @property
    def error_message(self) -> str:
        return self._error

    def _get(self, url: str, key: str = "") -> dict | list:
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
        raw = self._get(Urls.STATION_LIST_URL, "features")
        station_list = WeatherStationList()
        if raw:
            station_list.parse(raw)
            station_list.sort_by_name()
        return station_list

    def get_station_data(self, station_id: int) -> WeatherStation:
        url = Urls.WEATHER_STATION_URL.format(station_id)
        raw = self._get(url)
        station = WeatherStation()
        if raw:
            station.parse(raw)
        return station

    def get_city_weather(self, city: str, coordinates, api_key: str) -> dict:
        url = Urls.OPENWEATHERMAP_CITY_URL.format(city, api_key)
        data = self._get(url)
        if self.has_error:
            url = Urls.OPENWEATHERMAP_LOCATION_URL.format(
                coordinates.latitude, coordinates.longitude, api_key
            )
            data = self._get(url)
        return data

    def get_forecast(self, coordinates, api_key: str) -> dict:
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
                temp_c = round(temp_k - 273.15, 1)
                weather_id = item.get("weather", [{}])[0].get("id", 0)
                forecasts.append({
                    "time": time_part,
                    "temperature": f"{temp_c} °C",
                    "symbol": get_weather_symbol(weather_id),
                })
            result["forecast"] = forecasts

        return result
