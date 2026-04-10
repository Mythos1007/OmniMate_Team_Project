from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
import json
import os
from pathlib import Path
import re
from typing import Any

from assistant_robot.services.place_catalog import PlaceCatalog


_WEEKDAY_NAMES = ["월", "화", "수", "목", "금", "토", "일"]


@dataclass(frozen=True, slots=True)
class DueMissionEntry:
    mission_type: str
    label: str
    target_location: str
    announcement_text: str


class RuntimeDataService:
    def __init__(
        self,
        *,
        schedule_path: str | Path | None = None,
        alarm_path: str | Path | None = None,
        medication_path: str | Path | None = None,
    ) -> None:
        self.schedule_path = self._resolve_path(schedule_path, "ASSISTANT_SCHEDULES_FILE", "schedules.json")
        self.alarm_path = self._resolve_path(alarm_path, "ASSISTANT_ALARMS_FILE", "alarms.json")
        self.medication_path = self._resolve_path(medication_path, "ASSISTANT_MEDICATIONS_FILE", "medications.json")

    @classmethod
    def _resolve_path(cls, explicit: str | Path | None, env_name: str, filename: str) -> Path:
        if explicit is not None:
            return Path(explicit).expanduser().resolve()
        configured = os.getenv(env_name, "").strip()
        if configured:
            return Path(configured).expanduser().resolve()

        here = Path(__file__).resolve()
        candidates: list[Path] = []
        for parent in here.parents:
            candidates.extend(
                [
                    (parent / "assistant_gui" / "assistant_gui" / filename).resolve(),
                    (parent / "src" / "assistant" / "assistant_gui" / "assistant_gui" / filename).resolve(),
                ]
            )

        seen: set[Path] = set()
        for candidate in candidates:
            if candidate in seen:
                continue
            seen.add(candidate)
            if candidate.exists():
                return candidate
        for candidate in candidates:
            if candidate.parent.exists():
                return candidate
        return (Path.cwd() / filename).resolve()

    def build_schedule_summary(self, source_text: str) -> str:
        target_date = _resolve_target_date(source_text)
        schedules = self._load_schedule_items(target_date)
        label = _humanize_date_label(target_date)
        if not schedules:
            return f"{label} 일정은 등록된 내용이 없어요."

        ordered = sorted(schedules, key=lambda item: item.get("time", "99:99"))
        fragments = []
        for item in ordered[:4]:
            time_str = str(item.get("time", "시간 미정"))
            todo = str(item.get("todo", "일정"))
            place = str(item.get("place", "")).strip()
            if place:
                fragments.append(f"{time_str}에 {todo}, 장소는 {place}")
            else:
                fragments.append(f"{time_str}에 {todo}")
        suffix = "" if len(ordered) <= 4 else f" 외 {len(ordered) - 4}건이 더 있어요"
        return f"{label} 일정은 {', '.join(fragments)}입니다{suffix}."

    def build_alarm_summary(self, source_text: str) -> str:
        target_date = _resolve_target_date(source_text)
        target_weekday = _WEEKDAY_NAMES[target_date.weekday()]
        alarms = self.load_alarms()
        active_alarms = [alarm for alarm in alarms if bool(alarm.get("active")) and _alarm_matches_day(alarm, target_weekday)]
        label = _humanize_date_label(target_date)

        label_prefix = f"{label} 울리는"
        if label not in {"오늘", "내일", "모레"}:
            label_prefix = f"{label}에 울리는"

        if not active_alarms:
            return f"{label_prefix} 활성 알람은 없어요."

        ordered = sorted(active_alarms, key=lambda item: item.get("time", "99:99"))
        fragments = []
        for alarm in ordered[:5]:
            time_str = str(alarm.get("time", "--:--"))
            target = str(alarm.get("target", "사용자"))
            place = str(alarm.get("place", "현재 위치")).strip()
            memo = str(alarm.get("memo", "")).strip()
            fragment = f"{time_str} 알람"
            if target:
                fragment += f", 대상은 {target}"
            if place:
                fragment += f", 장소는 {place}"
            if memo:
                fragment += f", 메모는 {memo}"
            fragments.append(fragment)
        return f"{label_prefix} 알람은 " + "; ".join(fragments) + "."

    def build_medication_summary(self, source_text: str) -> str:
        del source_text
        meds = self.load_medications()
        if not meds:
            return "등록된 복약 일정이 없어요."

        pending = [med for med in meds if not bool(med.get("active"))]
        due_now = [med for med in pending if med.get("time") == datetime.now().strftime("%H:%M")]
        if due_now:
            first = due_now[0]
            return f"지금 복용할 약은 {first.get('pill', '약')}이고 예정 시각은 {first.get('time', '--:--')}입니다."

        if not pending:
            return f"오늘 복약 일정 {len(meds)}건은 모두 완료했어요."

        completed = len(meds) - len(pending)
        details = [f"{med.get('time', '--:--')} {med.get('pill', '약')}" for med in pending[:4]]
        return f"오늘 복약 일정은 총 {len(meds)}건이고 {completed}건 완료했어요. 남은 약은 {', '.join(details)}입니다."

    def add_schedule_from_text(self, source_text: str) -> str:
        target_date = _resolve_target_date(source_text)
        parsed_time = _extract_time_text(source_text)
        if parsed_time is None:
            return "일정을 추가하려면 날짜와 시간을 함께 말씀해주세요. 예를 들어 내일 오후 3시 팀 미팅 일정 추가해줘처럼 말하면 됩니다."

        place = _extract_labeled_value(source_text, ("장소", "위치"))
        todo = _extract_schedule_todo(source_text, place)
        schedules = self.load_schedules()
        date_key = target_date.strftime("%Y-%m-%d")
        schedules.setdefault(date_key, []).append({
            "time": parsed_time,
            "todo": todo,
            "place": place,
        })
        schedules[date_key] = sorted(schedules[date_key], key=lambda item: item.get("time", "99:99"))
        self._write_json(self.schedule_path, schedules)
        label = _humanize_date_label(target_date)
        if place:
            return f"{label} {parsed_time} 일정으로 {todo}을 추가했고 장소는 {place}로 저장했어요."
        return f"{label} {parsed_time} 일정으로 {todo}을 추가했어요."

    def add_alarm_from_text(self, source_text: str) -> str:
        parsed_time = _extract_time_text(source_text)
        if parsed_time is None:
            return "알람을 추가하려면 시간을 함께 말씀해주세요. 예를 들어 오전 7시 알람 맞춰줘처럼 말하면 됩니다."

        days = _extract_alarm_days(source_text)
        target = _extract_labeled_value(source_text, ("대상", "이름")) or "사용자"
        place = _extract_labeled_value(source_text, ("장소", "위치"))
        memo = _extract_alarm_memo(source_text)
        alarms = self.load_alarms()
        alarms.append(
            {
                "time": parsed_time,
                "days": days,
                "target": target,
                "place": place,
                "memo": memo,
                "active": True,
            }
        )
        alarms.sort(key=lambda item: item.get("time", "99:99"))
        self._write_json(self.alarm_path, alarms)
        if days:
            return f"{', '.join(days)} {parsed_time} 알람을 추가했어요."
        return f"매일 {parsed_time} 알람을 추가했어요."

    def add_medication_from_text(self, source_text: str) -> str:
        parsed_time = _extract_time_text(source_text)
        if parsed_time is None:
            return "복약 일정을 추가하려면 시간을 함께 말씀해주세요. 예를 들어 오전 8시 혈압약 복약 추가해줘처럼 말하면 됩니다."

        name = _extract_labeled_value(source_text, ("이름", "대상")) or "사용자"
        pill = _extract_medication_name(source_text)
        if not pill:
            return "복약 일정을 추가하려면 약 이름도 함께 말씀해주세요. 예를 들어 오전 8시 혈압약 복약 추가해줘처럼 말하면 됩니다."

        medications = self.load_medications()
        medications.append({"time": parsed_time, "name": name, "pill": pill, "active": False})
        medications.sort(key=lambda item: item.get("time", "99:99"))
        self._write_json(
            self.medication_path,
            {"last_run_date": datetime.now().strftime("%Y-%m-%d"), "meds": medications},
        )
        return f"{parsed_time} 복약 일정으로 {pill}을 추가했어요."

    def load_schedules(self) -> dict[str, list[dict[str, Any]]]:
        loaded = self._read_json(self.schedule_path)
        return loaded if isinstance(loaded, dict) else {}

    def load_alarms(self) -> list[dict[str, Any]]:
        loaded = self._read_json(self.alarm_path)
        return loaded if isinstance(loaded, list) else []

    def load_medications(self) -> list[dict[str, Any]]:
        loaded = self._read_json(self.medication_path)
        if isinstance(loaded, list):
            meds = loaded
        elif isinstance(loaded, dict):
            meds = loaded.get("meds", [])
        else:
            meds = []
        return meds if isinstance(meds, list) else []

    def mark_medication_completed(self, *, target_user: str = "", now: datetime | None = None) -> bool:
        loaded = self._read_json(self.medication_path)
        if isinstance(loaded, dict):
            meds = loaded.get("meds", [])
            payload_is_dict = True
        elif isinstance(loaded, list):
            meds = loaded
            payload_is_dict = False
        else:
            return False

        if not isinstance(meds, list) or not meds:
            return False

        candidate_indexes = [
            index for index, item in enumerate(meds)
            if isinstance(item, dict) and not bool(item.get("active"))
        ]
        if not candidate_indexes:
            return False

        user = str(target_user or "").strip()
        if user:
            matched = [
                index for index in candidate_indexes
                if str(meds[index].get("name", "")).strip() == user
            ]
            if matched:
                candidate_indexes = matched

        ref_now = now or datetime.now()
        ref_minutes = ref_now.hour * 60 + ref_now.minute

        def _time_gap(index: int) -> int:
            raw = str(meds[index].get("time", "")).strip()
            try:
                hour_text, minute_text = raw.split(":", 1)
                scheduled = int(hour_text) * 60 + int(minute_text)
                return abs(scheduled - ref_minutes)
            except Exception:
                return 24 * 60

        selected_index = min(candidate_indexes, key=_time_gap)
        meds[selected_index]["active"] = True

        if payload_is_dict:
            loaded["meds"] = meds
            loaded["last_run_date"] = ref_now.strftime("%Y-%m-%d")
            self._write_json(self.medication_path, loaded)
        else:
            self._write_json(self.medication_path, meds)
        return True

    def iter_due_runtime_missions(self, *, now: datetime | None = None) -> list[DueMissionEntry]:
        current = now or datetime.now()
        current_time = current.strftime("%H:%M")
        current_day = _WEEKDAY_NAMES[current.weekday()]
        due_entries: list[DueMissionEntry] = []

        for schedule in self._load_schedule_items(current.date()):
            if str(schedule.get("time", "")).strip() != current_time:
                continue
            place = str(schedule.get("place", "")).strip()
            if not place:
                continue
            todo = str(schedule.get("todo", "일정")).strip() or "일정"
            due_entries.append(
                DueMissionEntry(
                    mission_type="call",
                    label=todo,
                    target_location=place,
                    announcement_text=f"{todo} 일정 시간이 되어 {place}으로 이동합니다.",
                )
            )

        for alarm in self.load_alarms():
            if not bool(alarm.get("active")) or str(alarm.get("time", "")).strip() != current_time:
                continue
            if not _alarm_matches_day(alarm, current_day):
                continue
            label = str(alarm.get("memo") or alarm.get("target") or "alarm").strip()
            place = str(alarm.get("place", "")).strip()
            announcement = self._build_alarm_announcement(alarm)
            due_entries.append(
                DueMissionEntry(
                    mission_type="alarm",
                    label=label or "alarm",
                    target_location=place,
                    announcement_text=announcement,
                )
            )

        for medication in self.load_medications():
            if bool(medication.get("active")):
                continue
            if str(medication.get("time", "")).strip() != current_time:
                continue
            target_location = self._resolve_medication_target_location(medication)
            due_entries.append(
                DueMissionEntry(
                    mission_type="medication",
                    label=str(medication.get("name", "복약")).strip() or "복약",
                    target_location=target_location,
                    announcement_text=self._build_medication_announcement(medication),
                )
            )

        return due_entries

    @staticmethod
    def _resolve_medication_target_location(medication: dict[str, Any]) -> str:
        target_name = str(medication.get("name", "")).strip()
        try:
            catalog = PlaceCatalog()
            metadata = catalog.place_metadata()
            if target_name:
                resolved_name = catalog.resolve(target_name)
                if resolved_name in metadata:
                    return resolved_name
            for configured_target in catalog.medication_targets:
                resolved_name = catalog.resolve(configured_target)
                if resolved_name in metadata:
                    return resolved_name
        except Exception:
            pass
        return ""

    def _build_alarm_announcement(self, alarm: dict[str, Any]) -> str:
        target = str(alarm.get("target", "사용자")).strip() or "사용자"
        memo = str(alarm.get("memo", "")).strip()
        if memo:
            return f"{target}님, {memo}"
        return f"{target}님, 알람 시간입니다."

    def _build_medication_announcement(self, medication: dict[str, Any]) -> str:
        name = str(medication.get("name", "사용자")).strip() or "사용자"
        pill = str(medication.get("pill", "약")).strip() or "약"
        return f"{name}님, {pill} 복약 시간입니다."

    def _load_schedule_items(self, target_date: date) -> list[dict[str, Any]]:
        schedules = self.load_schedules()
        items = schedules.get(target_date.strftime("%Y-%m-%d"), [])
        return items if isinstance(items, list) else []

    @staticmethod
    def _read_json(path: Path) -> Any:
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return None

    @staticmethod
    def _write_json(path: Path, payload: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=4), encoding="utf-8")


