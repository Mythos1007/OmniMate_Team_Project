from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True)
class WeatherData:
    temperature_c: float
    condition: str
    humidity_percent: int | None = None
    rain_probability_percent: int | None = None
    location_name: str | None = None
    summary: str | None = None
    observed_at: datetime | None = None


class BaseWeatherProvider(ABC):
    @abstractmethod
    def get_current_weather(self, *, location_name: str | None = None) -> WeatherData:
        raise NotImplementedError
