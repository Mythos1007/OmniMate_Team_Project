from __future__ import annotations

from datetime import datetime

from assistant_robot.models.mission import Mission
from assistant_robot.models.robot_state import RobotState
from assistant_robot.orchestrator.battery_policy import BatteryPolicy
from assistant_robot.orchestrator.mission_queue import MissionQueue


class NextMissionResolver:
    def __init__(self, queue: MissionQueue, battery_policy: BatteryPolicy) -> None:
        self.queue = queue
        self.battery_policy = battery_policy

    def pop_dispatchable(self, *, state: RobotState, now: datetime | None = None) -> Mission | None:
        current_time = now or datetime.utcnow()
        pending = self.queue.list_pending(now=current_time)
        for mission in pending:
            if self.battery_policy.can_dispatch_mission(mission, state):
                self._remove(mission.mission_id)
                return mission
        return None

    def peek_dispatchable(self, *, state: RobotState, now: datetime | None = None) -> Mission | None:
        current_time = now or datetime.utcnow()
        pending = self.queue.list_pending(now=current_time)
        for mission in pending:
            if self.battery_policy.can_dispatch_mission(mission, state):
                return mission
        return None

    def _remove(self, mission_id: str) -> None:
        self.queue.remove(mission_id)
