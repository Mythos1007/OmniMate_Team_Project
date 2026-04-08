from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from assistant_robot.demo import build_mock_orchestrator
from assistant_robot.models.command_request import CommandRequest
from assistant_robot.models.enums import CommandSource, MissionType


def make_command(mission_type: MissionType, *, target_location: str | None = None, requires_movement: bool = True) -> CommandRequest:
    return CommandRequest(
        source=CommandSource.GUI,
        parsed_intent={"intent_name": mission_type.value, "requires_confirmation": mission_type == MissionType.DELIVERY},
        requires_movement=requires_movement,
        target_location=target_location,
    )


def test_new_mission_is_queued_while_delivery_running() -> None:
    orchestrator, _ = build_mock_orchestrator()
    orchestrator.submit_command(make_command(MissionType.DELIVERY, target_location="회의실 A"))
    orchestrator.submit_command(make_command(MissionType.CALL, target_location="로비"))

    assert orchestrator.active_mission is not None
    assert orchestrator.active_mission.mission_type == MissionType.DELIVERY
    assert orchestrator.state.pending_count == 1


def test_next_mission_auto_dispatches_after_completion() -> None:
    orchestrator, _ = build_mock_orchestrator()
    orchestrator.submit_command(make_command(MissionType.DELIVERY, target_location="회의실 A"))
    orchestrator.submit_command(make_command(MissionType.CALL, target_location="로비"))

    for _ in range(6):
        orchestrator.tick()

    assert orchestrator.active_mission is not None
    assert orchestrator.active_mission.mission_type == MissionType.CALL


def test_low_battery_restricted_rejects_move_but_allows_weather() -> None:
    orchestrator, _ = build_mock_orchestrator()
    orchestrator.update_battery(battery_level=10.0, charging=False)

    rejected = orchestrator.submit_command(make_command(MissionType.CALL, target_location="로비"))
    accepted = orchestrator.submit_command(make_command(MissionType.WEATHER_TTS, requires_movement=False))

    assert rejected.accepted is False
    assert accepted.accepted is True
    assert orchestrator.active_mission is not None
    assert orchestrator.active_mission.mission_type == MissionType.WEATHER_TTS


def test_multi_command_voice_keeps_only_first() -> None:
    orchestrator, tts_provider = build_mock_orchestrator()

    decision, parse_result = orchestrator.ingest_voice_text("옴니야 오늘 날씨 알려줘 그리고 회의실 A로 가줘")

    assert decision.accepted is True
    assert parse_result.primary_command is not None
    assert parse_result.primary_command.mission_type == MissionType.WEATHER_TTS
    assert len(parse_result.rejected_commands) == 1
    assert any("한 번에 하나의 요청만 처리" in request.text for request in tts_provider.requests)


def test_greeting_overlay_does_not_interrupt_current_mission() -> None:
    orchestrator, tts_provider = build_mock_orchestrator()
    orchestrator.submit_command(make_command(MissionType.DELIVERY, target_location="회의실 A"))
    active_mission_id = orchestrator.active_mission.mission_id if orchestrator.active_mission else None

    greeted = orchestrator.handle_face_recognized("민수", now=datetime.utcnow())
    greeted_again = orchestrator.handle_face_recognized("민수", now=datetime.utcnow() + timedelta(seconds=10))

    assert greeted is True
    assert greeted_again is False
    assert orchestrator.active_mission is not None
    assert orchestrator.active_mission.mission_id == active_mission_id
    assert any("민수님" in request.text for request in tts_provider.requests)


def test_where_are_you_command_is_supported() -> None:
    orchestrator, tts_provider = build_mock_orchestrator()

    decision, parse_result = orchestrator.ingest_voice_text("옴니야 어디가?")

    assert decision.accepted is True
    assert parse_result.primary_command is not None
    assert parse_result.primary_command.mission_type == MissionType.STATUS_BRIEF

    orchestrator.tick()

    assert any("현재" in request.text for request in tts_provider.requests)


def test_where_are_you_reports_destination_while_moving() -> None:
    orchestrator, tts_provider = build_mock_orchestrator()
    orchestrator.submit_command(make_command(MissionType.CALL, target_location="회의실 A"))
    request_count_before = len(tts_provider.requests)

    orchestrator.ingest_voice_text("옴니야 어디가?")

    assert any(
        "회의실 A" in request.text and ("이동" in request.text or "가고" in request.text)
        for request in tts_provider.requests[request_count_before:]
    )
    assert orchestrator.active_mission is not None
    assert orchestrator.active_mission.mission_type == MissionType.CALL
    assert orchestrator.state.pending_count == 0


