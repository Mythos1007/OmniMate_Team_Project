from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Literal


InputType = Literal["text", "audio"]


@dataclass(slots=True)
class InputPayload:
    input_type: InputType
    raw_input: str
    metadata: dict[str, Any] = field(default_factory=dict)


class InputProvider(ABC):
    @abstractmethod
    def get_input(self) -> InputPayload:
        """Return one input event from any source."""


class STTService(ABC):
    @abstractmethod
    def transcribe(self, payload: InputPayload) -> str:
        """Convert an audio payload into text."""
