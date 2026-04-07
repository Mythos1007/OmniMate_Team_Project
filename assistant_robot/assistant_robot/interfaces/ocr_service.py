from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(slots=True)
class OCRResult:
    target_user: str | None = None
    target_location: str | None = None
    confidence: float = 0.0
    raw_text: str = ""


class BaseOCRService(ABC):
    @abstractmethod
    def extract_delivery_target(self, raw_input: str) -> OCRResult:
        raise NotImplementedError
