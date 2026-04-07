from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class AlarmEntry:
    """알람 저장 항목."""

    time: str
    label: str


@dataclass(slots=True)
class ScheduleEntry:
    """일정 저장 항목."""

    title: str
    date: str
    time: str


@dataclass(slots=True)
class DeliveryEntry:
    """우편/물품 전달 요청 저장 항목."""

    item: str
    destination: str


@dataclass(slots=True)
class InMemoryServiceRegistry:
    """브레인 핸들러들이 공유하는 인메모리 저장소.

    실제 DB/외부 서비스 연동 전까지 상태를 메모리에 보관한다.
    """

    weather_summary: str = '현재 날씨는 맑음, 23도입니다.'
    alarms: list[AlarmEntry] = field(default_factory=list)
    schedules: list[ScheduleEntry] = field(default_factory=list)
    delivery_requests: list[DeliveryEntry] = field(default_factory=list)
    guidance_history: list[str] = field(default_factory=list)

    def add_alarm(self, time: str, label: str) -> AlarmEntry:
        entry = AlarmEntry(time=time, label=label)
        self.alarms.append(entry)
        return entry

    def list_alarms(self) -> list[AlarmEntry]:
        return list(self.alarms)

    def add_schedule(self, title: str, date: str, time: str) -> ScheduleEntry:
        entry = ScheduleEntry(title=title, date=date, time=time)
        self.schedules.append(entry)
        return entry

    def list_schedules(self) -> list[ScheduleEntry]:
        return list(self.schedules)

    def add_delivery_request(self, item: str, destination: str) -> DeliveryEntry:
        entry = DeliveryEntry(item=item, destination=destination)
        self.delivery_requests.append(entry)
        return entry

    def record_guidance(self, location: str) -> None:
        self.guidance_history.append(location)
