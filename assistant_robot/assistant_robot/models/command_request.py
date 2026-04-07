from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from assistant_robot.models.enums import CommandSource, MissionType


@dataclass(slots=True)
class CommandRequest:
    source: CommandSource
    raw_text: str = ""
    parsed_intent: dict[str, Any] = field(default_factory=dict)
    requires_movement: bool = False
    target_user: str | None = None
    target_location: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)

    @property
    def mission_type(self) -> MissionType:
        intent_name = self.parsed_intent.get("intent_name", MissionType.STATUS_BRIEF.value)
        return MissionType(intent_name)
