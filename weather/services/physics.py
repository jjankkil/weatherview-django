from .definitions import Constants


def fmi_feels_like_temperature(wind: float, rh: float, temp: float) -> float:
    """FMI apparent temperature combining wind chill and summer simmer index."""
    try:
        if temp <= 10.0:
            feels_like = (
                13.12
                + 0.6215 * temp
                - 11.37 * (wind ** 0.16)
                + 0.3965 * temp * (wind ** 0.16)
            )
        else:
            feels_like = temp - _fmi_summer_simmer_index(rh, temp)
        return round(feels_like, 1)
    except Exception:
        return Constants.INVALID_VALUE


def _fmi_summer_simmer_index(rh: float, temp: float) -> float:
    return (
        -8.784695
        + 1.61139411 * temp
        + 2.338549 * (rh / 100)
        - 0.14611605 * temp * (rh / 100)
        - 0.012308094 * (temp ** 2)
        - 0.016424828 * ((rh / 100) ** 2)
        + 0.002211732 * (temp ** 2) * (rh / 100)
        + 0.00072546 * temp * ((rh / 100) ** 2)
        - 0.000003582 * (temp ** 2) * ((rh / 100) ** 2)
    )
