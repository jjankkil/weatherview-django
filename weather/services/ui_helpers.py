def get_station_city(formatted_name: str) -> str:
    if formatted_name and "," in formatted_name:
        return formatted_name.split(",")[0]
    return ""


def get_weather_symbol(weather_id: int) -> str:
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
