#!/usr/bin/env python3
"""Minimal HTTP server that mimics the Digitraffic road-weather API for E2E tests.

Serves the same three endpoints WeatherService calls (see
weather/services/definitions.py Urls.STATION_LIST_URL / WEATHER_STATION_URL /
WEATHER_STATION_HISTORY_URL), using the raw Digitraffic response shapes
(GeoJSON station list, sensorValues observation payload, sensor-history
values). Timestamps are generated fresh per request so
seconds_until_next_update / the history bucketing window stay valid however
long the test run takes.

Point the Django app at this server via WVD_DIGITRAFFIC_BASE_URL=http://127.0.0.1:<port>.

Usage: python3 fixture_server.py <port>
"""

import datetime
import json
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse

_STATIONS = [
    {
        "id": 1001,
        "properties": {"name": "FIX1_Helsinki_Pasila"},
        "geometry": {"type": "Point", "coordinates": [24.932, 60.198, 10.0]},
    },
    {
        "id": 1002,
        "properties": {"name": "FIX2_Tampere_Keskusta"},
        "geometry": {"type": "Point", "coordinates": [23.763, 61.497, 100.0]},
    },
]

_STATION_SENSORS = {
    1001: {
        "ILMA": (-2.5, "C"),
        "KESKITUULI": (3.2, "m/s"),
        "MAKSIMITUULI": (5.0, "m/s"),
        "TUULENSUUNTA": (0, "deg"),
        "ILMAN_KOSTEUS": (78, "%"),
        "KASTEPISTE": (-5.8, "C"),
        "TIE_1": (-3.0, "C"),
    },
    1002: {
        "ILMA": (5.0, "C"),
        "KESKITUULI": (2.0, "m/s"),
        "MAKSIMITUULI": (4.0, "m/s"),
        "TUULENSUUNTA": (90, "deg"),
        "ILMAN_KOSTEUS": (65, "%"),
        "KASTEPISTE": (1.0, "C"),
        "TIE_1": (4.0, "C"),
    },
}

_UTC_FMT = "%Y-%m-%dT%H:%M:%SZ"


def _now_str():
    return datetime.datetime.now(datetime.timezone.utc).strftime(_UTC_FMT)


def _station_data_payload(station_id):
    sensors = _STATION_SENSORS.get(station_id, {})
    sensor_values = [
        {
            "id": idx,
            "stationId": station_id,
            "name": name,
            "shortName": name,
            "measuredTime": _now_str(),
            "value": value,
            "unit": unit,
        }
        for idx, (name, (value, unit)) in enumerate(sensors.items(), start=1)
    ]
    return {"dataUpdatedTime": _now_str(), "sensorValues": sensor_values}


def _history_payload(station_id):
    now = datetime.datetime.now(datetime.timezone.utc)
    temp_base = _STATION_SENSORS.get(station_id, {}).get("ILMA", (0.0, "C"))[0]
    values = []
    for minutes_ago in (0, 10, 20, 30):
        t = now - datetime.timedelta(minutes=minutes_ago)
        values.append({"id": 1, "value": temp_base, "measuredTime": t.strftime(_UTC_FMT)})
    values.append({"id": 23, "value": 0.0, "measuredTime": now.strftime(_UTC_FMT)})
    return {"values": values}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # keep test output quiet; Robot's Process output captures stdout/stderr separately

    def _send_json(self, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urlparse(self.path).path
        parts = [p for p in path.split("/") if p]
        # /stations
        if parts == ["stations"]:
            self._send_json({"features": _STATIONS})
            return
        # /stations/{id}/data
        if len(parts) == 3 and parts[0] == "stations" and parts[2] == "data":
            self._send_json(_station_data_payload(int(parts[1])))
            return
        # /stations/{id}/data/history
        if len(parts) == 4 and parts[0] == "stations" and parts[2:] == ["data", "history"]:
            self._send_json(_history_payload(int(parts[1])))
            return
        self.send_response(404)
        self.end_headers()


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 18766
    HTTPServer(("127.0.0.1", port), Handler).serve_forever()
