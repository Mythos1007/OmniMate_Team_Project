from __future__ import annotations

from assistant_robot.demo import build_mock_orchestrator
from assistant_robot.interfaces.weather_provider import WeatherData
from assistant_robot.services.weather_formatter import WeatherFormatter
from assistant_robot.models.command_request import CommandRequest
from assistant_robot.models.enums import CommandSource, MissionType


def test_weather_formatter_builds_natural_korean_sentence() -> None:
    formatter = WeatherFormatter()
    weather = WeatherData(
        temperature_c=23.0,
        condition="흐림",
        humidity_percent=55,
        rain_probability_percent=40,
        summary="흐리고 비 가능성이 있습니다",
    )

    sentence = formatter.format_for_tts(weather)

    assert "현재 기온은 23도" in sentence
    assert "강수 확률은 40퍼센트" in sentence


def test_weather_tts_executor_uses_script_repository() -> None:
    orchestrator, tts_provider = build_mock_orchestrator()
    command = CommandRequest(
        source=CommandSource.VOICE,
        parsed_intent={"intent_name": MissionType.WEATHER_TTS.value},
        requires_movement=False,
    )

    orchestrator.submit_command(command)
    orchestrator.tick()

    assert any(request.text.startswith("현재 기온은 23도") for request in tts_provider.requests)
