"""Station information and coordinate data structures for FMI weather stations.

Defines classes for representing weather station metadata, geographic coordinates,
station lists, and filtering logic for weather station collections.

@author Jari Jankkila
@date 2026
@version 1.0
"""

from .helpers import ok_to_add_station
from .ui_helpers import format_station_name


class Coordinates:
    """Geographic coordinate representation with latitude, longitude, and altitude."""
    def __init__(self, lat=0.0, lon=0.0, alt=0.0):
        """Initialize a geographic coordinate.

        @param lat Latitude in degrees (WGS84 projection). Default: 0.0
        @param lon Longitude in degrees (WGS84 projection). Default: 0.0
        @param alt Altitude in meters above sea level. Default: 0.0
        """
        self.latitude = lat  #!< Latitude coordinate in degrees
        self.longitude = lon  #!< Longitude coordinate in degrees
        self.altitude = alt  #!< Altitude in meters


class WeatherStationInfo:
    """Metadata and geographic information for a single FMI weather station.

    Represents a weather station from the FMI station list, including unique identifier,
    raw and formatted names, and geographic coordinates. Parses GeoJSON feature format
    from the FMI station list API.
    """
    def __init__(self):
        """Initialize an empty WeatherStationInfo object."""
        self.id = 0  #!< Unique FMI station identifier
        self.name = ""  #!< Raw station name from FMI (e.g., "CODE_City_Region")
        self.coordinates = Coordinates()  #!< Geographic location (lat, lon, alt)
        self._formatted_name = ""  #!< Cached formatted name (lazy-loaded)

    def parse(self, station_json: dict) -> bool:
        """Parse FMI GeoJSON feature object into station metadata.

        Extracts station information from a GeoJSON feature as returned by the FMI
        station list endpoint. Expected structure: GeoJSON feature with properties
        and geometry (Point with [lon, lat, alt] coordinates).

        @param station_json GeoJSON feature object from FMI API response.
        @return True if parsing succeeded, False if required keys are missing or malformed.
        @details
        - Expects GeoJSON Point geometry with [longitude, latitude, altitude] order
        - Requires "id" and "properties.name" keys in the feature
        - Coordinate order (lon, lat) is reversed to (lat, lon) in Coordinates object
        - Gracefully handles missing fields by returning False without throwing
        """
        try:
            coords = station_json["geometry"]["coordinates"]
            self.coordinates = Coordinates(lat=coords[1], lon=coords[0], alt=coords[2])
            self.id = station_json["id"]
            self.name = station_json["properties"]["name"]
            return True
        except Exception:
            return False

    @property
    def formatted_name(self) -> str:
        """Get the formatted station name (cached after first access).

        Lazily formats the raw station name on first access and caches the result
        for subsequent accesses. Uses @ref format_station_name for formatting logic.

        @return Formatted station name suitable for display (e.g., "City, Region CODE").
        """
        if not self._formatted_name:
            self._formatted_name = format_station_name(self.name)
        return self._formatted_name

    def to_dict(self) -> dict:
        """Convert station information to dictionary representation.

        Creates a dictionary containing all public station information suitable for
        serialization or API responses.

        @return Dictionary with keys: id, name, formatted_name, lat, lon
        """
        return {
            "id": self.id,
            "name": self.name,
            "formatted_name": self.formatted_name,
            "lat": self.coordinates.latitude,
            "lon": self.coordinates.longitude,
        }


class WeatherStationList:
    """Collection of FMI weather stations with search and filter operations.

    Manages a collection of WeatherStationInfo objects parsed from FMI API responses.
    Provides sorted access, search by ID/name, and filtering of public stations.
    """
    def __init__(self):
        """Initialize an empty weather station list."""
        self._stations: list[WeatherStationInfo] = []  #!< List of weather stations

    def parse(self, station_list_json: list) -> bool:
        """Parse a list of GeoJSON features into weather station objects.

        Parses FMI station list GeoJSON response (array of features) into
        WeatherStationInfo objects. Silently skips any features that fail to parse.

        @param station_list_json Array of GeoJSON feature objects from FMI station list API.
        @return True after parsing completes (even if all features failed to parse).
        @details
        - Clears existing stations before parsing new data
        - Features that fail to parse are silently skipped
        - Returns True regardless of parse results (always succeeds in structure)
        """
        self._stations.clear()
        for item in station_list_json:
            info = WeatherStationInfo()
            if info.parse(item):
                self._stations.append(info)
        return True

    def sort_by_name(self):
        """Sort the station list alphabetically by formatted station name.

        Modifies the list in-place to sort stations alphabetically by their
        formatted display names for consistent UI presentation.
        """
        self._stations.sort(key=lambda s: s.formatted_name)

    def find_by_id(self, station_id: int):
        """Find a station by its unique FMI identifier.

        Performs a linear search for the station with the given ID.

        @param station_id The FMI station identifier to search for.
        @return WeatherStationInfo object if found, None if not present in the list.
        """
        for s in self._stations:
            if s.id == station_id:
                return s
        return None

    def find_by_name(self, name: str):
        """Find a station by its formatted display name.

        Performs a linear search for the station with the given formatted name.

        @param name The formatted station name to search for (e.g., "City, Region CODE").
        @return WeatherStationInfo object if found, None if not present in the list.
        """
        for s in self._stations:
            if s.formatted_name == name:
                return s
        return None

    def get_name_list(self) -> list[dict]:
        """Get list of public stations as dictionary representations.

        Returns station information for all non-filtered stations (public stations).
        Uses @ref ok_to_add_station to filter out test and special-purpose stations.

        @return Array of station dictionaries (from @ref WeatherStationInfo.to_dict)
                containing only stations that pass the public filter.
        """
        return [
            s.to_dict()
            for s in self._stations
            if ok_to_add_station(s.name)
        ]
