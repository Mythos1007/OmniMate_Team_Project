from __future__ import annotations

import threading
import time

from std_msgs.msg import Bool

from assistant_robot.interfaces.confirmation_service import BaseConfirmationService


class RosConfirmationService(BaseConfirmationService):
    def __init__(self, node, *, topic_name: str = "/assistant/confirmation") -> None:
        self._node = node
        self._condition = threading.Condition()
        self._confirmation_generation = 0
        self._mission_baselines: dict[str, int] = {}
        self._subscription = self._node.create_subscription(Bool, topic_name, self._on_confirmation, 10)

    def _on_confirmation(self, message: Bool) -> None:
        if not bool(message.data):
            return
        with self._condition:
            self._confirmation_generation += 1
            self._condition.notify_all()

    def wait_for_confirmation(self, *, mission_id: str, timeout_seconds: int = 30) -> bool:
        timeout_seconds = max(0, int(timeout_seconds))
        with self._condition:
            baseline = self._mission_baselines.setdefault(mission_id, self._confirmation_generation)
            if self._confirmation_generation > baseline:
                self._mission_baselines.pop(mission_id, None)
                return True
            if timeout_seconds == 0:
                return False

            deadline = time.monotonic() + timeout_seconds
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return False
                self._condition.wait(timeout=remaining)
                if self._confirmation_generation > baseline:
                    self._mission_baselines.pop(mission_id, None)
                    return True