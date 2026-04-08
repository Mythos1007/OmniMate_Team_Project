from __future__ import annotations

from assistant_robot.adapters.mock_confirmation_service import MockConfirmationService
from assistant_robot.adapters.compatibility_data_loader import CompatibilityDataLoader
from assistant_robot.adapters.mock_navigation_controller import MockNavigationController
from assistant_robot.adapters.mock_weather_provider import MockWeatherProvider
from assistant_robot.adapters.mock_intent_parser import MockIntentParser
from assistant_robot.adapters.place_resolving_navigation_controller import PlaceResolvingNavigationController
from assistant_robot.executors.base import ExecutorContext
from assistant_robot.executors.medication_executor import MedicationExecution
from assistant_robot.models.enums import CommandSource, MissionType, MissionStatus
from assistant_robot.models.command_request import CommandRequest
from assistant_robot.models.mission import Mission
from assistant_robot.services.place_catalog import PlaceCatalog
from assistant_robot.services.weather_formatter import WeatherFormatter


def test_compatibility_data_loader_reads_literal_waypoints_and_alarm_entries() -> None:
    loader = CompatibilityDataLoader()

    waypoints = loader.load_waypoints()
    alarms = loader.load_alarm_entries()
    places = loader.load_places()

    assert "영업팀" in waypoints
    assert any(item.get("target_place") == "khj" for item in alarms)
    assert "home" in places


def test_place_resolving_navigation_controller_resolves_compact_aliases() -> None:
    controller = PlaceResolvingNavigationController(
        MockNavigationController(),
        place_catalog=PlaceCatalog(),
    )

    handle = controller.start_navigation(" 영업팀 ")

    assert handle.target_location == "영업팀"
    assert handle.metadata["requested_target"] == " 영업팀 "
    assert handle.metadata["resolved_target"] == "영업팀"


def test_scheduler_encoded_command_is_parsed_with_payload() -> None:
    parser = MockIntentParser()

    result = parser.parse("[SCHED]|medication|아침|khj|아침 약 드세요")

    assert result.primary_command is not None
    assert result.primary_command.source == CommandSource.SCHEDULER
    assert result.primary_command.mission_type == MissionType.MEDICATION
    assert result.primary_command.target_location == "khj"
    assert result.primary_command.target_user == "아침"
    assert result.primary_command.payload["announcement_text"] == "아침 약 드세요"


def test_medication_execution_supports_navigation_before_confirmation() -> None:
    context = ExecutorContext(
        navigation_controller=MockNavigationController(steps_per_navigation=1),
        confirmation_service=MockConfirmationService(default_result=True),
        weather_provider=MockWeatherProvider(),
        weather_formatter=WeatherFormatter(),
        logger=__import__("logging").getLogger(__name__),
    )
    command = CommandRequest(
        source=CommandSource.SCHEDULER,
        parsed_intent={"intent_name": MissionType.MEDICATION.value},
        requires_movement=True,
        target_user="아침",
        target_location="khj",
        payload={"announcement_text": "아침 약 드세요"},
    )
    mission = Mission.from_command(command)
    execution = MedicationExecution(mission, context)

    started = execution.step()
    navigating = execution.step()
    arrived = execution.step()
    waiting = execution.step()
    completed = execution.step()

    assert started.event_type == "started"
    assert navigating.event_type == "navigating"
    assert arrived.event_type == "arrived"
    assert waiting.event_type == "waiting_confirmation"
    assert waiting.details["speak_text"] == "아침 약 드세요"
    assert completed.details["status"] == MissionStatus.COMPLETED.value
