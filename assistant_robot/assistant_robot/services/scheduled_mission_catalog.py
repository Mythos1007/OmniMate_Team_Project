from __future__ import annotations

from importlib.resources import files
from pathlib import Path
from typing import Any

import yaml


class ScheduledMissionCatalog:
    def __init__(self, config_path: str | Path | None = None) -> None:
        self._config_path = Path(config_path).expanduser().resolve() if config_path else None

    def load_entries(self) -> list[dict[str, Any]]:
        config_path = self._config_path or Path(files("assistant_robot.config").joinpath("scheduled_missions.yaml"))
        loaded = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        if not isinstance(loaded, dict):
            return []
        entries = loaded.get("scheduled_missions", [])
        if not isinstance(entries, list):
            return []
        normalized: list[dict[str, Any]] = []
        for item in entries:
            if not isinstance(item, dict):
                continue
            normalized.append({str(key): value for key, value in item.items()})
        return normalized
