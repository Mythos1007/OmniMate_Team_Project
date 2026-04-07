from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta


@dataclass(slots=True)
class GreetingManager:
    cooldown_seconds: int = 60
    _last_greeted: dict[str, datetime] = field(default_factory=dict)

    def should_greet(self, user_name: str, *, now: datetime) -> bool:
        last_seen = self._last_greeted.get(user_name)
        if last_seen is not None and now - last_seen < timedelta(seconds=self.cooldown_seconds):
            return False
        self._last_greeted[user_name] = now
        return True
