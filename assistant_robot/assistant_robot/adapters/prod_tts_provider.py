from __future__ import annotations

import logging

from assistant_robot.interfaces.tts_provider import BaseTTSProvider, TTSRequest


class DemoProdTTSProvider(BaseTTSProvider):
    def __init__(self, logger: logging.Logger | None = None) -> None:
        self._logger = logger or logging.getLogger(__name__)

    def speak(self, request: TTSRequest) -> None:
        # TODO: Replace this placeholder with a production TTS SDK such as Azure Speech.
        self._logger.info("[DEMO TTS][%s] %s", request.priority.value, request.text)

    def stop(self) -> None:
        self._logger.info("[DEMO TTS] stop")
