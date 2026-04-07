from __future__ import annotations

from enum import Enum


class CommandSource(str, Enum):
    VOICE = "voice"
    GUI = "gui"
    SCHEDULER = "scheduler"
    SYSTEM = "system"


class MissionType(str, Enum):
    DELIVERY = "delivery"
    CALL = "call"
    ALARM = "alarm"
    MEDICATION = "medication"
    WEATHER_TTS = "weather_tts"
    STATUS_BRIEF = "status_brief"
    RETURN_TO_BASE = "return_to_base"


class MissionStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class TopState(str, Enum):
    BOOTING = "BOOTING"
    IDLE = "IDLE"
    EXECUTING = "EXECUTING"
    WAITING_CONFIRMATION = "WAITING_CONFIRMATION"
    CHARGING = "CHARGING"
    LOW_BATTERY_RESTRICTED = "LOW_BATTERY_RESTRICTED"
    ERROR = "ERROR"
    EMERGENCY_STOP = "EMERGENCY_STOP"


class TtsPriority(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
