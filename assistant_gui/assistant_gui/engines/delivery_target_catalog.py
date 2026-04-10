from __future__ import annotations

from pathlib import Path

import yaml


DELIVERY_TARGET_KEYWORDS: tuple[str, ...] = (
    "마케팅팀",
    "영업팀",
    "개발팀",
    "기획팀",
    "인사팀",
    "회계팀",
    "희정님",
)


def match_delivery_target(text: str) -> str:
    compact = "".join(str(text or "").split())
    for keyword in DELIVERY_TARGET_KEYWORDS:
        if keyword in compact:
            return keyword
    return ""


def _resolve_named_place_config_path() -> Path | None:
    here = Path(__file__).resolve()
    candidates = [
        here.parents[2] / "assistant_robot" / "assistant_robot" / "config" / "named_places.yaml",
        here.parents[4] / "assistant_robot" / "assistant_robot" / "config" / "named_places.yaml",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def load_delivery_target_lookup() -> dict[str, str]:
    config_path = _resolve_named_place_config_path()
    if config_path is None:
        return {keyword.replace(" ", ""): keyword for keyword in DELIVERY_TARGET_KEYWORDS}

    try:
        loaded = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except Exception:
        return {keyword.replace(" ", ""): keyword for keyword in DELIVERY_TARGET_KEYWORDS}

    named_places = loaded.get("named_places", {}) if isinstance(loaded, dict) else {}
    if not isinstance(named_places, dict):
        return {keyword.replace(" ", ""): keyword for keyword in DELIVERY_TARGET_KEYWORDS}

    lookup: dict[str, str] = {}
    for name, metadata in named_places.items():
        if not isinstance(metadata, dict) or not bool(metadata.get("ocr_enabled", False)):
            continue
        canonical = str(name).strip()
        if not canonical:
            continue
        aliases = metadata.get("aliases", [])
        if not isinstance(aliases, list):
            aliases = []
        for alias in [canonical, *aliases]:
            alias_text = str(alias).strip()
            if alias_text:
                lookup[alias_text.replace(" ", "")] = canonical
    if lookup:
        return lookup
    return {keyword.replace(" ", ""): keyword for keyword in DELIVERY_TARGET_KEYWORDS}


def match_delivery_target_from_lookup(text: str, lookup: dict[str, str]) -> str:
    compact = "".join(str(text or "").split())
    for keyword in sorted(lookup.keys(), key=len, reverse=True):
        if keyword in compact:
            return lookup[keyword]
    return ""
