from __future__ import annotations

import logging

from assistant_robot.interfaces.tts_provider import BaseTTSProvider, TTSRequest


class DevTTSProvider(BaseTTSProvider):
    def __init__(self, logger: logging.Logger | None = None) -> None:
        self._logger = logger or logging.getLogger(__name__)

    def speak(self, request: TTSRequest) -> None:
        self._logger.info("[DEV TTS][%s] %s", request.priority.value, request.text)

    def stop(self) -> None:
        self._logger.info("[DEV TTS] stop")
