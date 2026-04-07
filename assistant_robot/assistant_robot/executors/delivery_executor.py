from __future__ import annotations

from assistant_robot.executors.base import BaseMissionExecution, BaseMissionExecutor, ExecutorContext
from assistant_robot.interfaces.navigation_controller import NavigationHandle, NavigationState
from assistant_robot.models.enums import MissionStatus
from assistant_robot.models.mission import Mission
from assistant_robot.models.mission_result import MissionEvent


class DeliveryExecution(BaseMissionExecution):
    def __init__(self, mission: Mission, context: ExecutorContext) -> None:
        super().__init__(mission, context)
        self._phase = 0
        self._navigation: NavigationHandle | None = None

    def step(self) -> MissionEvent:
        if not self.mission.target_location:
            return MissionEvent(
                mission_id=self.mission.mission_id,
                event_type="failed",
                message_key="error.general",
                terminal=True,
                details={"status": MissionStatus.FAILED.value},
            )
        if self._phase == 0:
            self._phase = 1
            return MissionEvent(
                mission_id=self.mission.mission_id,
                event_type="started",
                message_key="delivery.start",
                message_params={"target_location": self.mission.target_location},
            )
        if self._phase == 1:
            self._navigation = self.context.navigation_controller.start_navigation(self.mission.target_location)
            self._phase = 2
            return MissionEvent(
                mission_id=self.mission.mission_id,
                event_type="navigating",
                message_key="navigation.resume",
                message_params={"target_location": self.mission.target_location},
            )
        if self._phase == 2 and self._navigation is not None:
            self._navigation = self.context.navigation_controller.poll_navigation(self._navigation)
            if self._navigation.status == NavigationState.ARRIVED:
                self._phase = 3
                return MissionEvent(
                    mission_id=self.mission.mission_id,
                    event_type="arrived",
                    message_key="delivery.arrived",
                    message_params={"target_location": self.mission.target_location},
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
        if self._phase == 3:
            self._phase = 4
            return MissionEvent(
                mission_id=self.mission.mission_id,
                event_type="waiting_confirmation",
                message_key="delivery.wait_sign",
            )
        confirmed = self.context.confirmation_service.wait_for_confirmation(mission_id=self.mission.mission_id)
        return MissionEvent(
            mission_id=self.mission.mission_id,
            event_type="completed" if confirmed else "failed",
            message_key="delivery.completed" if confirmed else "error.general",
            terminal=True,
            details={"status": MissionStatus.COMPLETED.value if confirmed else MissionStatus.FAILED.value},
        )


class DeliveryExecutor(BaseMissionExecutor):
    def create_execution(self, mission: Mission, context: ExecutorContext) -> BaseMissionExecution:
        return DeliveryExecution(mission, context)
