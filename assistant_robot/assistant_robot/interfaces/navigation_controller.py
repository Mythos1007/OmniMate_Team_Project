from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class NavigationState(str, Enum):
    IDLE = "idle"
    NAVIGATING = "navigating"
    ARRIVED = "arrived"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(slots=True)
class NavigationHandle:
    navigation_id: str
    target_location: str
    status: NavigationState = NavigationState.NAVIGATING
    steps_remaining: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


class BaseNavigationController(ABC):
    @abstractmethod
    def start_navigation(self, target_location: str, *, metadata: dict[str, Any] | None = None) -> NavigationHandle:
        raise NotImplementedError

    @abstractmethod
    def poll_navigation(self, handle: NavigationHandle) -> NavigationHandle:
        raise NotImplementedError

    @abstractmethod
    def cancel_navigation(self, handle: NavigationHandle) -> None:
        raise NotImplementedError

    @abstractmethod
    def get_current_location(self) -> str:
        raise NotImplementedError
