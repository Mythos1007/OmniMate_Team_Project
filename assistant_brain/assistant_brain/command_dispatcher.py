from __future__ import annotations

from assistant_commands import CanonicalCommand
from assistant_brain.dispatch_types import DispatchResult
from assistant_brain.handlers import InfoHandler, MotionHandler, NavigationHandler, TaskHandler
from assistant_brain.service_registry import InMemoryServiceRegistry


class CommandDispatcher:
    """정규 명령을 도메인 핸들러로 분기하는 디스패처."""

    def __init__(self, registry: InMemoryServiceRegistry | None = None) -> None:
        self._registry = registry or InMemoryServiceRegistry()
        self._motion_handler = MotionHandler()
        self._info_handler = InfoHandler(self._registry)
        self._task_handler = TaskHandler(self._registry)
        self._navigation_handler = NavigationHandler(self._registry)

    @property
    def registry(self) -> InMemoryServiceRegistry:
        return self._registry

    def dispatch(self, command: CanonicalCommand) -> DispatchResult:
        """명령 종류에 따라 적절한 핸들러를 선택해 실행한다."""
        if command.command in {
            'move_forward',
            'move_backward',
            'turn_left',
            'turn_right',
            'stop',
            'start_patrol',
            'pause_patrol',
            'resume_patrol',
        }:
            return self._motion_handler.handle(command)

        if command.command == 'weather_query':
            return self._info_handler.handle_weather_query()

        if command.command == 'alarm_create':
            return self._task_handler.handle_alarm_create(command)

        if command.command == 'alarm_list':
            return self._task_handler.handle_alarm_list()

        if command.command == 'schedule_create':
            return self._task_handler.handle_schedule_create(command)

        if command.command == 'schedule_list':
            return self._task_handler.handle_schedule_list()

        if command.command == 'guide_to_location':
            return self._navigation_handler.handle_guide_to_location(command)

        if command.command == 'deliver_mail':
            return self._navigation_handler.handle_deliver_mail(command)

        return DispatchResult(
            handled=False,
            status_text=f'[STUB] No handler registered for {command.command}',
            speak_text='아직 연결되지 않은 명령이에요.',
        )
