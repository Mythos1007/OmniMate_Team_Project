from __future__ import annotations

from datetime import datetime
import logging

from assistant_robot.adapters.mock_confirmation_service import MockConfirmationService
from assistant_robot.adapters.mock_intent_parser import MockIntentParser
from assistant_robot.adapters.mock_navigation_controller import MockNavigationController
from assistant_robot.adapters.mock_tts_provider import MockTTSProvider
from assistant_robot.adapters.mock_weather_provider import MockWeatherProvider
from assistant_robot.executors.alarm_executor import AlarmExecutor
from assistant_robot.executors.call_executor import CallExecutor
from assistant_robot.executors.delivery_executor import DeliveryExecutor
from assistant_robot.executors.medication_executor import MedicationExecutor
from assistant_robot.executors.return_to_base_executor import ReturnToBaseExecutor
from assistant_robot.executors.status_brief_executor import StatusBriefExecutor
from assistant_robot.executors.weather_tts_executor import WeatherTTSExecutor
from assistant_robot.executors.base import ExecutorContext
from assistant_robot.orchestrator.battery_policy import BatteryPolicy
from assistant_robot.orchestrator.mission_dispatcher import MissionDispatcher
from assistant_robot.orchestrator.mission_queue import MissionQueue
from assistant_robot.orchestrator.next_mission_resolver import NextMissionResolver
from assistant_robot.orchestrator.omni_orchestrator import OmniOrchestrator
from assistant_robot.orchestrator.state_machine import RobotStateMachine
from assistant_robot.services.greeting_manager import GreetingManager
from assistant_robot.services.tts_manager import TTSManager
from assistant_robot.services.tts_script_manager import TTSScriptManager
from assistant_robot.services.weather_formatter import WeatherFormatter


def build_mock_orchestrator(*, tts_profile: str = "default") -> tuple[OmniOrchestrator, MockTTSProvider]:
    """기능: 실제 외부 모듈 없이 전체 흐름을 검증할 수 있는 조립 함수."""

    logger = logging.getLogger("assistant_robot.demo")
    queue = MissionQueue()
    battery_policy = BatteryPolicy()
    state_machine = RobotStateMachine(battery_policy)
    tts_provider = MockTTSProvider()
    script_manager = TTSScriptManager(profile=tts_profile)
    tts_manager = TTSManager(tts_provider, script_manager)
    context = ExecutorContext(
        # TODO: 조원 코드가 준비되면 아래 mock들을 실제 adapter 구현으로 교체.
        navigation_controller=MockNavigationController(),
        confirmation_service=MockConfirmationService(),
        weather_provider=MockWeatherProvider(),
        weather_formatter=WeatherFormatter(),
        logger=logger,
    )
    dispatcher = MissionDispatcher(
        {
            "delivery": DeliveryExecutor(),
            "call": CallExecutor(),
            "alarm": AlarmExecutor(),
            "medication": MedicationExecutor(),
            "weather_tts": WeatherTTSExecutor(),
            "status_brief": StatusBriefExecutor(),
            "return_to_base": ReturnToBaseExecutor(),
        },
        context,
    )
    orchestrator = OmniOrchestrator(
        mission_queue=queue,
        state_machine=state_machine,
        battery_policy=battery_policy,
        dispatcher=dispatcher,
        next_mission_resolver=NextMissionResolver(queue, battery_policy),
        intent_parser=MockIntentParser(),
        tts_manager=tts_manager,
        greeting_manager=GreetingManager(),
        logger=logger,
    )
    orchestrator.update_battery(battery_level=85.0, charging=False)
    return orchestrator, tts_provider


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    orchestrator, tts_provider = build_mock_orchestrator(tts_profile="demo")
    # 기능 데모: 이동 명령과 non-move 날씨 명령을 순차 투입 기능.
    orchestrator.ingest_voice_text("옴니야 회의실 A로 가줘")
    orchestrator.ingest_voice_text("옴니야 오늘 날씨 알려줘")

    for _ in range(8):
        result = orchestrator.tick()
        if result is not None:
            logging.info("tick result: %s", result)

    logging.info("state: %s", orchestrator.state)
    logging.info("tts outputs: %s", [request.text for request in tts_provider.requests])


if __name__ == "__main__":
    main()
