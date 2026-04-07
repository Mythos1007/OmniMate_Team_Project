from __future__ import annotations

from dataclasses import dataclass

from assistant_robot.models.enums import TopState


@dataclass(slots=True)
class RobotState:
    top_state: TopState = TopState.BOOTING
    current_mission_id: str | None = None
    battery_level: float = 100.0
    charging: bool = False
    low_battery_restricted: bool = False
    pending_count: int = 0
    status_message_for_gui: str = "부팅 중입니다."
    charging_eta_minutes: int | None = None
    current_mission_type: str | None = None
    current_detail: str = ""
