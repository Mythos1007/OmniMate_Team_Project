from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(slots=True)
class Settings:
    host: str = "0.0.0.0"
    port: int = 8090
    cors_origins: list[str] = None  # type: ignore[assignment]
    ws_push_interval_sec: float = 0.5
    lat: float = 37.3886
    lon: float = 126.6424

    def __post_init__(self) -> None:
        if self.cors_origins is None:
            self.cors_origins = ["*"]


def _parse_origins(raw: str) -> list[str]:
    tokens = [part.strip() for part in raw.split(",") if part.strip()]
    return tokens or ["*"]


def load_settings() -> Settings:
    return Settings(
        host=os.getenv("ASSISTANT_WEB_HOST", "0.0.0.0"),
        port=int(os.getenv("ASSISTANT_WEB_PORT", "8090")),
        cors_origins=_parse_origins(os.getenv("ASSISTANT_WEB_CORS", "*")),
        ws_push_interval_sec=float(os.getenv("ASSISTANT_WEB_WS_INTERVAL", "0.5")),
        lat=float(os.getenv("ASSISTANT_WEATHER_LAT", "37.3886")),
        lon=float(os.getenv("ASSISTANT_WEATHER_LON", "126.6424")),
    )
