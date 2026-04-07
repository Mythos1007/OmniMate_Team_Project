from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from assistant_robot.models.enums import TtsPriority


@dataclass(slots=True)
class TTSRequest:
    text: str
    priority: TtsPriority = TtsPriority.NORMAL
    interrupt: bool = False
    ssml: str | None = None
    voice_style: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class BaseTTSProvider(ABC):
    @abstractmethod
    def speak(self, request: TTSRequest) -> None:
        raise NotImplementedError

    @abstractmethod
    def stop(self) -> None:
        raise NotImplementedError
