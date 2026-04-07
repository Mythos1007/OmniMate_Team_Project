from __future__ import annotations

import re
from typing import Any


DISTANCE_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"(?P<value>\d+(?:\.\d+)?)\s*(?:미터|m)"), "meter"),
    (re.compile(r"(?P<value>\d+(?:\.\d+)?)\s*(?:센티미터|cm)"), "centimeter"),
)

DURATION_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"(?P<value>\d+(?:\.\d+)?)\s*(?:초|second|sec|s)"), "second"),
    (re.compile(r"(?P<value>\d+(?:\.\d+)?)\s*(?:분|minute|min)"), "minute"),
)


def clean_text(text: str) -> str:
    collapsed = re.sub(r"\s+", " ", text.strip())
    return collapsed.lower()


def strip_measurements_for_matching(text: str) -> str:
    stripped = text
    for pattern, _unit in DISTANCE_PATTERNS + DURATION_PATTERNS:
        stripped = pattern.sub(" ", stripped)

    stripped = re.sub(r"\b동안\b", " ", stripped)
    return clean_text(stripped)


def _extract_measurement(
    text: str, patterns: tuple[tuple[re.Pattern[str], str], ...], value_key: str
) -> dict[str, Any]:
    for pattern, unit in patterns:
        match = pattern.search(text)
        if match:
            return {
                value_key: float(match.group("value")),
                "unit": unit,
            }
    return {}


def parse_distance(text: str) -> dict[str, Any]:
    return _extract_measurement(text, DISTANCE_PATTERNS, "distance")


def parse_duration(text: str) -> dict[str, Any]:
    return _extract_measurement(text, DURATION_PATTERNS, "duration")


def parse_command_args(text: str) -> dict[str, Any]:
    args: dict[str, Any] = {}
    for parser in (parse_distance, parse_duration):
        args.update(parser(text))
    return args
