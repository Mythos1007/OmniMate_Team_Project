from __future__ import annotations

from assistant_robot.executors.base import BaseMissionExecution, BaseMissionExecutor, ExecutorContext
from assistant_robot.models.mission import Mission


class MissionDispatcher:
    """미션 타입별 executor 선택 및 실행 인스턴스 생성 기능."""

    def __init__(self, executors: dict[str, BaseMissionExecutor], context: ExecutorContext) -> None:
        self._executors = executors
        self._context = context

    def dispatch(self, mission: Mission) -> BaseMissionExecution:
        """mission_type 기반 executor 조회 후 실행 객체 반환 기능."""
        executor = self._executors.get(mission.mission_type.value)
        if executor is None:
            raise KeyError(f"No executor registered for mission type: {mission.mission_type.value}")
        return executor.create_execution(mission, self._context)
