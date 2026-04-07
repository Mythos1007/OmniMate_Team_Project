from __future__ import annotations

from assistant_commands.command_executor import MockCommandExecutor
from assistant_commands import CanonicalCommand
from assistant_brain.dispatch_types import DispatchResult


class MotionHandler:
    def __init__(self) -> None:
        self._executor = MockCommandExecutor()

    def handle(self, command: CanonicalCommand) -> DispatchResult:
        execution_text = self._executor.execute(command)
        return DispatchResult(
            handled=True,
            status_text=execution_text,
            speak_text=self._build_speech(command),
        )

    def _build_speech(self, command: CanonicalCommand) -> str:
        if command.command == 'move_forward':
            if 'distance' in command.args and 'unit' in command.args:
                return f"앞으로 {command.args['distance']} {command.args['unit']} 이동할게요."
            if 'duration' in command.args and 'unit' in command.args:
                return f"앞으로 {command.args['duration']} {command.args['unit']} 동안 이동할게요."
            return '앞으로 이동할게요.'

        if command.command == 'move_backward':
            return '뒤로 이동할게요.'
        if command.command == 'turn_left':
            return '왼쪽으로 회전할게요.'
        if command.command == 'turn_right':
            return '오른쪽으로 회전할게요.'
        if command.command == 'stop':
            return '정지할게요.'
        if command.command == 'start_patrol':
            return '순찰을 시작할게요.'
        if command.command == 'pause_patrol':
            return '순찰을 잠시 멈출게요.'
        if command.command == 'resume_patrol':
            return '순찰을 다시 시작할게요.'
        return '이동 명령을 처리할게요.'