def test_weather_tts_runs_as_overlay_while_delivery_running() -> None:
    orchestrator, tts_provider = build_mock_orchestrator()
    orchestrator.submit_command(make_command(MissionType.DELIVERY, target_location="회의실 A"))
    request_count_before = len(tts_provider.requests)

    decision = orchestrator.submit_command(make_command(MissionType.WEATHER_TTS, requires_movement=False))

    assert decision.accepted is True
    assert decision.reason == "overlay_executed"
    assert orchestrator.active_mission is not None
    assert orchestrator.active_mission.mission_type == MissionType.DELIVERY
    assert orchestrator.state.pending_count == 0
    assert any("현재 기온은 23도" in request.text for request in tts_provider.requests[request_count_before:])


def test_schedule_status_runs_as_overlay_while_delivery_running() -> None:
    orchestrator, tts_provider = build_mock_orchestrator()
    orchestrator.submit_command(make_command(MissionType.DELIVERY, target_location="회의실 A"))
    request_count_before = len(tts_provider.requests)

    decision, parse_result = orchestrator.ingest_voice_text("옴니야 일정 알려줘")

    assert decision.accepted is True
    assert decision.reason == "overlay_executed"
    assert parse_result.primary_command is not None
    assert parse_result.primary_command.mission_type == MissionType.STATUS_BRIEF
    assert orchestrator.active_mission is not None
    assert orchestrator.active_mission.mission_type == MissionType.DELIVERY
    assert orchestrator.state.pending_count == 0
    assert any("일정" in request.text for request in tts_provider.requests[request_count_before:])


@pytest.mark.parametrize(
    ("utterance", "expected_fragment"),
    [
        ("옴니야 알람 맞춰줘", "알람"),
        ("옴니야 알람 알려줘", "알람"),
        ("옴니야 복약 확인해줘", "복약"),
        ("옴니", "듣고"),
    ],
)
def test_all_current_tts_only_status_commands_run_as_overlay_while_moving(
    utterance: str,
    expected_fragment: str,
) -> None:
    orchestrator, tts_provider = build_mock_orchestrator()
    orchestrator.submit_command(make_command(MissionType.DELIVERY, target_location="회의실 A"))
    request_count_before = len(tts_provider.requests)

    decision, parse_result = orchestrator.ingest_voice_text(utterance)

    assert decision.accepted is True
    assert decision.reason == "overlay_executed"
    assert parse_result.primary_command is not None
    assert parse_result.primary_command.mission_type == MissionType.STATUS_BRIEF
    assert orchestrator.active_mission is not None
    assert orchestrator.active_mission.mission_type == MissionType.DELIVERY
    assert orchestrator.state.pending_count == 0
    assert any(expected_fragment in request.text for request in tts_provider.requests[request_count_before:])


def test_cancel_request_cancels_active_navigation_mission() -> None:
    orchestrator, tts_provider = build_mock_orchestrator()
    orchestrator.submit_command(make_command(MissionType.CALL, target_location="회의실 A"))

    decision, parse_result = orchestrator.ingest_voice_text("옴니야 취소해줘")

    assert decision.accepted is True
    assert decision.reason == "cancelled_active_mission"
    assert parse_result.primary_command is not None
    assert orchestrator.active_mission is None
    assert any("취소" in request.text for request in tts_provider.requests)


def test_guide_me_phrase_is_parsed_as_call_command() -> None:
    orchestrator, _ = build_mock_orchestrator()

    decision, parse_result = orchestrator.ingest_voice_text("옴니야 회의실 A 안내해줘")

    assert decision.accepted is True
    assert parse_result.primary_command is not None
    assert parse_result.primary_command.mission_type == MissionType.CALL
    assert parse_result.primary_command.target_location == "회의실 A"


def test_schedule_alarm_cancel_medication_commands_are_supported() -> None:
    orchestrator, tts_provider = build_mock_orchestrator()

    cases = [
        "옴니야 일정 알려줘",
        "옴니야 알람 맞춰줘",
        "옴니야 알람 알려줘",
        "옴니야 복약 확인해줘",
        "옴니야 취소해줘",
    ]
    for utterance in cases:
        decision, parse_result = orchestrator.ingest_voice_text(utterance)
        assert decision.accepted is True
        assert parse_result.primary_command is not None
        assert parse_result.primary_command.mission_type == MissionType.STATUS_BRIEF
        orchestrator.tick()

    spoken = [request.text for request in tts_provider.requests]
    assert any("일정" in text for text in spoken)
    assert any("알람" in text for text in spoken)
    assert any("복약" in text for text in spoken)
    assert any("취소" in text for text in spoken)


def test_wakeword_only_is_recognized_without_command() -> None:
    orchestrator, tts_provider = build_mock_orchestrator()

    decision, parse_result = orchestrator.ingest_voice_text("옴니")

    assert decision.accepted is True
    assert parse_result.primary_command is not None
    assert parse_result.primary_command.mission_type == MissionType.STATUS_BRIEF
    orchestrator.tick()
    assert any("듣고" in request.text or "호출어" in request.text for request in tts_provider.requests)
