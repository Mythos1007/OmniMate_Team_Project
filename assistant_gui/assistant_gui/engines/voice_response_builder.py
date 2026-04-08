from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
import json
from pathlib import Path
import re
from typing import Any

try:
    from assistant_robot.services.runtime_data_service import RuntimeDataService
except ModuleNotFoundError:
    RuntimeDataService = None


_WEEKDAY_NAMES = ["월", "화", "수", "목", "금", "토", "일"]


@dataclass(frozen=True)
class DetectedIntent:
    name: str
    position: int


def build_contextual_voice_response(main_window, command_text: str) -> str:
    text = str(command_text or "").strip()
    if not text:
        return _fallback_response(main_window, text)

    intents = _detect_intents(text)
    if not intents:
        return _fallback_response(main_window, text)

    responses: list[str] = []
    seen: set[str] = set()
    for intent in intents:
        if intent.name in seen:
            continue
        seen.add(intent.name)
        response = _build_intent_response(main_window, intent.name, text)
        if response:
            responses.append(response)

    return " ".join(responses) if responses else _fallback_response(main_window, text)


def _detect_intents(text: str) -> list[DetectedIntent]:
    compact = _compact(text)
    patterns: dict[str, tuple[str, ...]] = {
        "weather": ("날씨", "기온", "온도", "미세먼지", "비와", "예보"),
        "schedule": ("오늘일정", "내일일정", "모레일정", "일정", "스케줄", "약속"),
        "medication": ("복약", "오늘약", "약이랑", "약도", "약은", "약뭐", "무슨약", "약먹", "약확인", "약체크", "먹어야해", "먹어야돼"),
        "alarm": ("오늘알람", "내일알람", "요일알람", "알람", "깨워", "리마인드"),
        "cancel": ("취소", "중지", "멈춰"),
        "where_status": ("어디가", "어디로가", "어디있", "상태"),
        "delivery_request": ("우편", "배달", "배송", "전달"),
        "navigation_request": ("안내해줘", "가줘", "로가", "이동해줘"),
    }

    detected: list[DetectedIntent] = []
    for intent_name, keywords in patterns.items():
        positions = [compact.find(keyword) for keyword in keywords if compact.find(keyword) >= 0]
        if positions:
            detected.append(DetectedIntent(intent_name, min(positions)))

    return sorted(detected, key=lambda item: item.position)


def _build_intent_response(main_window, intent_name: str, text: str) -> str:
    if intent_name == "weather":
        return _weather_response(main_window, text)
    if intent_name == "schedule":
        return _schedule_response(main_window, text)
    if intent_name == "medication":
        return _medication_response(main_window, text)
    if intent_name == "alarm":
        return _alarm_response(main_window, text)
    return _fallback_response(main_window, text, forced_intent=intent_name)


def _weather_response(main_window, text: str) -> str:
    engine = getattr(main_window, "weather_engine", None)
    if engine is None:
        return "날씨 엔진이 연결되지 않아 현재 날씨를 확인할 수 없어요."

    temp = str(getattr(engine, "temp", "--°"))
    desc = str(getattr(engine, "desc", "확인중"))
    air = str(getattr(engine, "air", "보통"))
    hourly = list(getattr(engine, "forecast_hourly", []) or [])
    weekly = list(getattr(engine, "forecast_weekly", []) or [])

    if temp == "--°" or desc in {"확인중", "날씨 API 키 미설정", ""}:
        return f"현재 날씨 정보를 아직 받아오지 못했어요. 상태는 {desc or '확인중'}입니다."

    pieces = [f"현재 날씨는 {desc}이고 기온은 {temp}예요. 미세먼지는 {air} 수준입니다."]
    compact = _compact(text)
    if "예보" in compact or "시간별" in compact:
        preview = []
        for item in hourly[:3]:
            preview.append(f"{item.get('time', '--')}에는 {item.get('temp', '--')}도 정도예요")
        if preview:
            pieces.append("오늘 시간별로는 " + ", ".join(preview) + ".")
    if "내일날씨" in compact or "주간" in compact or "이번주" in compact:
        if weekly:
            summary = []
            for item in weekly[:2]:
                summary.append(f"{item.get('date', '--')}은 {item.get('temp_range', '--')} 예상이에요")
            pieces.append("주간 예보로는 " + ", ".join(summary) + ".")
    return " ".join(pieces)


