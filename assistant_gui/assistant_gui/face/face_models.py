from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class FaceBaseState(str, Enum):
    IDLE = "idle"
    LISTENING = "listening"
    THINKING = "thinking"
    NAVIGATING = "navigating"
    WAITING_CONFIRMATION = "waiting_confirmation"
    CHARGING = "charging"
    LOW_BATTERY = "low_battery"
    ERROR = "error"
    EMERGENCY_STOP = "emergency_stop"


class TempExpression(str, Enum):
    NONE = "none"
    HAPPY = "happy"
    GREETING = "greeting"
    APOLOGETIC = "apologetic"
    SURPRISED = "surprised"


class BlinkState(str, Enum):
    OPEN = "open"
    CLOSED_1 = "closed_1"
    CLOSED_2 = "closed_2"


class MouthState(str, Enum):
    IDLE = "mouth_0"
    FRAME_1 = "mouth_1"
    FRAME_2 = "mouth_2"
    FRAME_3 = "mouth_3"


@dataclass(slots=True)
class FaceContext:
    # Source state from robot/app domain.
    system_base_state: FaceBaseState = FaceBaseState.IDLE
    # Non-power fallback state used when charging/low-battery overlays clear.
    fallback_base_state: FaceBaseState = FaceBaseState.IDLE
    # Short-lived base override (e.g., listening transient).
    transient_base_state: FaceBaseState | None = None
    transient_until: datetime | None = None
    # Final resolved display state consumed by renderer.
    display_state: FaceBaseState = FaceBaseState.IDLE

    temp_expression: TempExpression = TempExpression.NONE
    temp_until: datetime | None = None

    tts_active: bool = False
    blink_enabled: bool = True
    speaking_enabled: bool = True

    battery_percent: float = 100.0
    is_charging: bool = False
    low_battery_latched: bool = False

    current_mission_name: str = ""
    last_update_time: datetime = field(default_factory=datetime.utcnow)
