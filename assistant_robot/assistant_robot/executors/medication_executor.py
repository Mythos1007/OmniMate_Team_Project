from __future__ import annotations

from assistant_robot.executors.base import BaseMissionExecution, BaseMissionExecutor, ExecutorContext
from assistant_robot.models.enums import MissionStatus
from assistant_robot.models.mission import Mission
from assistant_robot.models.mission_result import MissionEvent


class MedicationExecution(BaseMissionExecution):
    def __init__(self, mission: Mission, context: ExecutorContext) -> None:
        super().__init__(mission, context)
        self._phase = 0

    def step(self) -> MissionEvent:
        if self._phase == 0:
            self._phase = 1
            return MissionEvent(
                mission_id=self.mission.mission_id,
                event_type="started",
                message_key="medication.reminder",
                message_params={"user_name": self.mission.target_user or "사용자"},
            )
        confirmed = self.context.confirmation_service.wait_for_confirmation(mission_id=self.mission.mission_id)
        return MissionEvent(
            mission_id=self.mission.mission_id,
            event_type="completed" if confirmed else "failed",
            message_key="medication.check_completed" if confirmed else "error.general",
            terminal=True,
            details={"status": MissionStatus.COMPLETED.value if confirmed else MissionStatus.FAILED.value},
        )


class MedicationExecutor(BaseMissionExecutor):
    def create_execution(self, mission: Mission, context: ExecutorContext) -> BaseMissionExecution:
        return MedicationExecution(mission, context)
