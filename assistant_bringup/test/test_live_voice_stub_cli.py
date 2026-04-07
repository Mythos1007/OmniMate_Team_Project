from __future__ import annotations

from assistant_bringup.live_voice_stub_cli import build_auxiliary_normalizer, resolve_command
from assistant_commands import CommandNormalizer


def test_auxiliary_normalizer_handles_weather_paraphrase() -> None:
    command, fallback_result = resolve_command(
        '오늘 비 올까?',
        CommandNormalizer(),
        build_auxiliary_normalizer('heuristic'),
    )

    assert fallback_result is None
    assert command.command == 'weather_query'


def test_auxiliary_normalizer_handles_alarm_paraphrase() -> None:
    command, fallback_result = resolve_command(
        '내일 아침 7시에 깨워줘',
        CommandNormalizer(),
        build_auxiliary_normalizer('heuristic'),
    )

    assert fallback_result is None
    assert command.command == 'alarm_create'
    assert command.args['time'] == '07:00'


def test_auxiliary_normalizer_handles_guidance_paraphrase() -> None:
    command, fallback_result = resolve_command(
        '회의실로 데려다줘',
        CommandNormalizer(),
        build_auxiliary_normalizer('heuristic'),
    )

    assert fallback_result is None
    assert command.command == 'guide_to_location'
    assert command.args['location'] == '회의실'
