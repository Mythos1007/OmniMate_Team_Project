from __future__ import annotations

import json
import os
from pathlib import Path

import requests


class WeatherService:
    def __init__(self, lat: float, lon: float) -> None:
        self.lat = lat
        self.lon = lon

    @staticmethod
    def _resolve_secrets_file_path() -> Path:
        configured = os.getenv("ASSISTANT_WEATHER_SECRETS_FILE", "").strip()
        if configured:
            return Path(configured).expanduser()
        shared_configured = os.getenv("ASSISTANT_SECRETS_FILE", "").strip()
        if shared_configured:
            return Path(shared_configured).expanduser()
        return Path.home() / ".config" / "assistant" / "secrets.json"

    @classmethod
    def load_weather_api_key(cls) -> str:
        env_key = os.getenv("ASSISTANT_WEATHER_API_KEY", "").strip()
        if env_key:
            return env_key

        path = cls._resolve_secrets_file_path()
        if not path.exists():
            return ""
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return ""
        if not isinstance(loaded, dict):
            return ""
        return str(loaded.get("weather_api_key", "")).strip()

    def get_now(self) -> tuple[float | None, str, str]:
        # Open-Meteo is keyless and works well for local-network web fallback.
        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": self.lat,
            "longitude": self.lon,
            "current": "temperature_2m,weather_code",
            "timezone": "Asia/Seoul",
        }
        try:
            res = requests.get(url, params=params, timeout=8)
            res.raise_for_status()
            data = res.json()
            current = data.get("current", {})
            temp = current.get("temperature_2m")
            code = int(current.get("weather_code", -1))
            return float(temp) if temp is not None else None, *self._decode_code(code)
        except Exception:
            return self._get_now_from_wttr()

    def _get_now_from_wttr(self) -> tuple[float | None, str, str]:
        try:
            res = requests.get("https://wttr.in/?format=j1", timeout=8)
            res.raise_for_status()
            data = res.json()
            current_list = data.get("current_condition") or []
            if not current_list:
                raise ValueError("missing current_condition")

            current = current_list[0]
            temp_raw = current.get("temp_C")
            temp = float(temp_raw) if temp_raw not in (None, "") else None
            desc_values = current.get("weatherDesc") or []
            desc = str(desc_values[0].get("value", "Weather unavailable")) if desc_values else "Weather unavailable"
            return temp, desc, self._icon_from_description(desc)
        except Exception:
            return None, "Weather unavailable", "?"

    @staticmethod
    def _icon_from_description(description: str) -> str:
        desc = str(description).lower()
        if "thunder" in desc or "storm" in desc:
            return "storm"
        if "snow" in desc or "sleet" in desc:
            return "snow"
        if "rain" in desc or "drizzle" in desc or "shower" in desc:
            return "rain"
        if "fog" in desc or "mist" in desc or "haze" in desc:
            return "fog"
        if "clear" in desc or "sun" in desc:
            return "sun"
        return "cloud"

    @staticmethod
    def _decode_code(code: int) -> tuple[str, str]:
        mapping = {
            0: ("Clear", "sun"),
            1: ("Mostly clear", "sun"),
            2: ("Partly cloudy", "cloud"),
            3: ("Overcast", "cloud"),
            45: ("Fog", "fog"),
            48: ("Rime fog", "fog"),
            51: ("Drizzle", "rain"),
            61: ("Rain", "rain"),
            71: ("Snow", "snow"),
            95: ("Thunderstorm", "storm"),
        }
        return mapping.get(code, ("Unknown", "cloud"))
