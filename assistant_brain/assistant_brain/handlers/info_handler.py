from __future__ import annotations

from assistant_brain.dispatch_types import DispatchResult
from assistant_brain.service_registry import InMemoryServiceRegistry


class InfoHandler:
    def __init__(self, registry: InMemoryServiceRegistry) -> None:
        self._registry = registry

    def handle_weather_query(self) -> DispatchResult:
        return DispatchResult(
            handled=True,
            status_text=f'[STUB] Weather lookup result: {self._registry.weather_summary}',
            speak_text=self._registry.weather_summary,
        )