def _schedule_response(main_window, text: str) -> str:
    if RuntimeDataService is not None:
        return RuntimeDataService().build_schedule_summary(text)
    target_date = _resolve_target_date(text)
    schedules = _load_schedule_items(main_window, target_date)
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


def _medication_response(main_window, text: str) -> str:
    if RuntimeDataService is not None:
        return RuntimeDataService().build_medication_summary(text)
    meds = _load_medications(main_window)
    if not meds:
        return "등록된 복약 일정이 없어요."

    pending = [med for med in meds if not bool(med.get("active"))]
    due_now = [med for med in pending if med.get("time") == datetime.now().strftime("%H:%M")]
    if due_now:
        first = due_now[0]
        return f"지금 복용할 약은 {first.get('pill', '약')}이고 예정 시각은 {first.get('time', '--:--')}입니다."

    compact = _compact(text)
    if "오늘약" in compact or "약뭐" in compact or "먹어야" in compact:
        if not pending:
            return "오늘 복약 일정은 모두 완료했어요."
        details = [f"{med.get('time', '--:--')}에 {med.get('pill', '약')}" for med in pending[:5]]
        return "오늘 아직 먹지 않은 약은 " + ", ".join(details) + "입니다."

    completed = len(meds) - len(pending)
    if not pending:
        return f"오늘 복약 일정 {len(meds)}건은 모두 완료했어요."
    details = [f"{med.get('time', '--:--')} {med.get('pill', '약')}" for med in pending[:4]]
    return f"오늘 복약 일정은 총 {len(meds)}건이고 {completed}건 완료했어요. 남은 약은 {', '.join(details)}입니다."


def _alarm_response(main_window, text: str) -> str:
    if RuntimeDataService is not None:
        return RuntimeDataService().build_alarm_summary(text)
    target_date = _resolve_target_date(text)
    target_weekday = _WEEKDAY_NAMES[target_date.weekday()]
    alarms = _load_alarms(main_window)
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
        target = str(alarm.get("target", "미지정"))
        place = str(alarm.get("place", "미지정"))
        memo = str(alarm.get("memo", "")).strip()
        fragment = f"{time_str} 알람, 대상은 {target}, 장소는 {place}"
        if memo:
            fragment += f", 메모는 {memo}"
        fragments.append(fragment)
    return f"{label_prefix} 알람은 " + "; ".join(fragments) + "."


def _fallback_response(main_window, text: str, forced_intent: str | None = None) -> str:
    scenario_key = forced_intent or main_window.classify_tts_scenario(text)
    context = main_window.build_tts_runtime_context(text)
    return main_window.render_tts_scenario(scenario_key, context)


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
            candidate = date(default_year, month, day)
        except ValueError:
            return None
        return candidate
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


def _load_json(path_str: str) -> Any:
    path = Path(path_str)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _load_schedule_items(main_window, target_date: date) -> list[dict[str, Any]]:
    manager = getattr(main_window, "schedule_mgr", None)
    if manager is None:
        return []
    loaded = _load_json(getattr(manager, "filename", ""))
    date_key = target_date.strftime("%Y-%m-%d")
    if not isinstance(loaded, dict):
        return []
    items = loaded.get(date_key, [])
    return items if isinstance(items, list) else []


def _load_alarms(main_window) -> list[dict[str, Any]]:
    manager = getattr(main_window, "alarm_mgr", None)
    if manager is None:
        return []
    loaded = _load_json(getattr(manager, "filename", ""))
    return loaded if isinstance(loaded, list) else []


def _load_medications(main_window) -> list[dict[str, Any]]:
    page = getattr(main_window, "medication_page", None)
    manager = getattr(page, "med_mgr", None)
    if manager is None:
        return []
    loaded = _load_json(getattr(manager, "filename", ""))
    if isinstance(loaded, list):
        meds = loaded
    elif isinstance(loaded, dict):
        meds = loaded.get("meds", [])
    else:
        meds = []

    if not isinstance(meds, list):
        return []
    ordered = sorted(meds, key=lambda item: item.get("time", "99:99"))
    return ordered


def _alarm_matches_day(alarm: dict[str, Any], weekday_name: str) -> bool:
    days = alarm.get("days", [])
    if not isinstance(days, list) or not days:
        return True
    return weekday_name in days
