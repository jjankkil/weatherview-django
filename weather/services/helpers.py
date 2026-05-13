"""Helper functions for weather station filtering and validation.

Provides utilities for filtering out test, special-purpose, and invalid weather station
entries from the FMI station list.

@author Jari Jankkila
@date 2026
@version 1.0
"""

_FILTERED = {"Test", "LA", "TSA", "TEST", "Meteo", "LAMID", "OptX"}  #!< Station name tokens indicating test or non-public stations


def ok_to_add_station(raw_name: str) -> bool:
    """Check if a station should be included in the public weather station list.

    Filters out test stations, special-purpose installations, and other stations
    that should not be displayed to end users. Uses token-based filtering on the
    station name.

    @param raw_name The raw station name from FMI data.
    @return True if the station should be included, False if it matches a filter token.
    @details
    - Returns False if raw_name is empty or None
    - Returns False if raw_name contains any of the tokens in _FILTERED (case-sensitive)
    - Returns True only if the name passes all filters
    """
    if not raw_name:
        return False
    for token in _FILTERED:
        if token in raw_name:
            return False
    return True
