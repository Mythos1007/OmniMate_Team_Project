from __future__ import annotations

from assistant_commands import CanonicalCommand
from assistant_brain.dispatch_types import DispatchResult
from assistant_brain.service_registry import InMemoryServiceRegistry


class TaskHandler:
    def __init__(self, registry: InMemoryServiceRegistry) -> None:
        self._registry = registry

    def handle_alarm_create(self, command: CanonicalCommand) -> DispatchResult:
        time = str(command.args.get('time', '07:00'))
        label = str(command.args.get('label', '기본 알람'))
        entry = self._registry.add_alarm(time=time, label=label)
        return DispatchResult(
            handled=True,
            status_text=f'[STUB] Alarm saved: {entry.time} {entry.label}',
            speak_text=f'{entry.time} 알람 {entry.label} 저장했어요.',
        )

    def handle_alarm_list(self) -> DispatchResult:
        alarms = self._registry.list_alarms()
        if not alarms:
            return DispatchResult(
                handled=True,
                status_text='[STUB] No alarms saved.',
                speak_text='저장된 알람이 없어요.',
            )

        summary = ', '.join(f'{entry.time} {entry.label}' for entry in alarms)
        return DispatchResult(
            handled=True,
            status_text=f'[STUB] Alarm list: {summary}',
            speak_text=f'저장된 알람은 {summary}예요.',
        )

    def handle_schedule_create(self, command: CanonicalCommand) -> DispatchResult:
        title = str(command.args.get('title', '기본 일정'))
        date = str(command.args.get('date', '오늘'))
        time = str(command.args.get('time', '09:00'))
        entry = self._registry.add_schedule(title=title, date=date, time=time)
        return DispatchResult(
            handled=True,
            status_text=f'[STUB] Schedule saved: {entry.date} {entry.time} {entry.title}',
            speak_text=f'{entry.date} {entry.time} 일정 {entry.title} 저장했어요.',
        )

    def handle_schedule_list(self) -> DispatchResult:
        schedules = self._registry.list_schedules()
        if not schedules:
            return DispatchResult(
                handled=True,
                status_text='[STUB] No schedules saved.',
                speak_text='저장된 일정이 없어요.',
            )

        summary = ', '.join(f'{entry.date} {entry.time} {entry.title}' for entry in schedules)
        return DispatchResult(
            handled=True,
            status_text=f'[STUB] Schedule list: {summary}',
            speak_text=f'저장된 일정은 {summary}예요.',
        )
