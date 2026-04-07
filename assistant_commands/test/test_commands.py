from __future__ import annotations

from assistant_commands.command_normalizer import CommandNormalizer

import pytest


@pytest.fixture
def normalizer() -> CommandNormalizer:
    return CommandNormalizer()


@pytest.mark.parametrize(
    ("text", "expected_command", "expected_args"),
    [
        ("앞으로 가", "move_forward", {}),
        ("전진해", "move_forward", {}),
        ("직진해", "move_forward", {}),
        ("뒤로 가", "move_backward", {}),
        ("후진해", "move_backward", {}),
        ("왼쪽으로 돌아", "turn_left", {}),
        ("좌회전해", "turn_left", {}),
        ("오른쪽으로 돌아", "turn_right", {}),
        ("우회전해", "turn_right", {}),
        ("멈춰", "stop", {}),
        ("정지", "stop", {}),
        ("순찰 시작해", "start_patrol", {}),
        ("순찰 멈춰", "pause_patrol", {}),
        ("순찰 재개해", "resume_patrol", {}),
        ("현재 상태 알려줘", "status_query", {}),
        ("앞으로 1미터 가", "move_forward", {"distance": 1.0, "unit": "meter"}),
        ("3초 동안 전진해", "move_forward", {"duration": 3.0, "unit": "second"}),
        ("이상한 문장", "unknown", {"original_text": "이상한 문장"}),
    ],
)
def test_normalize_commands(
    normalizer: CommandNormalizer,
    text: str,
    expected_command: str,
    expected_args: dict[str, object],
) -> None:
    result = normalizer.normalize(text)

    assert result.command == expected_command
    assert result.to_dict()["args"] == expected_args


def test_longer_patrol_phrase_wins_over_generic_stop(normalizer: CommandNormalizer) -> None:
    result = normalizer.normalize("지금 순찰 멈춰")

    assert result.command == "pause_patrol"


def test_whitespace_is_normalized(normalizer: CommandNormalizer) -> None:
    result = normalizer.normalize("  앞으로   1미터   가  ")

    assert result.command == "move_forward"
    assert result.args == {"distance": 1.0, "unit": "meter"}
