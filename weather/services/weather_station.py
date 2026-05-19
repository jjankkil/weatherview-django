"""Weather station data models and sensor value extraction.

Provides classes for representing FMI weather station observations including sensor
data, measurement timestamps, and computed derived values (feels-like temperature,
visibility formatting, update timing).

@author Jari Jankkila
@date 2026
@version 1.0
"""

import math
from datetime import datetime, timezone

from .definitions import Constants, ConversionType
from .physics import fmi_feels_like_temperature
from .ui_helpers import wind_direction_as_text


def _parse_timestamp(ts: str) -> datetime:
    """Parse ISO 8601 timestamp string into a datetime object.

    Attempts to parse a timestamp string using the dateutil library (more flexible)
    and falls back to epoch time (1970-01-01) if parsing fails.

    @param ts ISO 8601 formatted timestamp string (e.g., "2026-05-13T14:30:00Z").
    @return Parsed datetime object in UTC timezone. Returns epoch (1970-01-01) on parse error.
    @details
    - Uses dateutil.parser for flexible ISO 8601 parsing
    - Falls back gracefully if dateutil is unavailable or parsing fails
    - All returned datetimes are in UTC timezone
    """
    try:
        from dateutil import parser as dp
        return dp.parse(ts)
    except Exception:
        return datetime(1970, 1, 1, tzinfo=timezone.utc)


