import os
import threading
import math

import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from PySide6.QtCore import QObject, Signal

from geometry_msgs.msg import PoseWithCovarianceStamped
from nav_msgs.msg import Odometry

try:
    from assistant_gui.integrations.ros_runtime import get_shared_ros_runtime
except ModuleNotFoundError:
    from integrations.ros_runtime import get_shared_ros_runtime


class PoseEngine(QObject, threading.Thread):
    """Prefer AMCL pose updates and keep odom fallback disabled by default."""

    pose_changed = Signal(float, float, float, str)

    def __init__(self) -> None:
        QObject.__init__(self)
        threading.Thread.__init__(self)
        self.daemon = True
        self._stopped = threading.Event()
        self._ros_runtime = get_shared_ros_runtime()

        if not rclpy.ok():
            rclpy.init()

        self.node = Node("pose_engine_node")
        self._running = True
        self._last_pose: tuple[float, float, float] | None = None
        self._amcl_seen = False
        self._allow_odom_fallback = os.getenv("ASSISTANT_USE_ODOM_FALLBACK", "0").strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }

        self._amcl_sub = self.node.create_subscription(
            PoseWithCovarianceStamped,
            "/amcl_pose",
            self._on_amcl_pose,
            qos_profile_sensor_data,
        )
        self._odom_sub = None
        if self._allow_odom_fallback:
            self._odom_sub = self.node.create_subscription(
                Odometry,
                "/odom",
                self._on_odom,
                qos_profile_sensor_data,
            )

    def _emit_if_changed(self, x: float, y: float, yaw_rad: float, source: str) -> None:
        if self._last_pose is not None:
            last_x, last_y, last_yaw = self._last_pose
            if abs(last_x - x) < 1e-4 and abs(last_y - y) < 1e-4 and abs(last_yaw - yaw_rad) < 1e-4:
                return
        self._last_pose = (x, y, yaw_rad)
        self.pose_changed.emit(float(x), float(y), float(yaw_rad), source)

    @staticmethod
    def _yaw_from_orientation(orientation) -> float:
        x = float(getattr(orientation, 'x', 0.0))
        y = float(getattr(orientation, 'y', 0.0))
        z = float(getattr(orientation, 'z', 0.0))
        w = float(getattr(orientation, 'w', 1.0))
        siny_cosp = 2.0 * (w * z + x * y)
        cosy_cosp = 1.0 - 2.0 * (y * y + z * z)
        return math.atan2(siny_cosp, cosy_cosp)

    def _on_amcl_pose(self, msg: PoseWithCovarianceStamped) -> None:
        self._amcl_seen = True
        self._emit_if_changed(
            msg.pose.pose.position.x,
            msg.pose.pose.position.y,
            self._yaw_from_orientation(msg.pose.pose.orientation),
            "/amcl_pose",
        )

    def _on_odom(self, msg: Odometry) -> None:
        if not self._allow_odom_fallback or self._amcl_seen:
            return
        self._emit_if_changed(
            msg.pose.pose.position.x,
            msg.pose.pose.position.y,
            self._yaw_from_orientation(msg.pose.pose.orientation),
            "/odom",
        )

    def run(self) -> None:
        if not self._ros_runtime.add_node(self.node):
            return
        self._stopped.wait()

    def stop(self) -> None:
        self._running = False
        self._stopped.set()
        self._ros_runtime.remove_node(self.node)
