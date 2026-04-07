from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from uuid import uuid4

from assistant_robot.models.command_request import CommandRequest
from assistant_robot.models.enums import MissionStatus, MissionType


@dataclass(slots=True)
class Mission:
    mission_id: str
    mission_type: MissionType
    priority: int
    created_at: datetime
    scheduled_for: datetime | None = None
    expires_at: datetime | None = None
    target_user: str | None = None
    target_location: str | None = None
    requires_confirmation: bool = False
    payload: dict[str, object] = field(default_factory=dict)
    status: MissionStatus = MissionStatus.PENDING
    requires_movement: bool = False

    @classmethod
    def from_command(
        cls,
        command: CommandRequest,
        *,
        priority: int = 100,
        scheduled_for: datetime | None = None,
        expires_at: datetime | None = None,
        requires_confirmation: bool = False,
    ) -> "Mission":
        return cls(
            mission_id=str(uuid4()),
            mission_type=command.mission_type,
            priority=priority,
            created_at=datetime.utcnow(),
            scheduled_for=scheduled_for,
            expires_at=expires_at,
            target_user=command.target_user,
            target_location=command.target_location,
            requires_confirmation=requires_confirmation,
            payload=dict(command.payload),
            requires_movement=command.requires_movement,
        )

    def is_ready(self, now: datetime) -> bool:
        return self.scheduled_for is None or self.scheduled_for <= now

    def is_expired(self, now: datetime) -> bool:
        return self.expires_at is not None and self.expires_at <= now
