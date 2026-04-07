from __future__ import annotations

from assistant_robot.interfaces.confirmation_service import BaseConfirmationService


class MockConfirmationService(BaseConfirmationService):
    def __init__(self, *, default_result: bool = True) -> None:
        self.default_result = default_result
        self.calls: list[str] = []

    def wait_for_confirmation(self, *, mission_id: str, timeout_seconds: int = 30) -> bool:
        del timeout_seconds
        self.calls.append(mission_id)
        return self.default_result
