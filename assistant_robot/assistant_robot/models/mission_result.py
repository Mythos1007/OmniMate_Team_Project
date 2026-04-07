from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from assistant_robot.models.enums import MissionStatus


@dataclass(slots=True)
class MissionEvent:
    mission_id: str
    event_type: str
    message_key: str | None = None
    message_params: dict[str, Any] = field(default_factory=dict)
    details: dict[str, Any] = field(default_factory=dict)
    terminal: bool = False


@dataclass(slots=True)
class MissionResult:
    mission_id: str
    status: MissionStatus
    events: list[MissionEvent] = field(default_factory=list)
    error: str | None = None


@dataclass(slots=True)
class IntakeDecision:
    accepted: bool
    reason: str
    gui_message: str
    tts_message_key: str | None = None
    tts_message_params: dict[str, Any] = field(default_factory=dict)
    mission_id: str | None = None
    queued: bool = False
