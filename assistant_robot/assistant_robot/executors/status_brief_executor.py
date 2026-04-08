from __future__ import annotations

from assistant_robot.executors.base import BaseMissionExecution, BaseMissionExecutor, ExecutorContext
from assistant_robot.models.enums import MissionStatus
from assistant_robot.models.mission import Mission
from assistant_robot.models.mission_result import MissionEvent


class StatusBriefExecution(BaseMissionExecution):
    """기능: 이동 없이 현재 위치/상태를 짧게 음성 안내 기능."""

    def step(self) -> MissionEvent:
        action = str(self.mission.payload.get("action", "")).strip()
        source_text = str(self.mission.payload.get("source_text", "")).strip()
        runtime_data = self.context.runtime_data_service
        if runtime_data is not None:
            if action == "schedule_info":
                return MissionEvent(
                    mission_id=self.mission.mission_id,
                    event_type="completed",
                    terminal=True,
                    details={
                        "status": MissionStatus.COMPLETED.value,
                        "speak_text": runtime_data.build_schedule_summary(source_text),
                    },
                )
            if action in {"alarm_set", "alarm_add"}:
                return MissionEvent(
                    mission_id=self.mission.mission_id,
                    event_type="completed",
                    terminal=True,
                    details={
                        "status": MissionStatus.COMPLETED.value,
                        "speak_text": runtime_data.add_alarm_from_text(source_text),
                    },
                )
            if action == "alarm_info":
                return MissionEvent(
                    mission_id=self.mission.mission_id,
                    event_type="completed",
                    terminal=True,
                    details={
                        "status": MissionStatus.COMPLETED.value,
                        "speak_text": runtime_data.build_alarm_summary(source_text),
                    },
                )
            if action == "medication_info":
                return MissionEvent(
                    mission_id=self.mission.mission_id,
                    event_type="completed",
                    terminal=True,
                    details={
                        "status": MissionStatus.COMPLETED.value,
                        "speak_text": runtime_data.build_medication_summary(source_text),
                    },
                )
            if action == "schedule_add":
                return MissionEvent(
                    mission_id=self.mission.mission_id,
                    event_type="completed",
                    terminal=True,
                    details={
                        "status": MissionStatus.COMPLETED.value,
                        "speak_text": runtime_data.add_schedule_from_text(source_text),
                    },
                )
            if action == "medication_add":
                return MissionEvent(
                    mission_id=self.mission.mission_id,
                    event_type="completed",
                    terminal=True,
                    details={
                        "status": MissionStatus.COMPLETED.value,
                        "speak_text": runtime_data.add_medication_from_text(source_text),
                    },
                )

        if action == "schedule_info":
            return MissionEvent(
                mission_id=self.mission.mission_id,
                event_type="completed",
                message_key="status.schedule_summary",
                terminal=True,
                details={"status": MissionStatus.COMPLETED.value},
            )
        if action == "alarm_set":
            return MissionEvent(
                mission_id=self.mission.mission_id,
                event_type="completed",
                message_key="status.alarm_set",
                terminal=True,
                details={"status": MissionStatus.COMPLETED.value},
            )
        if action == "alarm_info":
            return MissionEvent(
                mission_id=self.mission.mission_id,
                event_type="completed",
                message_key="status.alarm_summary",
                terminal=True,
                details={"status": MissionStatus.COMPLETED.value},
            )
        if action == "medication_info":
            return MissionEvent(
                mission_id=self.mission.mission_id,
                event_type="completed",
                message_key="status.medication_summary",
                terminal=True,
                details={"status": MissionStatus.COMPLETED.value},
            )
        if action == "wakeword_ack":
            return MissionEvent(
                mission_id=self.mission.mission_id,
                event_type="completed",
                message_key="status.wakeword_ack",
                terminal=True,
                details={"status": MissionStatus.COMPLETED.value},
            )
        if action == "cancel_request":
            return MissionEvent(
                mission_id=self.mission.mission_id,
                event_type="completed",
                message_key="status.cancel_requested",
                terminal=True,
                details={"status": MissionStatus.COMPLETED.value},
            )

        destination = str(self.mission.payload.get("active_destination", "")).strip()
        if destination:
            return MissionEvent(
                mission_id=self.mission.mission_id,
                event_type="completed",
                message_key="status.current_destination",
                message_params={"target_location": destination},
                terminal=True,
                details={"status": MissionStatus.COMPLETED.value},
            )

        current_location = self.context.navigation_controller.get_current_location()
        return MissionEvent(
            mission_id=self.mission.mission_id,
            event_type="completed",
            message_key="status.current_location",
            message_params={"current_location": current_location},
            terminal=True,
            details={"status": MissionStatus.COMPLETED.value},
        )


class StatusBriefExecutor(BaseMissionExecutor):
    def create_execution(self, mission: Mission, context: ExecutorContext) -> BaseMissionExecution:
        return StatusBriefExecution(mission, context)
