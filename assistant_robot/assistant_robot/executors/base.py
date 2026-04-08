from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
import logging

from assistant_robot.interfaces.confirmation_service import BaseConfirmationService
from assistant_robot.interfaces.navigation_controller import BaseNavigationController
from assistant_robot.interfaces.weather_provider import BaseWeatherProvider
from assistant_robot.models.mission import Mission
from assistant_robot.models.mission_result import MissionEvent
from assistant_robot.services.weather_formatter import WeatherFormatter
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from assistant_robot.services.runtime_data_service import RuntimeDataService


@dataclass(slots=True)
class ExecutorContext:
    navigation_controller: BaseNavigationController
    confirmation_service: BaseConfirmationService
    weather_provider: BaseWeatherProvider
    weather_formatter: WeatherFormatter
    logger: logging.Logger
    runtime_data_service: RuntimeDataService | None = None


class BaseMissionExecution(ABC):
    def __init__(self, mission: Mission, context: ExecutorContext) -> None:
        self.mission = mission
        self.context = context

    @abstractmethod
    def step(self) -> MissionEvent:
        raise NotImplementedError

    def cancel(self) -> None:
        return None

    def pause_navigation(self) -> bool:
        return False

    def resume_navigation(self) -> bool:
        return False


class BaseMissionExecutor(ABC):
    @abstractmethod
    def create_execution(self, mission: Mission, context: ExecutorContext) -> BaseMissionExecution:
        raise NotImplementedError
