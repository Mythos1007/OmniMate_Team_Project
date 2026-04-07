from __future__ import annotations

from uuid import uuid4

from assistant_robot.interfaces.navigation_controller import (
    BaseNavigationController,
    NavigationHandle,
    NavigationState,
)


class MockNavigationController(BaseNavigationController):
    def __init__(self, *, steps_per_navigation: int = 2, current_location: str = "home") -> None:
        self.steps_per_navigation = steps_per_navigation
        self.current_location = current_location

    def start_navigation(self, target_location: str, *, metadata: dict[str, object] | None = None) -> NavigationHandle:
        return NavigationHandle(
            navigation_id=str(uuid4()),
            target_location=target_location,
            status=NavigationState.NAVIGATING,
            steps_remaining=self.steps_per_navigation,
            metadata=dict(metadata or {}),
        )

    def poll_navigation(self, handle: NavigationHandle) -> NavigationHandle:
        if handle.status != NavigationState.NAVIGATING:
            return handle
        handle.steps_remaining -= 1
        if handle.steps_remaining <= 0:
            handle.status = NavigationState.ARRIVED
            self.current_location = handle.target_location
        return handle

    def cancel_navigation(self, handle: NavigationHandle) -> None:
        handle.status = NavigationState.CANCELLED

    def get_current_location(self) -> str:
        return self.current_location