def _compact(text: str) -> str:
    return re.sub(r"\s+", "", str(text or "")).lower()


def _resolve_target_date(text: str) -> date:
    today = datetime.now().date()
    compact = _compact(text)
    if "모레" in compact:
        return today + timedelta(days=2)
    if "내일" in compact:
        return today + timedelta(days=1)
    if "오늘" in compact:
        return today

    explicit = _extract_explicit_date(text, today.year)
    if explicit is not None:
        return explicit

    weekday = _extract_weekday(text)
    if weekday is not None:
        delta = (weekday - today.weekday()) % 7
        return today + timedelta(days=delta)
    return today


def _extract_explicit_date(text: str, default_year: int) -> date | None:
    match = re.search(r"(20\d{2})[년\-\./]\s*(\d{1,2})[월\-\./]\s*(\d{1,2})", text)
    if match:
        year, month, day = map(int, match.groups())
        try:
            return date(year, month, day)
        except ValueError:
            return None
    match = re.search(r"(\d{1,2})월\s*(\d{1,2})일", text)
    if match:
        month, day = map(int, match.groups())
        try:
            return date(default_year, month, day)
        except ValueError:
            return None
    return None


def _extract_weekday(text: str) -> int | None:
    for index, name in enumerate(_WEEKDAY_NAMES):
        if f"{name}요일" in text:
            return index
    return None


