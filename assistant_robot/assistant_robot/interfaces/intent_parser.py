from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from assistant_robot.models.command_request import CommandRequest


@dataclass(slots=True)
class IntentParseResult:
    primary_command: CommandRequest | None
    rejected_commands: list[CommandRequest] = field(default_factory=list)
    rejection_message_key: str | None = None


class BaseIntentParser(ABC):
    @abstractmethod
    def parse(self, raw_text: str) -> IntentParseResult:
        raise NotImplementedError
