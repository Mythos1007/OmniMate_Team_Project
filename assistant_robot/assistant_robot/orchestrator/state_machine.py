from __future__ import annotations

from dataclasses import replace

from assistant_robot.models.enums import MissionStatus, TopState
from assistant_robot.models.mission import Mission
from assistant_robot.models.robot_state import RobotState
from assistant_robot.orchestrator.battery_policy import BatteryPolicy


class RobotStateMachine:
    """기능: 로봇의 상위 상태를 단일 축으로 관리 기능.

    주의:
    - 상태(top_state)와 queue는 별개 개념이다.
    - queue는 여러 개 미션을 담고, 상태는 항상 하나만 가진다.
    """

    def __init__(self, battery_policy: BatteryPolicy) -> None:
        self._battery_policy = battery_policy
        self._state = RobotState()

    @property
    def state(self) -> RobotState:
        return self._state

    def boot_completed(self) -> None:
        self._state.top_state = TopState.IDLE
        self._refresh_status_message()

    def update_battery(self, *, battery_level: float, charging: bool, charging_eta_minutes: int | None = None) -> None:
        # 기능: 배터리/충전 정보를 반영하고 LOW_BATTERY_RESTRICTED 진입 여부를 계산 기능.
        self._state.battery_level = battery_level
        self._state.charging = charging
        self._state.charging_eta_minutes = charging_eta_minutes
        self._state.low_battery_restricted = self._battery_policy.is_restricted(
            battery_level=battery_level,
            charging=charging,
        )
        if self._state.top_state not in {TopState.EXECUTING, TopState.WAITING_CONFIRMATION, TopState.EMERGENCY_STOP, TopState.ERROR}:
            if charging:
                self._state.top_state = TopState.CHARGING
            elif self._state.low_battery_restricted:
                self._state.top_state = TopState.LOW_BATTERY_RESTRICTED
            else:
                self._state.top_state = TopState.IDLE
        self._refresh_status_message()

    def set_pending_count(self, pending_count: int) -> None:
        self._state.pending_count = pending_count
        self._refresh_status_message()

    def set_active_mission(self, mission: Mission) -> None:
        self._state.current_mission_id = mission.mission_id
        self._state.current_mission_type = mission.mission_type.value
        self._state.current_detail = mission.target_location or mission.target_user or mission.mission_type.value
        self._state.top_state = TopState.EXECUTING
        self._refresh_status_message()

    def set_waiting_confirmation(self, mission: Mission) -> None:
        self._state.current_mission_id = mission.mission_id
        self._state.current_mission_type = mission.mission_type.value
        self._state.top_state = TopState.WAITING_CONFIRMATION
        self._refresh_status_message()

    def clear_active_mission(self) -> None:
        self._state.current_mission_id = None
        self._state.current_mission_type = None
        self._state.current_detail = ""
        if self._state.charging:
            self._state.top_state = TopState.CHARGING
        elif self._state.low_battery_restricted:
            self._state.top_state = TopState.LOW_BATTERY_RESTRICTED
        else:
            self._state.top_state = TopState.IDLE
        self._refresh_status_message()

    def set_error(self, message: str) -> None:
        self._state.top_state = TopState.ERROR
        self._state.current_detail = message
        self._refresh_status_message()

    def set_emergency_stop(self, enabled: bool) -> None:
        if enabled:
            self._state.top_state = TopState.EMERGENCY_STOP
        else:
            self.clear_active_mission()
        self._refresh_status_message()

    def apply_event(self, mission: Mission, *, event_type: str, status: MissionStatus | None = None) -> None:
        # 기능: executor 단계 이벤트를 top_state로 축약 반영 기능.
        if event_type == "waiting_confirmation":
            self.set_waiting_confirmation(mission)
            return
        if event_type in {"started", "navigating", "arrived"}:
            self.set_active_mission(mission)
            return
        if status in {MissionStatus.COMPLETED, MissionStatus.FAILED, MissionStatus.CANCELLED, MissionStatus.EXPIRED}:
            self.clear_active_mission()

    def snapshot(self) -> RobotState:
        return replace(self._state)

    def _refresh_status_message(self) -> None:
        # 기능: GUI가 바로 쓸 수 있는 안내 문구를 중앙에서 생성 기능.
        state = self._state
        if state.top_state == TopState.BOOTING:
            state.status_message_for_gui = "부팅 중입니다."
        elif state.top_state == TopState.EXECUTING:
            state.status_message_for_gui = f"현재 작업 중, 대기열 {state.pending_count}건"
        elif state.top_state == TopState.WAITING_CONFIRMATION:
            state.status_message_for_gui = "확인 응답을 기다리는 중입니다."
        elif state.top_state == TopState.CHARGING:
            if state.charging_eta_minutes is not None:
                state.status_message_for_gui = f"충전 중입니다. 약 {state.charging_eta_minutes}분 남았습니다."
            else:
                state.status_message_for_gui = "충전 중입니다."
        elif state.top_state == TopState.LOW_BATTERY_RESTRICTED:
            state.status_message_for_gui = "배터리가 부족하여 이동 요청이 제한됩니다."
        elif state.top_state == TopState.ERROR:
            state.status_message_for_gui = state.current_detail or "오류 상태입니다."
        elif state.top_state == TopState.EMERGENCY_STOP:
            state.status_message_for_gui = "비상 정지 상태입니다."
        else:
            state.status_message_for_gui = f"대기 중입니다. 대기열 {state.pending_count}건"
