from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True)
class RecognizedFace:
    user_name: str
    recognized_at: datetime
    confidence: float = 1.0


class BaseFaceRecognitionService(ABC):
    @abstractmethod
    def detect_registered_person(self) -> RecognizedFace | None:
        raise NotImplementedError
