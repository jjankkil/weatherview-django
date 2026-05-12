import math
from datetime import datetime, timezone

from .definitions import Constants, ConversionType
from .physics import fmi_feels_like_temperature
from .ui_helpers import wind_direction_as_text


def _parse_timestamp(ts: str) -> datetime:
    try:
        from dateutil import parser as dp
        return dp.parse(ts)
    except Exception:
        return datetime(1970, 1, 1, tzinfo=timezone.utc)


class Sensor:
    INVALID_VALUE = -999

    def __init__(self):
        self.id = 0
        self.station_id = 0
        self.name = ""
        self.short_name = ""
        self.value = 0.0
        self.unit = ""
        self.sensor_value_description = ""
        self.measured_time: datetime = datetime(1970, 1, 1, tzinfo=timezone.utc)

    def parse(self, data: dict) -> bool:
        try:
            self.id = data["id"]
            self.station_id = data["stationId"]
            self.name = data["name"]
            self.short_name = data.get("shortName", "")
            self.measured_time = _parse_timestamp(data["measuredTime"])
            self.value = data["value"]
            unit = data.get("unit", "")
            self.unit = "" if unit in Constants.MISSING_UNIT else unit
            self.sensor_value_description = data.get("sensorValueDescriptionFi", "")
            return True
        except Exception:
            return False


class WeatherStation:
    def __init__(self):
        self.sensors: list[Sensor] = []
        self._latest_time: datetime = datetime(1970, 1, 1, tzinfo=timezone.utc)
        self._previous_time: datetime = datetime(1970, 1, 1, tzinfo=timezone.utc)

    def parse(self, data: dict) -> bool:
        obs_time = _parse_timestamp(data.get("dataUpdatedTime", ""))
        if self._latest_time == self._previous_time:
            self._previous_time = obs_time
            self._latest_time = obs_time
        elif obs_time != self._previous_time:
            self._previous_time = self._latest_time
            self._latest_time = obs_time

        self.sensors.clear()
        for s_data in data.get("sensorValues", []):
            sensor = Sensor()
            if sensor.parse(s_data):
                self.sensors.append(sensor)
        return True

    def _find(self, name: str):
        for s in self.sensors:
            if s.name == name:
                return s
        return None

    def _find_by_id(self, sensor_id: int):
        for s in self.sensors:
            if s.id == sensor_id:
                return s
        return None

    def get_value(self, identifier: str, conv=ConversionType.TO_INT):
        if identifier.isnumeric():
            s = self._find_by_id(int(identifier))
        else:
            s = self._find(identifier)
        if s is None:
            return Constants.INVALID_VALUE
        if conv == ConversionType.TO_FLOAT:
            return float(str(s.value))
        return int(str(s.value).split(".")[0])

    def get_formatted(self, name: str) -> str:
        s = self._find(name)
        if s:
            return f"{s.value} {s.unit}".strip()
        return ""

    @property
    def observation_time(self) -> datetime:
        return self._latest_time

    @property
    def air_temperature(self) -> float:
        return self.get_value("ILMA", ConversionType.TO_FLOAT)

    @property
    def air_humidity(self) -> float:
        return self.get_value("ILMAN_KOSTEUS", ConversionType.TO_FLOAT)

    @property
    def wind_speed(self) -> float:
        return self.get_value("KESKITUULI", ConversionType.TO_FLOAT)

    @property
    def wind_direction(self):
        return self.get_value("TUULENSUUNTA")

    @property
    def visibility(self):
        return self.get_value("58")

    @property
    def visibility_str(self) -> str:
        v = self.visibility
        if v is None or v < 0:
            return ""
        if v >= 1000:
            return f"{math.floor(v / 1000)} km"
        if v >= 100:
            return f"{math.floor(v - v % 100)} m"
        return f"{math.floor(v - v % 10)} m"

    @property
    def feels_like(self) -> float:
        return fmi_feels_like_temperature(self.wind_speed, self.air_humidity, self.air_temperature)

    @property
    def present_weather(self) -> tuple[str, str]:
        s = self._find("SADE")
        if s is None:
            return "Säätila:", ""
        label = "Sade:" if s.value >= 1.0 else "Säätila:"
        return label, s.sensor_value_description

    @property
    def seconds_until_next_update(self) -> int:
        if self._latest_time == self._previous_time:
            return Constants.DEFAULT_POLLING_INTERVAL_S
        interval = abs((self._latest_time - self._previous_time).total_seconds())
        try:
            from django.utils import timezone as dj_tz
            now = dj_tz.now()
        except Exception:
            now = datetime.now(tz=timezone.utc)
        elapsed = (now - self._latest_time).total_seconds()
        wait = interval - elapsed + Constants.STATION_UPDATE_DELAY_S
        return max(0, min(int(wait), 600))

    def to_dict(self, lang: str = "fi") -> dict:
        temp = self.air_temperature
        feels = self.feels_like
        wind = self.wind_speed
        wind_dir = self.wind_direction
        pw_label, pw_text = self.present_weather

        wind_dir_text = wind_direction_as_text(
            wind_dir if wind_dir != Constants.INVALID_VALUE else None, lang
        )

        return {
            "observation_time": self._latest_time.strftime("%d.%m.%Y %H:%M") if self._latest_time.year > 1970 else "",
            "temperature": f"{temp} °C" if temp != Constants.INVALID_VALUE else "",
            "temperature_raw": temp if temp != Constants.INVALID_VALUE else None,
            "feels_like": f"{feels} °C" if feels != Constants.INVALID_VALUE else "",
            "temperature_change": self.get_formatted("ILMA_DERIVAATTA"),
            "wind_speed": self.get_formatted("KESKITUULI"),
            "wind_speed_raw": wind if wind != Constants.INVALID_VALUE else None,
            "wind_max": self.get_formatted("MAKSIMITUULI"),
            "wind_direction": wind_dir_text,
            "humidity": self.get_formatted("ILMAN_KOSTEUS"),
            "visibility": self.visibility_str,
            "present_weather_label": pw_label,
            "present_weather": pw_text,
            "seconds_until_next_update": self.seconds_until_next_update,
        }
