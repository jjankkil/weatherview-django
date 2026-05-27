"""Constant definitions and configuration values for the weather service.

Centralizes all constant values, API endpoints, URL templates, formatting specifications,
and enum types used throughout the weather service module.

@author Jari Jankkila
@date 2026
@version 1.0
"""

import enum


class Constants:
    """Application-wide constant values and configuration parameters.

    Defines sentinel values, timing parameters, and data limits used by the weather service.
    """
    FORECAST_CNT = 3  #!< Legacy constant (no longer used for forecast slicing; kept for reference)
    STATION_UPDATE_DELAY_S = 60  #!< Delay in seconds before checking for new station data
    DEFAULT_POLLING_INTERVAL_S = 60  #!< Default polling interval when update timing is unknown
    INVALID_VALUE = -999.0  #!< Sentinel value indicating missing or invalid measurement
    MISSING_UNIT = ["///", "???"]  #!< Unit string values that indicate missing data


class ConversionType(enum.Enum):
    """Enumeration of numeric conversion types for sensor values.

    @details Used by @ref WeatherStation.get_value to specify output data type.
    """
    TO_INT = 1  #!< Convert sensor value to integer
    TO_FLOAT = 2  #!< Convert sensor value to floating-point number


class Formats:
    """DateTime format strings for display and parsing.

    Defines standard format patterns used throughout the application for parsing
    and formatting timestamps and time values.
    """
    SHORT_TIME_FORMAT = "%H:%M"  #!< Display format: hour:minute (e.g., "14:30")
    TIME_FORMAT = "%H:%M:%S"  #!< Display format: hour:minute:second (e.g., "14:30:45")
    DATE_TIME_FORMAT = "%d.%m.%Y %H:%M"  #!< Display format: Finnish date and time (e.g., "13.05.2026 14:30")
    UTC_TIMESTAMP_FORMAT = "%Y-%m-%dT%H:%M:%SZ"  #!< ISO 8601 UTC format for parsing API responses


class Urls:
    """API endpoint templates for weather data providers.

    Contains URL templates for FMI (Finnish Meteorological Institute) and OpenWeatherMap
    APIs. URL templates with {} placeholders are formatted with query parameters at runtime.

    @details
    - FMI endpoints return GeoJSON-formatted weather station and measurement data
    - OpenWeatherMap endpoints require API key authentication (appid parameter)
    - All endpoints return JSON responses
    """
    OPENWEATHERMAP_CITY_URL = (
        "https://api.openweathermap.org/data/2.5/weather?q={}&appid={}"
    )  #!< Current weather by city name. Args: city name, API key
    OPENWEATHERMAP_LOCATION_URL = (
        "https://api.openweathermap.org/data/2.5/weather?lat={}&lon={}&appid={}"
    )  #!< Current weather by coordinates. Args: latitude, longitude, API key
    OPENWEATHERMAP_FORECAST_URL = (
        "https://api.openweathermap.org/data/2.5/forecast?lat={}&lon={}&appid={}"
    )  #!< 5-day forecast (all 3-hour periods). Args: latitude, longitude, API key
    STATION_LIST_URL = "https://tie.digitraffic.fi/api/weather/v1/stations"  #!< FMI station list with metadata and coordinates
    WEATHER_STATION_URL = "https://tie.digitraffic.fi/api/weather/v1/stations/{}/data"  #!< FMI station observations. Args: station ID
