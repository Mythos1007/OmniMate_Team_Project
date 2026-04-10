from __future__ import annotations

from dataclasses import dataclass
import re


_COORDINATE_TARGET_PATTERN = re.compile(
    r"^navigate\s*:\s*"
    r"x\s*=\s*(?P<x>-?\d+(?:\.\d+)?)\s*,\s*"
    r"y\s*=\s*(?P<y>-?\d+(?:\.\d+)?)"
    r"(?:\s*,\s*yaw\s*=\s*(?P<yaw>-?\d+(?:\.\d+)?))?"
    r"(?:\s*,\s*frame(?:_id)?\s*=\s*(?P<frame_id>[A-Za-z0-9_./-]+))?\s*$",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class CoordinateTarget:
    x: float
    y: float
    yaw: float = 0.0
    frame_id: str = "map"


def parse_coordinate_target(raw_target: str) -> CoordinateTarget | None:
    match = _COORDINATE_TARGET_PATTERN.match(str(raw_target or "").strip())
    if match is None:
        return None
    frame_id = str(match.group("frame_id") or "map").strip() or "map"
    return CoordinateTarget(
        x=float(match.group("x")),
        y=float(match.group("y")),
        yaw=float(match.group("yaw") or 0.0),
        frame_id=frame_id,
    )