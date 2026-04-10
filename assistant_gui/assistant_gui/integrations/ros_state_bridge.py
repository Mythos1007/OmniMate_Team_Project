"""GUI ↔ ROS2 상태 브리지.

백그라운드 스레드에서 rclpy.spin 을 실행하며, /assistant/state 토픽을 구독한다.
Qt 시그널을 통해 메인 스레드(GUI)에 상태를 전달한다.

ROS2 환경이 없어도 GUI 단독 실행이 가능하도록 import 실패를 조용히 처리한다.
"""
from __future__ import annotations

import json
from typing import Callable

try:
    import rclpy
    from rclpy.node import Node
    from std_msgs.msg import String

    _ROS_AVAILABLE = True
except ImportError:
    _ROS_AVAILABLE = False


# ─── Qt 임포트 (PySide6) ────────────────────────────────────────────────────
from PySide6.QtCore import QObject, Signal

try:
    from assistant_gui.integrations.ros_runtime import get_shared_ros_runtime
except ModuleNotFoundError:
    from integrations.ros_runtime import get_shared_ros_runtime


class RosStateBridge(QObject):
    """ROS2 /assistant/state 구독자를 백그라운드 스레드에서 실행하는 Qt 브리지.

    연결 예시:
        bridge = RosStateBridge()
        bridge.state_changed.connect(my_slot)
        bridge.status_changed.connect(my_status_slot)
        bridge.start()
    """

    # Qt 시그널 — 메인 스레드(GUI)에서 안전하게 수신 가능
    state_changed = Signal(str)    # AssistantState.state 값 (예: 'SLEEPING', 'LISTENING' …)
    status_changed = Signal(str)   # /assistant/status_text 값

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._node: object | None = None  # rclpy.Node (type erase to avoid import error)
        self._running = False
        self._ros_runtime = get_shared_ros_runtime()

    def start(self) -> None:
        """ROS2 스핀 스레드를 시작 기능. ROS2가 없으면 아무것도 하지 않는다."""
        if not _ROS_AVAILABLE:
            return
        if self._running:
            return
        try:
            self._node = _StateSubscriberNode(
                on_state=lambda s: self.state_changed.emit(s),
                on_status=lambda s: self.status_changed.emit(s),
            )
            if not self._ros_runtime.add_node(self._node):
                self._node = None
                return
            self._running = True
        except Exception as exc:
            print(f'[RosStateBridge] ROS2 setup error: {exc}')
            self._node = None
            self._running = False

    def stop(self) -> None:
        self._running = False
        if self._node is not None:
            self._ros_runtime.remove_node(self._node)
            self._node = None


if _ROS_AVAILABLE:

    class _StateSubscriberNode(Node):
        def __init__(
            self,
            on_state: Callable[[str], None],
            on_status: Callable[[str], None],
        ) -> None:
            super().__init__('assistant_gui_state_listener')

            self._on_state = on_state
            self._on_status = on_status

            # AssistantState는 custom msg — import 실패 시 String으로 fallback
            try:
                from assistant_interfaces.msg import AssistantState
                self.create_subscription(
                    AssistantState,
                    '/assistant/state',
                    self._on_state_msg,
                    10,
                )
            except Exception:
                pass

            self.create_subscription(
                String,
                '/assistant/status_text',
                lambda msg: self._on_status(msg.data),
                10,
            )
            self.create_subscription(
                String,
                '/assistant/orchestrator/status',
                self._on_orchestrator_status,
                10,
            )

        def _on_state_msg(self, msg: object) -> None:
            self._on_state(str(msg.state))  # type: ignore[union-attr]

        def _on_orchestrator_status(self, msg: String) -> None:
            try:
                payload = json.loads(msg.data)
            except Exception:
                self._on_status(msg.data)
                return
            top_state = str(payload.get('top_state', '')).strip()
            status_message = str(payload.get('status_message_for_gui', '')).strip()
            if top_state:
                self._on_state(top_state)
            if status_message:
                self._on_status(status_message)