def _humanize_date_label(target_date: date) -> str:
    today = datetime.now().date()
    if target_date == today:
        return "오늘"
    if target_date == today + timedelta(days=1):
        return "내일"
    if target_date == today + timedelta(days=2):
        return "모레"
    return f"{target_date.month}월 {target_date.day}일"


def _extract_time_text(text: str) -> str | None:
    match = re.search(r"\b(\d{1,2})[:시]\s*(\d{2})\b", text)
    if match and ":" in match.group(0):
        hour, minute = map(int, match.groups())
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            return f"{hour:02d}:{minute:02d}"

    match = re.search(r"(오전|오후|새벽|저녁|밤)?\s*(\d{1,2})\s*시(?:\s*(\d{1,2})\s*분?)?", text)
    if not match:
        return None
    meridiem, hour_text, minute_text = match.groups()
    hour = int(hour_text)
    minute = int(minute_text or "0")
    if hour > 23 or minute > 59:
        return None
    if meridiem in {"오후", "저녁", "밤"} and hour < 12:
        hour += 12
    if meridiem in {"오전", "새벽"} and hour == 12:
        hour = 0
    return f"{hour:02d}:{minute:02d}"


def _extract_labeled_value(text: str, labels: tuple[str, ...]) -> str:
    for label in labels:
        match = re.search(rf"{label}(?:은|는|이|가)?\s*([가-힣A-Za-z0-9_ ]+)", text)
        if match:
            return match.group(1).strip().rstrip(".,")
    return ""


