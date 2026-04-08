from __future__ import annotations

from pydantic import BaseModel, Field


class CommandRequest(BaseModel):
    text: str = Field(min_length=1, max_length=240)
    source: str = Field(default="web")


class CommandResponse(BaseModel):
    accepted: bool
    detail: str


class NavigateClickRequest(BaseModel):
    x_m: float = Field(ge=-1000.0, le=1000.0)
    y_m: float = Field(ge=-1000.0, le=1000.0)


class HealthResponse(BaseModel):
    ok: bool
    ros_available: bool


class WeatherResponse(BaseModel):
    temperature_c: float | None
    description: str
    icon: str


class StateResponse(BaseModel):
    ros_available: bool
    assistant_state: str
    status_text: str
    battery_percent: int | None
    charging: bool
    pose_x_m: float | None
    pose_y_m: float | None
    pose_source: str
    updated_at_unix: float


class ScheduleUpsertRequest(BaseModel):
    date: str = Field(min_length=10, max_length=10)
    time: str = Field(min_length=4, max_length=5)
    todo: str = Field(min_length=1, max_length=120)
    place: str = Field(default="", max_length=120)


class AlarmUpsertRequest(BaseModel):
    time: str = Field(min_length=4, max_length=5)
    target: str = Field(default="미지정", max_length=120)
    place: str = Field(default="미지정", max_length=120)
    days: list[str] = Field(default_factory=list)
    memo: str = Field(default="", max_length=240)
    active: bool = True


class AlarmToggleRequest(BaseModel):
    active: bool


class MedicationUpsertRequest(BaseModel):
    time: str = Field(min_length=4, max_length=5)
    name: str = Field(default="사용자", max_length=120)
    pill: str = Field(default="약", max_length=120)
    active: bool = False


class MedicationToggleRequest(BaseModel):
    active: bool
