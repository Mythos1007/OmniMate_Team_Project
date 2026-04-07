from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from assistant_robot.models.command_request import CommandRequest
from assistant_robot.models.enums import CommandSource
from assistant_robot.models.mission import Mission


@dataclass(slots=True)
class ScheduleService:
    scheduled_commands: list[tuple[datetime, CommandRequest]] = field(default_factory=list)

    def add_scheduled_command(self, when: datetime, command: CommandRequest) -> None:
        self.scheduled_commands.append((when, command))
        self.scheduled_commands.sort(key=lambda item: item[0])

    def due_missions(self, *, now: datetime) -> list[Mission]:
        due: list[Mission] = []
        remaining: list[tuple[datetime, CommandRequest]] = []
        for when, command in self.scheduled_commands:
            if when <= now:
                if command.source != CommandSource.SCHEDULER:
                    command.source = CommandSource.SCHEDULER
                due.append(Mission.from_command(command, scheduled_for=when))
            else:
                remaining.append((when, command))
        self.scheduled_commands = remaining
        return due
