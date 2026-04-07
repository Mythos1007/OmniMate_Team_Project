from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


CanonicalCommandName = Literal[
    "move_forward",
    "move_backward",
    "turn_left",
    "turn_right",
    "stop",
    "start_patrol",
    "pause_patrol",
    "resume_patrol",
    "status_query",
    "weather_query",
    "alarm_create",
    "alarm_list",
    "schedule_create",
    "schedule_list",
    "guide_to_location",
    "deliver_mail",
    "unknown",
]

SUPPORTED_COMMANDS: tuple[CanonicalCommandName, ...] = (
    "move_forward",
    "move_backward",
    "turn_left",
    "turn_right",
    "stop",
    "start_patrol",
    "pause_patrol",
    "resume_patrol",
    "status_query",
    "weather_query",
    "alarm_create",
    "alarm_list",
    "schedule_create",
    "schedule_list",
    "guide_to_location",
    "deliver_mail",
    "unknown",
)


@dataclass(slots=True)
class CanonicalCommand:
    command: CanonicalCommandName
    args: dict[str, Any] = field(default_factory=dict)
    original_text: str = ""

    def to_dict(self) -> dict[str, Any]:
        args = dict(self.args)
        if self.command == "unknown" and self.original_text:
            args.setdefault("original_text", self.original_text)

        return {
            "command": self.command,
            "args": args,
        }
