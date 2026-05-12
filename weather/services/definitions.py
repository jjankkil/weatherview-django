import enum


class Constants:
    FORECAST_CNT = 3
    STATION_UPDATE_DELAY_S = 60
    DEFAULT_POLLING_INTERVAL_S = 60
    INVALID_VALUE = -999.0
    MISSING_UNIT = ["///", "???"]


class ConversionType(enum.Enum):
    TO_INT = 1
    TO_FLOAT = 2


class Formats:
    SHORT_TIME_FORMAT = "%H:%M"
    TIME_FORMAT = "%H:%M:%S"
    DATE_TIME_FORMAT = "%d.%m.%Y %H:%M"
    UTC_TIMESTAMP_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


class Urls:
    OPENWEATHERMAP_CITY_URL = (
        "https://api.openweathermap.org/data/2.5/weather?q={}&appid={}"
    )
    OPENWEATHERMAP_LOCATION_URL = (
        "https://api.openweathermap.org/data/2.5/weather?lat={}&lon={}&appid={}"
    )
    OPENWEATHERMAP_FORECAST_URL = (
        "https://api.openweathermap.org/data/2.5/forecast?cnt=8&lat={}&lon={}&appid={}"
    )
    STATION_LIST_URL = "https://tie.digitraffic.fi/api/weather/v1/stations"
    WEATHER_STATION_URL = "https://tie.digitraffic.fi/api/weather/v1/stations/{}/data"
