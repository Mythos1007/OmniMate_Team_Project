from __future__ import annotations

from assistant_robot.executors.base import BaseMissionExecution, BaseMissionExecutor, ExecutorContext
from assistant_robot.models.enums import MissionStatus
from assistant_robot.models.mission import Mission
from assistant_robot.models.mission_result import MissionEvent


class WeatherTTSExecution(BaseMissionExecution):
    """기능: 이동 없이 날씨 정보를 조회하고 TTS 문구 key로 완료 이벤트를 반환 기능."""

    def __init__(self, mission: Mission, context: ExecutorContext) -> None:
        super().__init__(mission, context)
        self._done = False

    def step(self) -> MissionEvent:
        # step 기반 실행기라서 한 번 완료 후 재호출되면 terminal completed를 유지 기능.
        if self._done:
            return MissionEvent(
                mission_id=self.mission.mission_id,
                event_type="completed",
                terminal=True,
                details={"status": MissionStatus.COMPLETED.value},
            )
        weather = self.context.weather_provider.get_current_weather(
            location_name=self.mission.target_location,
        )
        payload = self.context.weather_formatter.build_tts_payload(weather)
        self._done = True
        return MissionEvent(
            mission_id=self.mission.mission_id,
            event_type="completed",
            message_key="weather.current_summary",
            message_params=payload,
            terminal=True,
            details={"status": MissionStatus.COMPLETED.value, "weather": payload},
        )


class WeatherTTSExecutor(BaseMissionExecutor):
    def create_execution(self, mission: Mission, context: ExecutorContext) -> BaseMissionExecution:
        return WeatherTTSExecution(mission, context)
