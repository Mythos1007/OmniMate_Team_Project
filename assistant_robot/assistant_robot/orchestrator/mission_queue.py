from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from threading import Lock

from assistant_robot.models.enums import MissionStatus
from assistant_robot.models.mission import Mission


class MissionQueue:
    """기능: pending mission 저장소.

    선택 규칙:
    - 우선순위(priority) 높은 순
    - scheduled_for 도달한 미션만 실행 후보
    - expires_at 지난 미션은 자동 만료 처리
    """

    def __init__(self) -> None:
        self._missions: list[Mission] = []
        self._lock = Lock()

    def push(self, mission: Mission) -> None:
        with self._lock:
            self._missions.append(mission)

    def expire_old_missions(self, *, now: datetime | None = None) -> list[Mission]:
        current_time = now or datetime.utcnow()
        expired: list[Mission] = []
        with self._lock:
            active: list[Mission] = []
            for mission in self._missions:
                if mission.is_expired(current_time):
                    expired.append(replace(mission, status=MissionStatus.EXPIRED))
                else:
                    active.append(mission)
            self._missions = active
        return expired

    def pop_next(self, *, now: datetime | None = None) -> Mission | None:
        # 기능: 현재 시점에 실행 가능한 미션 중 최우선 1개를 꺼낸다.
        current_time = now or datetime.utcnow()
        self.expire_old_missions(now=current_time)
        with self._lock:
            ready = [mission for mission in self._missions if mission.is_ready(current_time)]
            if not ready:
                return None
            chosen = sorted(ready, key=self._sort_key)[0]
            self._missions = [mission for mission in self._missions if mission.mission_id != chosen.mission_id]
        return chosen

    def peek_next(self, *, now: datetime | None = None) -> Mission | None:
        current_time = now or datetime.utcnow()
        self.expire_old_missions(now=current_time)
        with self._lock:
            ready = [mission for mission in self._missions if mission.is_ready(current_time)]
            if not ready:
                return None
            return sorted(ready, key=self._sort_key)[0]

    def list_pending(self, *, now: datetime | None = None) -> list[Mission]:
        current_time = now or datetime.utcnow()
        self.expire_old_missions(now=current_time)
        with self._lock:
            return sorted(list(self._missions), key=self._sort_key)

    def get_pending_count(self, *, now: datetime | None = None) -> int:
        return len(self.list_pending(now=now))

    def remove(self, mission_id: str) -> None:
        with self._lock:
            self._missions = [mission for mission in self._missions if mission.mission_id != mission_id]

    @staticmethod
    def _sort_key(mission: Mission) -> tuple[int, datetime, datetime, str]:
        # 확장 포인트: 같은 목적지/같은 사용자 중복 병합 규칙을 여기에 추가할 수 있다.
        scheduled_for = mission.scheduled_for or mission.created_at
        return (-mission.priority, scheduled_for, mission.created_at, mission.mission_id)
