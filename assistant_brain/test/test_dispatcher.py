from __future__ import annotations

from assistant_brain.command_dispatcher import CommandDispatcher
from assistant_commands import CanonicalCommand


def test_motion_command_dispatches_to_motion_handler() -> None:
    dispatcher = CommandDispatcher()

    result = dispatcher.dispatch(
        CanonicalCommand(command='move_forward', args={'distance': 1.0, 'unit': 'meter'})
    )

    assert result.handled is True
    assert result.status_text == '[EXECUTE] Moving forward for 1.0 meter'
    assert result.speak_text == '앞으로 1.0 meter 이동할게요.'


def test_alarm_create_and_list_uses_in_memory_store() -> None:
    dispatcher = CommandDispatcher()

    create_result = dispatcher.dispatch(
        CanonicalCommand(command='alarm_create', args={'time': '07:30', 'label': '기상'})
    )
    list_result = dispatcher.dispatch(CanonicalCommand(command='alarm_list'))

    assert create_result.status_text == '[STUB] Alarm saved: 07:30 기상'
    assert list_result.status_text == '[STUB] Alarm list: 07:30 기상'


def test_schedule_create_and_list_uses_in_memory_store() -> None:
    dispatcher = CommandDispatcher()

    create_result = dispatcher.dispatch(
        CanonicalCommand(
            command='schedule_create',
            args={'date': '내일', 'time': '10:00', 'title': '팀 미팅'},
        )
    )
    list_result = dispatcher.dispatch(CanonicalCommand(command='schedule_list'))

    assert create_result.status_text == '[STUB] Schedule saved: 내일 10:00 팀 미팅'
    assert list_result.status_text == '[STUB] Schedule list: 내일 10:00 팀 미팅'


def test_weather_query_returns_stub_snapshot() -> None:
    dispatcher = CommandDispatcher()

    result = dispatcher.dispatch(CanonicalCommand(command='weather_query'))

    assert result.handled is True
    assert result.speak_text == '현재 날씨는 맑음, 23도입니다.'


def test_navigation_commands_record_stub_state() -> None:
    dispatcher = CommandDispatcher()

    guide_result = dispatcher.dispatch(
        CanonicalCommand(command='guide_to_location', args={'location': '회의실'})
    )
    deliver_result = dispatcher.dispatch(
        CanonicalCommand(command='deliver_mail', args={'item': '우편물', 'destination': '안내데스크'})
    )

    assert guide_result.status_text == '[STUB] Guidance requested to 회의실'
    assert deliver_result.status_text == '[STUB] Delivery queued: 우편물 -> 안내데스크'
    assert dispatcher.registry.guidance_history == ['회의실']
    assert len(dispatcher.registry.delivery_requests) == 1


def test_unknown_dispatch_returns_unhandled_result() -> None:
    dispatcher = CommandDispatcher()

    result = dispatcher.dispatch(CanonicalCommand(command='unknown', args={'original_text': '테스트'}))

    assert result.handled is False
    assert result.speak_text == '아직 연결되지 않은 명령이에요.'
