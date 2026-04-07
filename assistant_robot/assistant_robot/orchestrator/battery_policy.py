from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from assistant_robot.models.command_request import CommandRequest
from assistant_robot.models.enums import MissionType
from assistant_robot.models.mission import Mission
from assistant_robot.models.robot_state import RobotState


@dataclass(slots=True)
class BatteryPolicy:
    """기능: 배터리 관련 intake/dispatch 정책을 단일 클래스로 관리한다."""

    low_battery_threshold: float = 20.0
    allow_queue_registration_while_charging: bool = True
    return_location: str = "charging_station"

    def is_restricted(self, *, battery_level: float, charging: bool) -> bool:
        return battery_level <= self.low_battery_threshold and not charging

    def can_accept_command(self, command: CommandRequest, state: RobotState) -> tuple[bool, str]:
        # 정책: 저전력 제한에서는 이동 필요 명령만 거절하고, non-move 요청은 허용한다.
        if state.charging and not self.allow_queue_registration_while_charging and command.requires_movement:
            return False, "charging_reject_move"
        if state.low_battery_restricted and command.requires_movement:
            return False, "battery.low_reject_move"
        return True, "queue.accepted"

    def can_dispatch_mission(self, mission: Mission, state: RobotState) -> bool:
        # 정책: 제한 상태에서는 복귀 미션 이외의 이동 미션 dispatch를 막는다.
        if state.low_battery_restricted and mission.requires_movement:
            return mission.mission_type == MissionType.RETURN_TO_BASE
        return True

    def should_return_after_current(self, state: RobotState, *, current_mission: Mission | None) -> bool:
        if not state.low_battery_restricted:
            return False
        if current_mission is None:
            return False
        return current_mission.mission_type != MissionType.RETURN_TO_BASE

    def build_return_mission(self, *, now: datetime | None = None) -> Mission:
        return Mission(
            mission_id=f"return-{int((now or datetime.utcnow()).timestamp())}",
            mission_type=MissionType.RETURN_TO_BASE,
            priority=1000,
            created_at=now or datetime.utcnow(),
            target_location=self.return_location,
            requires_movement=True,
        )
