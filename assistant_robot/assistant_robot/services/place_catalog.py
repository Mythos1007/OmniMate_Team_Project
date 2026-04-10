from __future__ import annotations

from dataclasses import dataclass
from importlib.resources import files
import os
from pathlib import Path
from typing import Any

import yaml

from assistant_robot.services.navigation_target_normalizer import normalize_navigation_target


@dataclass(frozen=True, slots=True)
class NamedPlace:
    name: str
    metadata: dict[str, Any]

    @property
    def aliases(self) -> tuple[str, ...]:
        raw_aliases = self.metadata.get("aliases", [])
        if not isinstance(raw_aliases, list):
            return ()
        return tuple(str(item) for item in raw_aliases if str(item).strip())

    @property
    def ocr_enabled(self) -> bool:
        return bool(self.metadata.get("ocr_enabled", False))

    @property
    def source(self) -> str:
        return str(self.metadata.get("source", "")).strip()


class PlaceCatalog:
    def __init__(self, config_path: str | Path | None = None) -> None:
        self._config_path = Path(config_path).expanduser().resolve() if config_path else None
        self._raw = self._load_raw()
        self._places = self._load_places()
        self._alias_map = self._build_alias_map()

    @property
    def medication_targets(self) -> list[str]:
        targets = self._raw.get("medication_targets", [])
        return [str(item) for item in targets] if isinstance(targets, list) else []

    def named_places(self) -> dict[str, NamedPlace]:
        return dict(self._places)

    def place_metadata(self) -> dict[str, dict[str, Any]]:
        return {name: dict(place.metadata) for name, place in self._places.items()}

    def places_by_source(self, source_name: str) -> dict[str, dict[str, Any]]:
        return {
            name: dict(place.metadata)
            for name, place in self._places.items()
            if place.source == source_name
        }

    def ocr_keywords(self) -> tuple[str, ...]:
        names = [name for name, place in self._places.items() if place.ocr_enabled]
        return tuple(sorted(names, key=len, reverse=True))

    def resolve(self, raw_name: str) -> str:
        compact = self._compact(raw_name)
        if not compact:
            return raw_name
        exact = self._alias_map.get(compact)
        if exact:
            return exact
        for alias, canonical in self._alias_map.items():
            if alias and alias in compact:
                return canonical
        return raw_name

    def _load_raw(self) -> dict[str, Any]:
        config_path = self._resolve_config_path()
        loaded = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        return loaded if isinstance(loaded, dict) else {}

    def _resolve_config_path(self) -> Path:
        if self._config_path is not None:
            return self._config_path

        env_path = os.environ.get("ASSISTANT_NAMED_PLACES_FILE", "").strip()
        if env_path:
            candidate = Path(env_path).expanduser().resolve()
            if candidate.exists():
                return candidate

        source_root = Path(__file__).resolve().parents[3]
        source_candidates = (
            source_root / "assistant_bringup" / "config" / "named_places_catalog.yaml",
            source_root / "assistant_robot" / "assistant_robot" / "config" / "named_places.yaml",
        )
        for candidate in source_candidates:
            if candidate.exists():
                return candidate

        return Path(files("assistant_robot.config").joinpath("named_places.yaml"))

    def _load_places(self) -> dict[str, NamedPlace]:
        raw_places = self._raw.get("named_places", {})
        if not isinstance(raw_places, dict):
            return {}
        places: dict[str, NamedPlace] = {}
        for name, metadata in raw_places.items():
            if not isinstance(metadata, dict):
                continue
            places[str(name)] = NamedPlace(name=str(name), metadata={str(key): value for key, value in metadata.items()})
        return places

    def _build_alias_map(self) -> dict[str, str]:
        alias_map: dict[str, str] = {}
        for name, place in self._places.items():
            alias_map[self._compact(name)] = name
            for alias in place.aliases:
                alias_map[self._compact(alias)] = name
        return alias_map

    @staticmethod
    def _compact(value: str) -> str:
        return normalize_navigation_target(str(value or "").lower())
