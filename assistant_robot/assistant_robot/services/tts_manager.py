from __future__ import annotations

from assistant_robot.interfaces.tts_provider import BaseTTSProvider, TTSRequest
from assistant_robot.models.enums import TtsPriority
from assistant_robot.services.tts_script_manager import TTSScriptManager


class TTSManager:
    def __init__(self, provider: BaseTTSProvider, script_manager: TTSScriptManager) -> None:
        self.provider = provider
        self.script_manager = script_manager

    def speak(self, text: str, *, priority: TtsPriority = TtsPriority.NORMAL, interrupt: bool = False) -> None:
        self.provider.speak(TTSRequest(text=text, priority=priority, interrupt=interrupt))

    def speak_message(
        self,
        key: str,
        *,
        priority: TtsPriority = TtsPriority.NORMAL,
        interrupt: bool = False,
        **kwargs: object,
    ) -> str:
        text = self.script_manager.format_message(key, **kwargs)
        self.speak(text, priority=priority, interrupt=interrupt)
        return text

    def stop(self) -> None:
        self.provider.stop()
