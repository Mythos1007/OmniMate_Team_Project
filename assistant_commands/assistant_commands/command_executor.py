from __future__ import annotations

from assistant_commands.command_schema import CanonicalCommand


class MockCommandExecutor:
    def execute(self, command: CanonicalCommand) -> str:
        handler = getattr(self, f"execute_{command.command}", self.execute_unknown)
        return handler(command.args)

    def execute_move_forward(self, args: dict[str, object]) -> str:
        return f"[EXECUTE] Moving forward{self._format_motion_suffix(args)}"

    def execute_move_backward(self, args: dict[str, object]) -> str:
        return f"[EXECUTE] Moving backward{self._format_motion_suffix(args)}"

    def execute_turn_left(self, args: dict[str, object]) -> str:
        return "[EXECUTE] Turning left"

    def execute_turn_right(self, args: dict[str, object]) -> str:
        return "[EXECUTE] Turning right"

    def execute_stop(self, args: dict[str, object]) -> str:
        return "[EXECUTE] Stop"

    def execute_start_patrol(self, args: dict[str, object]) -> str:
        return "[EXECUTE] Patrol started"

    def execute_pause_patrol(self, args: dict[str, object]) -> str:
        return "[EXECUTE] Patrol paused"

    def execute_resume_patrol(self, args: dict[str, object]) -> str:
        return "[EXECUTE] Patrol resumed"

    def execute_status_query(self, args: dict[str, object]) -> str:
        return "[EXECUTE] Reporting current status"

    def execute_unknown(self, args: dict[str, object]) -> str:
        original_text = args.get("original_text", "")
        return f"[EXECUTE] Unknown command: {original_text}"

    def _format_motion_suffix(self, args: dict[str, object]) -> str:
        if "distance" in args and "unit" in args:
            return f" for {args['distance']} {args['unit']}"
        if "duration" in args and "unit" in args:
            return f" for {args['duration']} {args['unit']}"
        return ""
