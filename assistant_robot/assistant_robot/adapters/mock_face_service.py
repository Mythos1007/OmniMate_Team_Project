from __future__ import annotations

from collections import deque
from datetime import datetime

from assistant_robot.interfaces.face_service import BaseFaceRecognitionService, RecognizedFace


class MockFaceRecognitionService(BaseFaceRecognitionService):
    def __init__(self) -> None:
        self._queue: deque[RecognizedFace] = deque()

    def enqueue(self, user_name: str) -> None:
        self._queue.append(RecognizedFace(user_name=user_name, recognized_at=datetime.utcnow()))

    def detect_registered_person(self) -> RecognizedFace | None:
        return self._queue.popleft() if self._queue else None
