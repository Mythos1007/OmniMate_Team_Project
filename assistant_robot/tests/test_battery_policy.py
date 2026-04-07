from __future__ import annotations

from assistant_robot.models.command_request import CommandRequest
from assistant_robot.models.enums import CommandSource, MissionType, TopState
from assistant_robot.models.robot_state import RobotState
from assistant_robot.orchestrator.battery_policy import BatteryPolicy


def test_low_battery_rejects_movement_command() -> None:
    policy = BatteryPolicy(low_battery_threshold=20.0)
    state = RobotState(top_state=TopState.LOW_BATTERY_RESTRICTED, low_battery_restricted=True, battery_level=10.0)
    command = CommandRequest(
        source=CommandSource.VOICE,
        parsed_intent={"intent_name": MissionType.CALL.value},
        requires_movement=True,
        target_location="회의실 A",
    )

    accepted, reason = policy.can_accept_command(command, state)

    assert accepted is False
    assert reason == "battery.low_reject_move"


def test_low_battery_allows_non_move_query() -> None:
    policy = BatteryPolicy(low_battery_threshold=20.0)
    state = RobotState(top_state=TopState.LOW_BATTERY_RESTRICTED, low_battery_restricted=True, battery_level=10.0)
    command = CommandRequest(
        source=CommandSource.VOICE,
        parsed_intent={"intent_name": MissionType.WEATHER_TTS.value},
        requires_movement=False,
    )

    accepted, reason = policy.can_accept_command(command, state)

    assert accepted is True
    assert reason == "queue.accepted"
