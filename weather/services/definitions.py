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
    STATION_UPDATE_DELAY_S = 60  #!< Delay in seconds before checking for new station data
    DEFAULT_DATA_REFRESH_INTERVAL_S = 300  #!< Default weather data refresh interval at a station when update timing is unknown (5 min)
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

    Contains URL templates for the Digitraffic road weather station API and the
    FMI WFS open data forecast API. All endpoints are freely accessible without
    authentication. URL templates with {} placeholders are formatted with query
    parameters at runtime.

    @details
    - Digitraffic endpoints return GeoJSON-formatted station data (JSON)
    - FMI WFS forecast endpoint returns XML (GML/WFS 2.0 simple feature format)
    """
    STATION_LIST_URL = "https://tie.digitraffic.fi/api/weather/v1/stations"  #!< Digitraffic road weather station list with metadata and coordinates
    WEATHER_STATION_URL = "https://tie.digitraffic.fi/api/weather/v1/stations/{}/data"  #!< Digitraffic station observations. Args: station ID
    WEATHER_STATION_HISTORY_URL = "https://tie.digitraffic.fi/api/weather/v1/stations/{}/data/history"  #!< Digitraffic station sensor value history (max 24h). Args: station ID
    FMI_FORECAST_HOURLY_URL = (
        "https://opendata.fmi.fi/wfs/eng?service=WFS&version=2.0.0&request=getFeature"
        "&storedquery_id=fmi::forecast::edited::weather::scandinavia::point::simple"
        "&latlon={},{}&timestep=60&starttime={}&endtime={}&parameters=Temperature,WeatherSymbol3"
    )  #!< FMI edited Scandinavia hourly point forecast (XML); sampled at 60-min steps so today's 3-hour display slots can report their peak. Args: latitude, longitude, starttime (ISO 8601 UTC), endtime (ISO 8601 UTC)
    FMI_FORECAST_DAILY_URL = (
        "https://opendata.fmi.fi/wfs/eng?service=WFS&version=2.0.0&request=getFeature"
        "&storedquery_id=fmi::forecast::edited::weather::scandinavia::point::simple"
        "&latlon={},{}&timestep=60&starttime={}&endtime={}&parameters=Temperature,WeatherSymbol3"
    )  #!< FMI edited Scandinavia hourly point forecast (XML); sampled at 60-min steps and aggregated to a per-local-day maximum. Args: latitude, longitude, starttime (ISO 8601 UTC), endtime (ISO 8601 UTC)
