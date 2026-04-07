from __future__ import annotations

from assistant_robot.interfaces.tts_provider import BaseTTSProvider, TTSRequest


class MockTTSProvider(BaseTTSProvider):
    def __init__(self) -> None:
        self.requests: list[TTSRequest] = []

    def speak(self, request: TTSRequest) -> None:
        self.requests.append(request)

    def stop(self) -> None:
        self.requests.append(TTSRequest(text="__STOP__", interrupt=True))
