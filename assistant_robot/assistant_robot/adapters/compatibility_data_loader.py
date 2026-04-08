from __future__ import annotations

import ast
from functools import lru_cache
from pathlib import Path
from typing import Any

from assistant_robot.services.place_catalog import PlaceCatalog
from assistant_robot.services.scheduled_mission_catalog import ScheduledMissionCatalog


class CompatibilityDataLoader:
    """Load packaged data first and fall back to legacy workspace files if needed."""

    def __init__(self, legacy_dir: str | Path | None = None) -> None:
        self._legacy_dir = self._resolve_legacy_dir(legacy_dir)
        self._place_catalog = PlaceCatalog()
        self._schedule_catalog = ScheduledMissionCatalog()

    @property
    def legacy_dir(self) -> Path | None:
        return self._legacy_dir

    def load_waypoints(self) -> dict[str, dict[str, Any]]:
        packaged = self._place_catalog.places_by_source("waypoints")
        if packaged:
            return packaged
        loaded = self._load_literal_assignments("waypoints.py", frozenset({"WAYPOINTS"}))
        waypoints = loaded.get("WAYPOINTS", {})
        return waypoints if isinstance(waypoints, dict) else {}

    def load_medicine_targets(self) -> list[str]:
        packaged = self._place_catalog.medication_targets
        if packaged:
            return packaged
        loaded = self._load_literal_assignments("waypoints.py", frozenset({"MEDICINE_TARGETS"}))
        targets = loaded.get("MEDICINE_TARGETS", [])
        return [str(item) for item in targets] if isinstance(targets, list) else []

    def load_places(self) -> dict[str, dict[str, Any]]:
        packaged = self._place_catalog.places_by_source("config_places")
        if packaged:
            return packaged
        loaded = self._load_literal_assignments("config.py", frozenset({"places"}))
        places = loaded.get("places", {})
        return places if isinstance(places, dict) else {}

    def load_alarm_entries(self) -> list[dict[str, Any]]:
        packaged = self._schedule_catalog.load_entries()
        if packaged:
            return packaged
        loaded = self._load_literal_assignments("config.py", frozenset({"alarms"}))
        alarms = loaded.get("alarms", [])
        if not isinstance(alarms, list):
            return []
        normalized: list[dict[str, Any]] = []
        for item in alarms:
            if not isinstance(item, dict):
                continue
            normalized.append({str(key): value for key, value in item.items()})
        return normalized

    @lru_cache(maxsize=8)
    def _load_literal_assignments(self, file_name: str, variable_names: frozenset[str] | set[str]) -> dict[str, Any]:
        if self._legacy_dir is None:
            return {}
        file_path = self._legacy_dir / file_name
        if not file_path.exists():
            return {}

        try:
            module = ast.parse(file_path.read_text(encoding="utf-8"), filename=str(file_path))
        except Exception:
            return {}

        wanted = set(variable_names)
        loaded: dict[str, Any] = {}
        for node in module.body:
            if not isinstance(node, ast.Assign):
                continue
            if len(node.targets) != 1 or not isinstance(node.targets[0], ast.Name):
                continue
            name = node.targets[0].id
            if name not in wanted or name in loaded:
                continue
            try:
                loaded[name] = ast.literal_eval(node.value)
            except Exception:
                continue
        return loaded

    @staticmethod
    def _resolve_legacy_dir(legacy_dir: str | Path | None) -> Path | None:
        if legacy_dir is not None:
            candidate = Path(legacy_dir).expanduser().resolve()
            return candidate if candidate.exists() and candidate.is_dir() else None

        current = Path(__file__).resolve()
        for parent in current.parents:
            candidate = parent / "plus"
            if candidate.exists() and candidate.is_dir():
                return candidate
        return None
