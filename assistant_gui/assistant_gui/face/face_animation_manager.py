from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import datetime, timedelta

from .face_models import BlinkState, MouthState


@dataclass(slots=True)
class FaceOverlayState:
    blink_state: BlinkState = BlinkState.OPEN
    mouth_state: MouthState = MouthState.IDLE


class FaceAnimationManager:
    """blink / mouth overlay 프레임을 관리 기능."""

    def __init__(self) -> None:
        self._overlay = FaceOverlayState()
        self._next_blink_at = datetime.utcnow() + timedelta(seconds=self._next_blink_interval())
        self._blink_step = 0
        self._blink_last_change = datetime.utcnow()
        self._mouth_index = 0
        self._mouth_last_change = datetime.utcnow()

    @staticmethod
    def _next_blink_interval() -> float:
        return random.uniform(2.8, 5.0)

    def trigger_blink_once(self, *, now: datetime | None = None) -> None:
        now = now or datetime.utcnow()
        self._blink_step = 1
        self._blink_last_change = now

    def update(self, *, now: datetime | None = None, blink_enabled: bool = True, speaking_active: bool = False) -> FaceOverlayState:
        now = now or datetime.utcnow()

        # Blink progression
        if blink_enabled:
            if self._blink_step == 0 and now >= self._next_blink_at:
                self._blink_step = 1
                self._blink_last_change = now
            elif self._blink_step in (1, 2) and (now - self._blink_last_change).total_seconds() >= 0.09:
                self._blink_step += 1
                self._blink_last_change = now
            elif self._blink_step >= 3 and (now - self._blink_last_change).total_seconds() >= 0.09:
                self._blink_step = 0
                self._next_blink_at = now + timedelta(seconds=self._next_blink_interval())
        else:
            self._blink_step = 0

        if self._blink_step == 1:
            self._overlay.blink_state = BlinkState.CLOSED_1
        elif self._blink_step == 2:
            self._overlay.blink_state = BlinkState.CLOSED_2
        else:
            self._overlay.blink_state = BlinkState.OPEN

        # Mouth progression
        if speaking_active:
            if (now - self._mouth_last_change).total_seconds() >= 0.12:
                self._mouth_index = (self._mouth_index + 1) % 4
                self._mouth_last_change = now
        else:
            self._mouth_index = 0
            self._mouth_last_change = now

        self._overlay.mouth_state = [
            MouthState.IDLE,
            MouthState.FRAME_1,
            MouthState.FRAME_2,
            MouthState.FRAME_3,
        ][self._mouth_index]

        return self._overlay
