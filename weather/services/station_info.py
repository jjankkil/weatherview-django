from .helpers import ok_to_add_station
from .ui_helpers import format_station_name


class Coordinates:
    def __init__(self, lat=0.0, lon=0.0, alt=0.0):
        self.latitude = lat
        self.longitude = lon
        self.altitude = alt


class WeatherStationInfo:
    def __init__(self):
        self.id = 0
        self.name = ""
        self.coordinates = Coordinates()
        self._formatted_name = ""

    def parse(self, station_json: dict) -> bool:
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
        if not self._formatted_name:
            self._formatted_name = format_station_name(self.name)
        return self._formatted_name

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "formatted_name": self.formatted_name,
            "lat": self.coordinates.latitude,
            "lon": self.coordinates.longitude,
        }


class WeatherStationList:
    def __init__(self):
        self._stations: list[WeatherStationInfo] = []

    def parse(self, station_list_json: list) -> bool:
        self._stations.clear()
        for item in station_list_json:
            info = WeatherStationInfo()
            if info.parse(item):
                self._stations.append(info)
        return True

    def sort_by_name(self):
        self._stations.sort(key=lambda s: s.formatted_name)

    def find_by_id(self, station_id: int):
        for s in self._stations:
            if s.id == station_id:
                return s
        return None

    def find_by_name(self, name: str):
        for s in self._stations:
            if s.formatted_name == name:
                return s
        return None

    def get_name_list(self) -> list[dict]:
        return [
            s.to_dict()
            for s in self._stations
            if ok_to_add_station(s.name)
        ]