class Sensor:
    """Individual sensor measurement from an FMI weather station.

    Represents a single sensor reading including the measured value, unit,
    timestamp, and descriptive information. Sensor names are FMI-specific codes
    that identify the measurement type.
    """
    INVALID_VALUE = -999  #!< Sentinel value for missing or invalid measurements

    def __init__(self):
        """Initialize an empty Sensor object."""
        self.id = 0  #!< Unique sensor identifier
        self.station_id = 0  #!< FMI station ID this sensor belongs to
        self.name = ""  #!< FMI sensor name code (e.g., "ILMA", "KESKITUULI", "ILMAN_KOSTEUS")
        self.short_name = ""  #!< Optional abbreviated sensor name
        self.value = 0.0  #!< Measured sensor value
        self.unit = ""  #!< Unit of measurement (e.g., "°C", "m/s", "%"). Empty if missing.
        self.sensor_value_description = ""  #!< Finnish description of the measurement or condition
        self.measured_time: datetime = datetime(1970, 1, 1, tzinfo=timezone.utc)  #!< Timestamp of measurement

    def parse(self, data: dict) -> bool:
        """Parse FMI sensor data object into sensor attributes.

        Extracts sensor information from FMI API response data, including measurement
        value, unit, timestamp, and localized description. Missing or placeholder unit
        values are converted to empty strings.

        @param data Dictionary from FMI sensor values API response.
        @return True if parsing succeeded, False if required keys are missing.
        @details
        - Expects keys: id, stationId, name, measuredTime, value
        - Optional keys: shortName, unit, sensorValueDescriptionFi
        - Units matching Constants.MISSING_UNIT patterns ("///", "???") are replaced with empty string
        - Timestamp is parsed using @ref _parse_timestamp
        - Returns False without throwing on missing required keys
        """
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
    """FMI weather station with collection of sensor measurements.

    Represents a single weather station's observations including multiple sensor
    readings (temperature, humidity, wind, etc.). Tracks observation timestamps to
    calculate update intervals and manages sensor data retrieval.

    @details
    - Maintains both current and previous observation timestamps for update timing
    - Provides convenience properties for common weather measurements
    - Calculates derived values (feels-like temperature, formatted visibility)
    - Converts raw API values to appropriate units and formats
    """
    def __init__(self):
        """Initialize an empty WeatherStation object."""
        self.sensors: list[Sensor] = []  #!< List of sensor measurements
        self._latest_time: datetime = datetime(1970, 1, 1, tzinfo=timezone.utc)  #!< Most recent observation timestamp
        self._previous_time: datetime = datetime(1970, 1, 1, tzinfo=timezone.utc)  #!< Previous observation timestamp (for interval calculation)

    def parse(self, data: dict) -> bool:
        """Parse FMI weather station observation data.

        Extracts all sensor measurements from FMI API response and updates observation
        timestamps. Tracks both latest and previous update times for update interval calculation.

        @param data Dictionary from FMI station weather data API response.
        @return True after parsing completes (always succeeds in structure).
        @details
        - Expects key: sensorValues (array of sensor dictionaries)
        - Optional key: dataUpdatedTime (ISO 8601 timestamp)
        - Updates _latest_time and _previous_time to track observation timing
        - Sensors that fail to parse are silently skipped
        - Clears existing sensors before parsing new data
        """
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
        """Find a sensor by its FMI name code.

        Internal method for locating a sensor in the collection by name identifier.

        @param name FMI sensor name code (e.g., "ILMA" for air temperature).
        @return Sensor object if found, None otherwise.
        """
        for s in self.sensors:
            if s.name == name:
                return s
        return None

    def _find_by_id(self, sensor_id: int):
        """Find a sensor by its unique identifier.

        Internal method for locating a sensor in the collection by numeric ID.

        @param sensor_id Unique sensor identifier.
        @return Sensor object if found, None otherwise.
        """
        for s in self.sensors:
            if s.id == sensor_id:
                return s
        return None

    def get_value(self, identifier: str, conv=ConversionType.TO_INT):
        """Get a sensor value by name or ID with optional type conversion.

        Retrieves a sensor measurement and converts it to the specified numeric type.
        Identifier can be either a sensor name (string) or a numeric ID (numeric string).

        @param identifier Sensor name (FMI code like "ILMA") or numeric ID as string.
        @param conv ConversionType specifying output format (TO_INT or TO_FLOAT).
        @return Converted sensor value, or Constants.INVALID_VALUE if sensor not found.
        @details
        - If identifier is numeric (only digits), searches by sensor ID
        - Otherwise, searches by sensor name code
        - TO_INT: truncates decimal portion by splitting on "." and taking first part
        - TO_FLOAT: converts entire value to float
        - Returns sentinel value if sensor not found in collection
        """
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
        """Get a sensor reading as a formatted display string with unit.

        Retrieves a sensor value and combines it with its unit for display.

        @param name FMI sensor name code.
        @return Formatted string like "20.5 °C" or empty string if sensor not found.
        """
        s = self._find(name)
        if s:
            return f"{s.value} {s.unit}".strip()
        return ""

    @property
    def observation_time(self) -> datetime:
        """Get the timestamp of the latest observation.

        @return Timestamp (UTC timezone) of the most recent measurement update.
        """
        return self._latest_time

    @property
    def air_temperature(self) -> float:
        """Get the current air temperature reading.

        @return Air temperature in Celsius, or Constants.INVALID_VALUE if not available.
        """
        return self.get_value("ILMA", ConversionType.TO_FLOAT)

    @property
    def air_humidity(self) -> float:
        """Get the current relative humidity reading.

        @return Relative humidity as percentage (0-100), or Constants.INVALID_VALUE if not available.
        """
        return self.get_value("ILMAN_KOSTEUS", ConversionType.TO_FLOAT)

    @property
    def dew_point(self) -> float:
        """Get the dew point temperature reading.

        @return Dew point in Celsius, or Constants.INVALID_VALUE if not available.
        """
        return self.get_value("KASTEPISTE", ConversionType.TO_FLOAT)

    @property
    def road_temperature(self) -> float:
        """Get the road surface temperature reading.

        Tries sensors TIE_1 through TIE_4 in order, returning the first valid reading.

        @return Road surface temperature in Celsius, or Constants.INVALID_VALUE if not available.
        """
        for name in ("TIE_1", "TIE_2", "TIE_3", "TIE_4"):
            v = self.get_value(name, ConversionType.TO_FLOAT)
            if v != Constants.INVALID_VALUE:
                return v
        return Constants.INVALID_VALUE

    @property
    def wind_speed(self) -> float:
        """Get the current wind speed reading.

        @return Wind speed in m/s, or Constants.INVALID_VALUE if not available.
        """
        return self.get_value("KESKITUULI", ConversionType.TO_FLOAT)

    @property
    def wind_direction(self):
        """Get the current wind direction reading.

        @return Wind direction in degrees (0-360), or Constants.INVALID_VALUE if not available.
        """
        return self.get_value("TUULENSUUNTA")

    @property
    def visibility(self):
        """Get the current visibility measurement.

        @return Visibility in meters, or Constants.INVALID_VALUE if not available.
        """
        return self.get_value("58")

    @property
    def visibility_str(self) -> str:
        """Get visibility as a human-readable formatted string.

        Converts raw visibility measurement (in meters) to a formatted string with
        appropriate units (m or km) and precision.

        @return Formatted visibility string (e.g., "5 km", "200 m"), or empty string if unavailable.
        @details
        - >= 1000 m: displayed as kilometers (rounded down to nearest km)
        - 100-999 m: displayed as meters (rounded down to nearest 100 m)
        - < 100 m: displayed as meters (rounded down to nearest 10 m)
        - Returns empty string if visibility is negative or not available
        """
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
        """Get the perceived temperature combining wind chill and heat index.

        Calculates FMI feels-like temperature using @ref fmi_feels_like_temperature with
        current wind speed, humidity, and air temperature.

        @return Perceived temperature in Celsius, or Constants.INVALID_VALUE if inputs are unavailable.
        """
        return fmi_feels_like_temperature(self.wind_speed, self.air_humidity, self.air_temperature)

    @property
    def present_weather(self) -> tuple[str, str]:
        """Get the current weather condition (precipitation or general description).

        Returns a tuple of (label, description) describing current weather. Label indicates
        type of weather, and description provides Finnish localized text.

        @return Tuple of (label_string, description_string):
                - If precipitation detected: ("Sade:", weather_description)
                - If no precipitation: ("Säätila:", weather_description or empty)
                - If sensor missing: ("Säätila:", "")
        @details
        - Looks up "SADE" sensor for precipitation data
        - Classifies as rain if sensor value >= 1.0
        - Uses sensor_value_description for Finnish condition text
        """
        s = self._find("SADE")
        if s is None:
            return "Säätila:", ""
        label = "Sade:" if s.value >= 1.0 else "Säätila:"
        return label, s.sensor_value_description

    @property
    def seconds_until_next_update(self) -> int:
        """Calculate seconds until the next expected data update.

        Estimates the time until the next observation based on the observed update interval
        between the latest two observations. Used for scheduling client-side polling.

        @return Seconds to wait before polling for the next update. Clamped to [0, 600].
        @details
        - If no prior observation: returns DEFAULT_POLLING_INTERVAL_S (60s)
        - Otherwise: calculates interval between latest and previous observations
        - Factors in elapsed time since latest observation
        - Adds STATION_UPDATE_DELAY_S buffer before the expected next update time
        - Clamped to minimum 0 (update available now) and maximum 600s (10 min)
        - Attempts to use Django timezone for current time if available; falls back to UTC
        """
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
        """Convert station data to dictionary representation suitable for templates/APIs.

        Creates a formatted dictionary with all weather observations and derived values,
        with units and localized strings ready for display. Includes both formatted strings
        and raw numeric values where applicable.

        @param lang Language code for localization ("fi" for Finnish, "en" for English, etc.).
        @return Dictionary with formatted weather data keys suitable for JSON serialization:
                - observation_time: formatted timestamp (Finnish format) or empty if not available
                - temperature: formatted string with unit (e.g., "20.5 °C") or empty
                - temperature_raw: numeric temperature value or None if unavailable
                - feels_like: formatted perceived temperature (rounded integer) or empty
                - temperature_change: formatted rate of change string (value + unit) or empty
                - wind_speed: formatted wind speed with unit or empty
                - wind_speed_raw: numeric wind speed value or None if unavailable
                - wind_max: formatted maximum wind gust with unit or empty
                - wind_direction: localized cardinal direction text or empty
                - humidity: formatted relative humidity with unit or empty
                - dew_point: formatted dew point temperature from KASTEPISTE sensor or empty
                - road_temperature: formatted road surface temperature or empty
                - visibility: formatted visibility (e.g., "5 km") or empty
                - present_weather_label: weather category label ("Sade:" or "Säätila:") or empty
                - present_weather: Finnish weather condition description or empty
                - seconds_until_next_update: integer seconds until next polling expected
        @details
        - Timestamp formatted as "DD.MM.YYYY HH:MM" in Finnish format
        - All values use Constants.INVALID_VALUE to detect missing data
        - Wind direction translation uses lang parameter via @ref wind_direction_as_text
        - Formatted values include units; raw values omit units
        - Returns both formatted and raw numeric values for flexibility
        """
        temp = self.air_temperature
        feels = self.feels_like
        wind = self.wind_speed
        wind_dir = self.wind_direction
        pw_label, pw_text = self.present_weather

        wind_dir_text = wind_direction_as_text(
            wind_dir if wind_dir != Constants.INVALID_VALUE else None, lang
        )

        obs_time_str = ""
        if self._latest_time.year > 1970:
            try:
                from django.utils import timezone as dj_tz
                local_time = dj_tz.localtime(self._latest_time)
                obs_time_str = local_time.strftime("%d.%m.%Y %H:%M")
            except Exception:
                obs_time_str = self._latest_time.strftime("%d.%m.%Y %H:%M")

        return {
            "observation_time": obs_time_str,
            "temperature": f"{temp} °C" if temp != Constants.INVALID_VALUE else "",
            "temperature_raw": temp if temp != Constants.INVALID_VALUE else None,
            "feels_like": f"{round(feels)} °C" if feels != Constants.INVALID_VALUE else "",
            "temperature_change": self.get_formatted("ILMA_DERIVAATTA"),
            "wind_speed": self.get_formatted("KESKITUULI"),
            "wind_speed_raw": wind if wind != Constants.INVALID_VALUE else None,
            "wind_max": self.get_formatted("MAKSIMITUULI"),
            "wind_direction": wind_dir_text,
            "humidity": self.get_formatted("ILMAN_KOSTEUS"),
            "dew_point": self.get_formatted("KASTEPISTE"),
            "road_temperature": f"{self.road_temperature} °C" if self.road_temperature != Constants.INVALID_VALUE else "",
            "visibility": self.visibility_str,
            "present_weather_label": pw_label,
            "present_weather": pw_text,
            "seconds_until_next_update": self.seconds_until_next_update,
        }
