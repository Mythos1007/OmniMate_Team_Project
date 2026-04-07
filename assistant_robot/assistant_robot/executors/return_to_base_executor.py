from __future__ import annotations

from assistant_robot.executors.base import BaseMissionExecution, BaseMissionExecutor, ExecutorContext
from assistant_robot.interfaces.navigation_controller import NavigationHandle, NavigationState
from assistant_robot.models.enums import MissionStatus
from assistant_robot.models.mission import Mission
from assistant_robot.models.mission_result import MissionEvent


class ReturnToBaseExecution(BaseMissionExecution):
    def __init__(self, mission: Mission, context: ExecutorContext) -> None:
        super().__init__(mission, context)
        self._navigation: NavigationHandle | None = None
        self._started = False

    def step(self) -> MissionEvent:
        target_location = self.mission.target_location or "충전소"
        if not self._started:
            self._started = True
            self._navigation = self.context.navigation_controller.start_navigation(target_location)
            return MissionEvent(
                mission_id=self.mission.mission_id,
                event_type="started",
                message_key="battery.low_finish_then_return",
            )
        if self._navigation is None:
            return MissionEvent(
                mission_id=self.mission.mission_id,
                event_type="failed",
                message_key="error.general",
                terminal=True,
                details={"status": MissionStatus.FAILED.value},
            )
        self._navigation = self.context.navigation_controller.poll_navigation(self._navigation)
        if self._navigation.status == NavigationState.ARRIVED:
            return MissionEvent(
                mission_id=self.mission.mission_id,
                event_type="completed",
                message_key="navigation.arrived",
                message_params={"target_location": target_location},
                terminal=True,
                details={"status": MissionStatus.COMPLETED.value},
            )
        return MissionEvent(mission_id=self.mission.mission_id, event_type="navigating")


class ReturnToBaseExecutor(BaseMissionExecutor):
    def create_execution(self, mission: Mission, context: ExecutorContext) -> BaseMissionExecution:
        return ReturnToBaseExecution(mission, context)
