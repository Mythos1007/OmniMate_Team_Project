from __future__ import annotations

from assistant_robot.executors.base import BaseMissionExecution, BaseMissionExecutor, ExecutorContext
from assistant_robot.models.mission import Mission


class MissionDispatcher:
    def __init__(self, executors: dict[str, BaseMissionExecutor], context: ExecutorContext) -> None:
        self._executors = executors
        self._context = context

    def dispatch(self, mission: Mission) -> BaseMissionExecution:
        executor = self._executors.get(mission.mission_type.value)
        if executor is None:
            raise KeyError(f"No executor registered for mission type: {mission.mission_type.value}")
        return executor.create_execution(mission, self._context)
