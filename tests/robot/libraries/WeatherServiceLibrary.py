"""Robot Framework keyword library wrapping weather/services/* pure functions.

Lets .robot files exercise side-effect-free business logic directly (no HTTP,
no Django server) — e.g. temperature/wind_speed/humidity -> feels-like, or
wind degrees -> localized compass text.
"""

import os
import sys
from pathlib import Path

_PROJECT_ROOT = str(Path(__file__).resolve().parents[3])
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "weatherview_project.settings")
os.environ.setdefault("WVD_SECRET_KEY", "robot-test-key-DO-NOT-USE-IN-PROD")

import django

django.setup()

from weather.services.physics import fmi_feels_like_temperature
from weather.services.ui_helpers import wind_direction_as_text


class WeatherServiceLibrary:
    def compute_feels_like(self, wind: float, rh: float, temp: float) -> float:
        return fmi_feels_like_temperature(float(wind), float(rh), float(temp))

    def wind_degrees_to_text(self, degrees, lang: str = "fi") -> str:
        return wind_direction_as_text(None if degrees is None else float(degrees), lang)
