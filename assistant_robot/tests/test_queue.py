from __future__ import annotations

from datetime import datetime, timedelta

from assistant_robot.models.enums import CommandSource, MissionType
from assistant_robot.models.command_request import CommandRequest
from assistant_robot.models.mission import Mission
from assistant_robot.orchestrator.mission_queue import MissionQueue


def make_mission(*, mission_type: MissionType, priority: int, scheduled_for: datetime | None = None) -> Mission:
    command = CommandRequest(
        source=CommandSource.GUI,
        parsed_intent={"intent_name": mission_type.value},
        requires_movement=mission_type != MissionType.WEATHER_TTS,
        target_location="회의실 A",
    )
    return Mission.from_command(command, priority=priority, scheduled_for=scheduled_for)


def test_queue_respects_priority_and_schedule() -> None:
    queue = MissionQueue()
    now = datetime.utcnow()
    later = now + timedelta(minutes=10)

    queue.push(make_mission(mission_type=MissionType.CALL, priority=100))
    queue.push(make_mission(mission_type=MissionType.ALARM, priority=300, scheduled_for=later))
    queue.push(make_mission(mission_type=MissionType.DELIVERY, priority=200))

    first = queue.pop_next(now=now)
    second = queue.pop_next(now=now)
    third = queue.pop_next(now=later + timedelta(seconds=1))

    assert first is not None and first.mission_type == MissionType.DELIVERY
    assert second is not None and second.mission_type == MissionType.CALL
    assert third is not None and third.mission_type == MissionType.ALARM


def test_queue_expires_old_missions() -> None:
    queue = MissionQueue()
    expired_mission = make_mission(mission_type=MissionType.CALL, priority=100)
    expired_mission.expires_at = datetime.utcnow() - timedelta(seconds=1)
    queue.push(expired_mission)

    expired = queue.expire_old_missions()

    assert len(expired) == 1
    assert queue.get_pending_count() == 0
