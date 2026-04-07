from __future__ import annotations

from abc import ABC, abstractmethod


class BaseSeatResolver(ABC):
    @abstractmethod
    def resolve(self, user_name: str) -> str | None:
        raise NotImplementedError
