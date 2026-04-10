from __future__ import annotations

import json
from typing import Callable

from PySide6.QtCore import QObject, Signal

try:
    import rclpy
    from rclpy.node import Node
    from std_msgs.msg import String

    _ROS_AVAILABLE = True
except Exception:
    _ROS_AVAILABLE = False

try:
    from assistant_gui.integrations.ros_runtime import get_shared_ros_runtime
except ModuleNotFoundError:
    from integrations.ros_runtime import get_shared_ros_runtime


DATA_SYNC_REQUEST_TOPIC = "/assistant/data_sync/request"
DATA_SYNC_SNAPSHOT_TOPIC = "/assistant/data_sync/snapshot"


class DataSyncBridge(QObject):
    snapshot_requested = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._node: object | None = None
        self._running = False
        self._ros_runtime = get_shared_ros_runtime()

    def start(self) -> None:
        if not _ROS_AVAILABLE or self._running:
            return
        try:
            self._node = _DataSyncNode(on_request=lambda request_id: self.snapshot_requested.emit(request_id))
            if not self._ros_runtime.add_node(self._node):
                self._node = None
                return
            self._running = True
        except Exception as exc:
            print(f"[DataSyncBridge] ROS2 setup error: {exc}")
            self._node = None
            self._running = False

    def stop(self) -> None:
        self._running = False
        if self._node is not None:
            self._ros_runtime.remove_node(self._node)
            self._node = None

    def publish_snapshot(self, payload: dict[str, object]) -> bool:
        if not self._running or self._node is None:
            return False
        try:
            self._node.publish_snapshot(payload)  # type: ignore[attr-defined]
            return True
        except Exception:
            return False


if _ROS_AVAILABLE:
    class _DataSyncNode(Node):
        def __init__(self, on_request: Callable[[str], None]) -> None:
            super().__init__("assistant_gui_data_sync_bridge")
            self._on_request = on_request
            self._snapshot_publisher = self.create_publisher(String, DATA_SYNC_SNAPSHOT_TOPIC, 10)
            self.create_subscription(String, DATA_SYNC_REQUEST_TOPIC, self._on_snapshot_request, 10)

        def _on_snapshot_request(self, message: String) -> None:
            self._on_request(str(message.data or "").strip())

        def publish_snapshot(self, payload: dict[str, object]) -> None:
            serialized = json.dumps(payload, ensure_ascii=False)
            self._snapshot_publisher.publish(String(data=serialized))
