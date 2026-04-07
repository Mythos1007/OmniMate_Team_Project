from __future__ import annotations

from abc import ABC, abstractmethod


class BaseConfirmationService(ABC):
    @abstractmethod
    def wait_for_confirmation(self, *, mission_id: str, timeout_seconds: int = 30) -> bool:
        raise NotImplementedError
