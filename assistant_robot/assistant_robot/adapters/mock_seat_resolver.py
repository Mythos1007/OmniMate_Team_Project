from __future__ import annotations

from assistant_robot.interfaces.seat_resolver import BaseSeatResolver


class MockSeatResolver(BaseSeatResolver):
    def __init__(self, mapping: dict[str, str] | None = None) -> None:
        self.mapping = mapping or {"민수": "회의실 A", "지은": "로비"}

    def resolve(self, user_name: str) -> str | None:
        return self.mapping.get(user_name)
