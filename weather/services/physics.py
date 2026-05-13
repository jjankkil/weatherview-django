import math

from .definitions import Constants


def fmi_feels_like_temperature(wind, rh, temp) -> float:
    """Compute a feels-like temperature combining wind chill and summer simmer index.

    Returns `Constants.INVALID_VALUE` when inputs are invalid or calculation fails.
    """
    if (
        wind == Constants.INVALID_VALUE
        or rh == Constants.INVALID_VALUE
        or temp == Constants.INVALID_VALUE
    ):
        return Constants.INVALID_VALUE

    try:
        a = 15.0
        t0 = 37.0
        chill = (
            a
            + (1.0 - a / t0) * temp
            + a / t0 * math.pow(wind + 1.0, 0.16) * (temp - t0)
        )

        heat = __fmi_summer_simmer_index(rh, temp)
        if heat == Constants.INVALID_VALUE:
            return Constants.INVALID_VALUE

        feels_like = temp + (chill - temp) + (heat - temp)
        return feels_like

    except Exception:
        return Constants.INVALID_VALUE


def __fmi_summer_simmer_index(rh: float, temp: float) -> float:
    """Internal helper for the summer/simmer index used in feels-like calculation."""
    simmer_limit = 14.5

    try:
        if temp <= simmer_limit:
            return temp

        RH_REF = 50.0 / 100.0
        r = rh / 100.0
        result = (
            1.8 * temp
            - 0.55 * (1.0 - r) * (1.8 * temp - 26.0)
            - 0.55 * (1.0 - RH_REF) * 26.0
        ) / (1.8 * (1.0 - 0.55 * (1.0 - RH_REF)))
        return result

    except Exception:
        return Constants.INVALID_VALUE
