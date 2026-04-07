from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Literal


IntentCategory = Literal["command", "query", "chat"]

# intent_name → category 매핑 (라우터에서 참조 가능)
INTENT_CATEGORIES: dict[str, IntentCategory] = {
    # command — 로봇이 물리적으로 실행해야 하는 동작
    "move_forward":   "command",
    "move_backward":  "command",
    "turn_left":      "command",
    "turn_right":     "command",
    "stop":           "command",
    "start_patrol":   "command",
    "pause_patrol":   "command",
    "resume_patrol":  "command",
    "guide_to_place": "command",
    "follow_me":      "command",
    "go_home":        "command",
    "deliver_mail":   "command",
    # query — 정보 조회 (실행 권한 없음)
    "get_battery_status": "query",
    "get_current_time":   "query",
    "get_robot_status":   "query",
    "status_query":       "query",
    "weather_query":      "query",
    "alarm_list":         "query",
    "schedule_list":      "query",
    # chat — 대화/안내 (정보 출력만)
    "smalltalk": "chat",
    "unknown":   "chat",
}


@dataclass
class IntentClassification:
    intent_name: str
    confidence: float
    slots: dict[str, str] = field(default_factory=dict)
    intent_category: IntentCategory = "chat"


STOP_KEYWORDS = ('stop', 'halt', '멈춰', '정지', '중지')
FORWARD_KEYWORDS = ('앞으로 가', '앞으로', '직진', '직진해', '앞으로 이동', '전진')
FOLLOW_KEYWORDS = ('follow me', '따라와', 'follow')
GO_HOME_KEYWORDS = ('go home', '원위치로 가', '복귀', 'home으로 가')
BATTERY_KEYWORDS = ('battery', '배터리')
TIME_KEYWORDS = ('what time', '몇 시', '몇시', '현재 시각')
STATUS_KEYWORDS = ('status', 'state', '상태 알려줘', '로봇 상태')
SMALLTALK_KEYWORDS = ('hello', 'hi', '안녕', '반가워', 'hey assistant')


def normalize_text(text: str) -> str:
    return ' '.join(text.strip().lower().split())


def canonicalize_place_name(place_name: str) -> str:
    compact = place_name.strip().lower()
    return re.sub(r'\s+', '_', compact)


def extract_place_name(text: str) -> str | None:
    patterns = [
        r'guide me to (?P<place>[a-zA-Z0-9_\- ]+)',
        r'take me to (?P<place>[a-zA-Z0-9_\- ]+)',
        r'(?P<place>.+?)(?:로|으로) 안내해줘',
        r'(?P<place>.+?)(?:로|으로) 가줘',
    ]

    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return canonicalize_place_name(match.group('place'))
    return None


def _make(intent_name: str, confidence: float, slots: dict[str, str] | None = None) -> IntentClassification:
    """intent_name 에서 카테고리를 자동 조회해 IntentClassification 을 생성 기능."""
    return IntentClassification(
        intent_name=intent_name,
        confidence=confidence,
        slots=slots or {},
        intent_category=INTENT_CATEGORIES.get(intent_name, "chat"),
    )


def classify_intent(text: str) -> IntentClassification:
    normalized = normalize_text(text)

    if any(keyword in normalized for keyword in STOP_KEYWORDS):
        return _make('stop', 0.99)

    if any(keyword in normalized for keyword in FORWARD_KEYWORDS):
        return _make('move_forward', 0.96)

    place_name = extract_place_name(normalized)
    if place_name:
        return _make('guide_to_place', 0.92, {'place_name': place_name})

    if any(keyword in normalized for keyword in FOLLOW_KEYWORDS):
        return _make('follow_me', 0.95)

    if any(keyword in normalized for keyword in GO_HOME_KEYWORDS):
        return _make('go_home', 0.95)

    if any(keyword in normalized for keyword in BATTERY_KEYWORDS):
        return _make('get_battery_status', 0.90)

    if any(keyword in normalized for keyword in TIME_KEYWORDS):
        return _make('get_current_time', 0.90)

    if any(keyword in normalized for keyword in STATUS_KEYWORDS):
        return _make('get_robot_status', 0.88)

    if any(keyword in normalized for keyword in SMALLTALK_KEYWORDS):
        return _make('smalltalk', 0.75)

    return _make('unknown', 0.10)
