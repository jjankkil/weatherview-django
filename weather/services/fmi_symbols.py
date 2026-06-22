"""FMI WeatherSymbol3 to emoji mapping for UI display.

Maps integer codes from the FMI open data `WeatherSymbol3` parameter (used in
FMI WFS forecast products) to Unicode emoji symbols for display in the weather
forecast carousel.

@author Jari Jankkila
@date 2026
@version 1.0
"""

_SYMBOL_MAP: dict[int, str] = {
    1:  "☀",   # Clear sky
    2:  "⛅",  # Partly cloudy
    3:  "☁",   # Cloudy
    21: "🌦",  # Light rain showers
    22: "🌧",  # Rain showers
    23: "🌧",  # Heavy rain showers
    31: "🌦",  # Light rain
    32: "🌧",  # Rain
    33: "🌧",  # Heavy rain
    41: "🌨",  # Light snow showers
    42: "❄",   # Snow showers
    43: "❄",   # Heavy snow showers
    51: "🌨",  # Light snow
    52: "❄",   # Snow
    53: "❄",   # Heavy snow
    61: "⛈",  # Thunderstorm
    62: "⛈",  # Heavy thunderstorm
    63: "⛈",  # Thunderstorm with hail
    71: "🌧",  # Light sleet showers
    72: "🌧",  # Sleet showers
    73: "🌧",  # Heavy sleet showers
    81: "🌧",  # Light sleet
    82: "🌧",  # Sleet
    83: "❄",   # Heavy sleet
    91: "🌫",  # Fog
    92: "🌫",  # Dense fog
}


def get_fmi_weather_symbol(code) -> str:
    """Map an FMI WeatherSymbol3 code to a Unicode emoji symbol.

    FMI WeatherSymbol3 codes are integers 1–99 (daytime) used in FMI forecast
    products. Night-time variants (100+) are not produced when using a daily
    timestep anchored at noon UTC.

    @param code Integer (or float/string) weather symbol code from the FMI
               forecast API. Values that cannot be converted to int return "".
    @return Unicode emoji representing the weather condition, or empty string
            for unknown or unparseable codes.
    @details
    - 1: Clear → ☀
    - 2: Partly cloudy → ⛅
    - 3: Cloudy → ☁
    - 21–23: Rain showers (light/moderate/heavy) → 🌦/🌧
    - 31–33: Rain (light/moderate/heavy) → 🌦/🌧
    - 41–43: Snow showers (light/moderate/heavy) → 🌨/❄
    - 51–53: Snow (light/moderate/heavy) → 🌨/❄
    - 61–63: Thunderstorm → ⛈
    - 71–73, 81–83: Sleet showers / sleet → 🌧/❄
    - 91–92: Fog / dense fog → 🌫
    """
    try:
        return _SYMBOL_MAP.get(int(float(code)), "")
    except (TypeError, ValueError):
        return ""
