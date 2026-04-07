from __future__ import annotations

from assistant_robot.executors.base import BaseMissionExecution, BaseMissionExecutor, ExecutorContext
from assistant_robot.interfaces.navigation_controller import NavigationHandle, NavigationState
from assistant_robot.models.enums import MissionStatus
from assistant_robot.models.mission import Mission
from assistant_robot.models.mission_result import MissionEvent


class AlarmExecution(BaseMissionExecution):
    def __init__(self, mission: Mission, context: ExecutorContext) -> None:
        super().__init__(mission, context)
        self._phase = 0
        self._navigation: NavigationHandle | None = None

    def step(self) -> MissionEvent:
        target_location = self.mission.target_location or "알림 위치"
        if self._phase == 0:
            self._phase = 1
            return MissionEvent(
                mission_id=self.mission.mission_id,
                event_type="started",
                message_key="alarm.start",
                message_params={"target_location": target_location},
            )
        if self._phase == 1:
            self._navigation = self.context.navigation_controller.start_navigation(target_location)
            self._phase = 2
            return MissionEvent(
                mission_id=self.mission.mission_id,
                event_type="navigating",
                message_key="navigation.resume",
                message_params={"target_location": target_location},
            )
        if self._phase == 2 and self._navigation is not None:
            self._navigation = self.context.navigation_controller.poll_navigation(self._navigation)
            if self._navigation.status == NavigationState.ARRIVED:
                self._phase = 3
                return MissionEvent(
                    mission_id=self.mission.mission_id,
                    event_type="arrived",
                    message_key="alarm.arrived",
                    message_params={"target_location": target_location},
                )
            return MissionEvent(mission_id=self.mission.mission_id, event_type="navigating")
        if self._phase == 3:
            self._phase = 4
            message_key = "medication.reminder" if self.mission.payload.get("medication") else "alarm.wait_confirm"
            return MissionEvent(
                mission_id=self.mission.mission_id,
                event_type="waiting_confirmation",
                message_key=message_key,
                message_params={"user_name": self.mission.target_user or "사용자"},
            )
        confirmed = self.context.confirmation_service.wait_for_confirmation(mission_id=self.mission.mission_id)
        if self.mission.payload.get("medication") and confirmed:
            return MissionEvent(
                mission_id=self.mission.mission_id,
                event_type="completed",
                message_key="medication.check_completed",
                terminal=True,
                details={"status": MissionStatus.COMPLETED.value},
            )
        return MissionEvent(
            mission_id=self.mission.mission_id,
            event_type="completed" if confirmed else "failed",
            message_key="alarm.wait_confirm" if not confirmed else None,
            terminal=True,
            details={"status": MissionStatus.COMPLETED.value if confirmed else MissionStatus.FAILED.value},
        )


class AlarmExecutor(BaseMissionExecutor):
    def create_execution(self, mission: Mission, context: ExecutorContext) -> BaseMissionExecution:
        return AlarmExecution(mission, context)
