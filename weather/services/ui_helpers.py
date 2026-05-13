"""User interface helper functions for weather display formatting.

Provides utility functions for formatting weather data for presentation including
weather symbol mapping, wind direction translation, and station name parsing.

@author Jari Jankkila
@date 2026
@version 1.0
"""


def get_station_city(formatted_name: str) -> str:
    """Extract city name from a formatted station name.

    Parses a formatted station name (expected format: "City, Region") to extract
    and return only the city portion (before the comma).

    @param formatted_name The formatted station name from @ref WeatherStationInfo.formatted_name.
    @return The city name (text before the first comma), or empty string if no comma is present.
    @details
    - Expects input format: "City, Region Code" or "City, Details"
    - Returns the entire input if no comma is found
    - Returns empty string if input is None or empty
    """
    if formatted_name and "," in formatted_name:
        return formatted_name.split(",")[0]
    return ""


def get_weather_symbol(weather_id: int) -> str:
    """Map OpenWeatherMap weather condition ID to a Unicode emoji symbol.

    Converts OpenWeatherMap API weather condition codes (200-804) into human-readable
    Unicode weather emoji symbols for display in the user interface.

    @param weather_id The weather condition ID from OpenWeatherMap API.
    @return Unicode emoji symbol representing the weather condition, or empty string if unmapped.
    @details
    - IDs 200-232: Thunderstorm conditions → ⛈ (thunder cloud)
    - IDs 300-321: Drizzle conditions → 🌦 (cloud with rain)
    - IDs 500-531: Rain conditions → 🌧 (cloud with heavy rain)
    - IDs 600-622: Snow conditions → ❄ (snowflake)
    - IDs 701-741: Mist/fog conditions → 🌫 (fog)
    - ID 762: Volcanic ash → 🌋 (volcano)
    - ID 771: Squall/wind → 💨 (wind)
    - ID 781: Tornado → 🌪 (tornado)
    - ID 800: Clear/sunny → ☀ (sun)
    - IDs 801-804: Cloudy conditions → ☁ (cloud)
    - Other IDs: No mapping available → empty string
    """
    if 200 <= weather_id <= 232:
        return "⛈"
    elif 300 <= weather_id <= 321:
        return "🌦"
    elif 500 <= weather_id <= 531:
        return "🌧"
    elif 600 <= weather_id <= 622:
        return "❄"
    elif 701 <= weather_id <= 741:
        return "🌫"
    elif weather_id == 762:
        return "🌋"
    elif weather_id == 771:
        return "💨"
    elif weather_id == 781:
        return "🌪"
    elif weather_id == 800:
        return "☀"
    elif 801 <= weather_id <= 804:
        return "☁"
    return ""


def wind_direction_as_text(degrees, lang="fi") -> str:
    """Convert wind direction degrees to human-readable cardinal direction text.

    Maps a numeric compass heading (0-360 degrees, where 0°=N, 90°=E, 180°=S, 270°=W)
    to the eight primary cardinal directions and translates to the specified language.

    @param degrees Wind direction in degrees (0-360). None or negative values return empty string.
    @param lang Language code for translation: "en" for English, any other value defaults to Finnish ("fi").
    @return Localized cardinal direction text (e.g., "from North", "pohjoisesta"), or empty string if input is None.
    @details
    - Degrees greater than 360 are normalized by subtracting 360 (handles multiple rotations)
    - Each of 8 cardinal directions spans 45° (±22.5° centered on cardinal point):
      - N: 337.5°-22.5°, NE: 22.5°-67.5°, E: 67.5°-112.5°, SE: 112.5°-157.5°,
      - S: 157.5°-202.5°, SW: 202.5°-247.5°, W: 247.5°-292.5°, NW: 292.5°-337.5°
    - Finnish output uses "from" phrases (e.g., "pohjoisesta" = "from North")
    - English output explicitly includes "from" prefix
    """
    if degrees is None:
        return ""

    while degrees > 360:
        degrees -= 360.0

    fi = {
        "NE": "koillisesta", "E": "idästä", "SE": "kaakosta",
        "S": "etelästä", "SW": "lounaasta", "W": "lännestä",
        "NW": "luoteesta", "N": "pohjoisesta",
    }
    en = {
        "NE": "from NE", "E": "from E", "SE": "from SE",
        "S": "from S", "SW": "from SW", "W": "from W",
        "NW": "from NW", "N": "from N",
    }
    labels = en if lang == "en" else fi

    if 22.5 <= degrees < 67.5:
        key = "NE"
    elif 67.5 <= degrees < 112.5:
        key = "E"
    elif 112.5 <= degrees < 157.5:
        key = "SE"
    elif 157.5 <= degrees < 202.5:
        key = "S"
    elif 202.5 <= degrees < 247.5:
        key = "SW"
    elif 247.5 <= degrees < 292.5:
        key = "W"
    elif 292.5 <= degrees < 337.5:
        key = "NW"
    else:
        key = "N"

    return labels[key]


def format_station_name(raw_name: str) -> str:
    """Format a raw FMI station name into a human-readable display format.

    Parses underscore-delimited FMI station names and reorganizes tokens to create
    a formatted name with city and regional information in a consistent format.

    @param raw_name The raw station name from FMI API (e.g., "CODE_City_Region_Details").
    @return Formatted station name suitable for display (e.g., "City, Region CODE" or "City, Region CODE Details"),
            or the input unchanged if it has fewer than 2 tokens.
    @details
    - Expected input format: underscore-delimited tokens with: CODE_City_Region[_Details...]
    - Output format depends on token count:
      - 2 tokens: "City, CODE" (e.g., "Helsinki, KEHÄ")
      - 3 tokens: "City, Region CODE" (e.g., "Helsinki, Vantaa KPA")
      - 4+ tokens: "City, Region CODE Details..." (e.g., "Helsinki, Vantaa KPA Additional")
    - Returns input unchanged if None, empty, or single-token
    - Reorganizes tokens to prioritize city name, then region, then code
    """
    if not raw_name:
        return ""
    tokens = raw_name.split("_")
    n = len(tokens)
    if n > 3:
        return f"{tokens[1]}, {tokens[2]} {tokens[0]} {tokens[3]}"
    elif n == 3:
        return f"{tokens[1]}, {tokens[2]} {tokens[0]}"
    elif n == 2:
        return f"{tokens[1]}, {tokens[0]}"
    return raw_name
