import threading

import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from PySide6.QtCore import QObject, Signal

from geometry_msgs.msg import PoseWithCovarianceStamped
from nav_msgs.msg import Odometry


class PoseEngine(QObject, threading.Thread):
    """/amcl_pose 또는 /odom에서 현재 좌표를 받아 Qt 시그널로 전달한다."""

    pose_changed = Signal(float, float, str)

    def __init__(self) -> None:
        QObject.__init__(self)
        threading.Thread.__init__(self)
        self.daemon = True

        if not rclpy.ok():
            rclpy.init()

        self.node = Node("pose_engine_node")
        self._running = True
        self._last_xy: tuple[float, float] | None = None

        self._amcl_sub = self.node.create_subscription(
            PoseWithCovarianceStamped,
            "/amcl_pose",
            self._on_amcl_pose,
            qos_profile_sensor_data,
        )
        self._odom_sub = self.node.create_subscription(
            Odometry,
            "/odom",
            self._on_odom,
            qos_profile_sensor_data,
        )

    def _emit_if_changed(self, x: float, y: float, source: str) -> None:
        if self._last_xy is not None:
            last_x, last_y = self._last_xy
            if abs(last_x - x) < 1e-4 and abs(last_y - y) < 1e-4:
                return
        self._last_xy = (x, y)
        self.pose_changed.emit(float(x), float(y), source)

    def _on_amcl_pose(self, msg: PoseWithCovarianceStamped) -> None:
        self._emit_if_changed(msg.pose.pose.position.x, msg.pose.pose.position.y, "/amcl_pose")

    def _on_odom(self, msg: Odometry) -> None:
        # /amcl_pose가 없는 환경에서도 /odom으로 최소 현재 위치를 표시한다.
        self._emit_if_changed(msg.pose.pose.position.x, msg.pose.pose.position.y, "/odom")

    def run(self) -> None:
        try:
            while self._running and rclpy.ok():
                rclpy.spin_once(self.node, timeout_sec=0.2)
        except Exception as exc:
            print(f"[PoseEngine] spin error: {exc}")

    def stop(self) -> None:
        self._running = False
        try:
            self.node.destroy_node()
        except Exception:
            pass
