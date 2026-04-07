"""GUI ↔ ROS2 상태 브리지.

백그라운드 스레드에서 rclpy.spin 을 실행하며, /assistant/state 토픽을 구독한다.
Qt 시그널을 통해 메인 스레드(GUI)에 상태를 전달한다.

ROS2 환경이 없어도 GUI 단독 실행이 가능하도록 import 실패를 조용히 처리한다.
"""
from __future__ import annotations

import threading
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
        self._thread: threading.Thread | None = None
        self._node: object | None = None  # rclpy.Node (type erase to avoid import error)
        self._running = False

    def start(self) -> None:
        """ROS2 스핀 스레드를 시작 기능. ROS2가 없으면 아무것도 하지 않는다."""
        if not _ROS_AVAILABLE:
            return
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._spin, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        if self._node is not None:
            try:
                self._node.destroy_node()  # type: ignore[union-attr]
            except Exception:
                pass

    def _spin(self) -> None:
        try:
            if not rclpy.ok():
                rclpy.init()
            node = _StateSubscriberNode(
                on_state=lambda s: self.state_changed.emit(s),
                on_status=lambda s: self.status_changed.emit(s),
            )
            self._node = node
            while self._running and rclpy.ok():
                rclpy.spin_once(node, timeout_sec=0.1)
        except Exception as exc:
            print(f'[RosStateBridge] ROS2 spin error: {exc}')
        finally:
            self._running = False


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

        def _on_state_msg(self, msg: object) -> None:
            self._on_state(str(msg.state))  # type: ignore[union-attr]
