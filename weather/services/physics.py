"""Physics calculations module for weather-related computations.

Provides functions for calculating perception-adjusted temperature metrics including
wind chill effect and humidity-based heat perception (summer simmer index). These
calculations are based on FMI (Finnish Meteorological Institute) models.

@author Jari Jankkila
@date 2026
@version 1.0
"""

import math

from .definitions import Constants


def fmi_feels_like_temperature(wind, rh, temp) -> float:
    """Compute a feels-like temperature combining wind chill and summer simmer index.

    Calculates the perceived temperature by combining two effects: wind chill in cold
    conditions and humidity-related heat perception in warm conditions. Returns the
    FMI model's combined perception-adjusted temperature.

    @param wind Wind speed in m/s. Use Constants.INVALID_VALUE for missing data.
    @param rh Relative humidity as a percentage (0-100). Use Constants.INVALID_VALUE for missing data.
    @param temp Air temperature in Celsius. Use Constants.INVALID_VALUE for missing data.
    @return Perceived temperature in Celsius, or Constants.INVALID_VALUE if inputs are invalid or calculation fails.
    @details
    - Wind chill component is calculated using the FMI formula when wind is present
    - Heat perception (summer simmer) is applied when temperature exceeds 14.5°C
    - The final feels-like temperature combines both effects with the base temperature
    - All input parameters must be valid (not Constants.INVALID_VALUE) for computation
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
    """Calculate the FMI summer/simmer index for humidity-adjusted heat perception.

    Internal helper function that applies relative humidity correction to temperature
    in warm conditions. Only applies adjustment when temperature exceeds 14.5°C;
    below that threshold, returns the input temperature unchanged.

    @param rh Relative humidity as a percentage (0-100).
    @param temp Air temperature in Celsius.
    @return Humidity-adjusted temperature in Celsius, or Constants.INVALID_VALUE on calculation error.
    @details
    - Used internally by @ref fmi_feels_like_temperature only
    - Temperature threshold of 14.5°C matches FMI model specification
    - Formula normalizes against a reference humidity of 50%
    - Returns input temperature if below threshold (no summer effect)
    """
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
