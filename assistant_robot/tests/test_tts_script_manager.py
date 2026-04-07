from __future__ import annotations

from assistant_robot.services.tts_script_manager import TTSScriptManager


def test_get_message_with_placeholder() -> None:
    manager = TTSScriptManager(profile="default")

    message = manager.get_message("call.start", user_name="민수")

    assert message == "민수님 위치로 이동하겠습니다."


def test_missing_key_returns_fallback() -> None:
    manager = TTSScriptManager(profile="default")

    message = manager.get_message("does.not.exist")

    assert "문제가 발생했습니다" in message


def test_round_robin_selection_for_multiple_candidates() -> None:
    manager = TTSScriptManager(profile="default")

    first = manager.get_random_message("weather.current_summary", temperature=23, weather_summary="흐림")
    second = manager.get_random_message("weather.current_summary", temperature=23, weather_summary="흐림")

    assert first != second
    assert "23도" in first
    assert "23도" in second