def _extract_schedule_todo(text: str, place: str) -> str:
    cleaned = str(text)
    cleaned = re.sub(r"(오늘|내일|모레|\d{1,2}월\s*\d{1,2}일|[월화수목금토일]요일)", " ", cleaned)
    cleaned = re.sub(r"(오전|오후|새벽|저녁|밤)?\s*\d{1,2}\s*시(?:\s*\d{1,2}\s*분?)?", " ", cleaned)
    cleaned = re.sub(r"\b\d{1,2}:\d{2}\b", " ", cleaned)
    cleaned = re.sub(r"(나\s*)?(일정|스케줄|약속)\s*(추가|등록)(해\s*줘|해주세요)?", " ", cleaned)
    if place:
        cleaned = cleaned.replace(place, " ")
        cleaned = re.sub(r"(장소|위치)(은|는|이|가)?", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" .,;")
    return cleaned or "새 일정"


def _extract_alarm_days(text: str) -> list[str]:
    return [name for name in _WEEKDAY_NAMES if f"{name}요일" in text]


def _extract_alarm_memo(text: str) -> str:
    cleaned = str(text)
    cleaned = re.sub(r"(오늘|내일|모레|[월화수목금토일]요일)", " ", cleaned)
    cleaned = re.sub(r"(오전|오후|새벽|저녁|밤)?\s*\d{1,2}\s*시(?:\s*\d{1,2}\s*분?)?", " ", cleaned)
    cleaned = re.sub(r"\b\d{1,2}:\d{2}\b", " ", cleaned)
    cleaned = re.sub(r"알람\s*(맞춰|설정|추가|등록)(해\s*줘|해주세요)?", " ", cleaned)
    cleaned = re.sub(r"(대상|이름|장소|위치)(은|는|이|가)?\s*[가-힣A-Za-z0-9_ ]+", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" .,;")
    return cleaned


def _extract_medication_name(text: str) -> str:
    labeled = _extract_labeled_value(text, ("약", "복약"))
    if labeled:
        return labeled
    cleaned = str(text)
    cleaned = re.sub(r"(오늘|내일|모레|[월화수목금토일]요일)", " ", cleaned)
    cleaned = re.sub(r"(오전|오후|새벽|저녁|밤)?\s*\d{1,2}\s*시(?:\s*\d{1,2}\s*분?)?", " ", cleaned)
    cleaned = re.sub(r"\b\d{1,2}:\d{2}\b", " ", cleaned)
    cleaned = re.sub(r"(복약|약)\s*(추가|등록)(해\s*줘|해주세요)?", " ", cleaned)
    cleaned = re.sub(r"(이름|대상)(은|는|이|가)?\s*[가-힣A-Za-z0-9_ ]+", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" .,;")
    return cleaned


def _alarm_matches_day(alarm: dict[str, Any], weekday_name: str) -> bool:
    days = alarm.get("days", [])
    if not isinstance(days, list) or not days:
        return True
    return weekday_name in days
