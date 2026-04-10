from __future__ import annotations

_TRAILING_PARTICLES = (
    "에게",
    "한테",
    "으로",
    "로",
    "에",
)


def normalize_navigation_target(raw_target: str) -> str:
    text = "".join(str(raw_target or "").split())
    if not text:
        return ""
    for suffix in _TRAILING_PARTICLES:
        if text.endswith(suffix) and len(text) > len(suffix):
            return text[: -len(suffix)]
    return text