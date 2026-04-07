from __future__ import annotations

from assistant_robot.executors.base import BaseMissionExecution, BaseMissionExecutor, ExecutorContext
from assistant_robot.interfaces.navigation_controller import NavigationHandle, NavigationState
from assistant_robot.models.enums import MissionStatus
from assistant_robot.models.mission import Mission
from assistant_robot.models.mission_result import MissionEvent


class CallExecution(BaseMissionExecution):
    def __init__(self, mission: Mission, context: ExecutorContext) -> None:
        super().__init__(mission, context)
        self._phase = 0
        self._navigation: NavigationHandle | None = None

    def step(self) -> MissionEvent:
        if not self.mission.target_location and not self.mission.target_user:
            return MissionEvent(
                mission_id=self.mission.mission_id,
                event_type="failed",
                message_key="error.general",
                terminal=True,
                details={"status": MissionStatus.FAILED.value},
            )
        target_location = self.mission.target_location or self.mission.target_user or "지정 위치"
        if self._phase == 0:
            self._phase = 1
            return MissionEvent(
                mission_id=self.mission.mission_id,
                event_type="started",
                message_key="call.start",
                message_params={"user_name": self.mission.target_user or target_location},
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
                return MissionEvent(
                    mission_id=self.mission.mission_id,
                    event_type="completed",
                    message_key="call.arrived",
                    message_params={"user_name": self.mission.target_user or target_location},
                    terminal=True,
                    details={"status": MissionStatus.COMPLETED.value},
                )
            if self._navigation.status == NavigationState.FAILED:
                return MissionEvent(
                    mission_id=self.mission.mission_id,
                    event_type="failed",
                    message_key="error.general",
                    terminal=True,
                    details={"status": MissionStatus.FAILED.value},
                )
            return MissionEvent(mission_id=self.mission.mission_id, event_type="navigating")
        return MissionEvent(mission_id=self.mission.mission_id, event_type="failed", terminal=True, details={"status": MissionStatus.FAILED.value})


class CallExecutor(BaseMissionExecutor):
    def create_execution(self, mission: Mission, context: ExecutorContext) -> BaseMissionExecution:
        return CallExecution(mission, context)
