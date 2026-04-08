from __future__ import annotations

import threading
import time
from dataclasses import dataclass, asdict

try:
    import rclpy
    from rclpy.node import Node
    from rclpy.qos import qos_profile_sensor_data
    from std_msgs.msg import String, Bool, Float32
    from nav_msgs.msg import Odometry
    from geometry_msgs.msg import PoseWithCovarianceStamped
    from sensor_msgs.msg import BatteryState

    ROS_OK = True
except Exception:
    ROS_OK = False


@dataclass(slots=True)
class Snapshot:
    ros_available: bool = ROS_OK
    assistant_state: str = "UNKNOWN"
    status_text: str = "Waiting for ROS data"
    battery_percent: int | None = None
    charging: bool = False
    pose_x_m: float | None = None
    pose_y_m: float | None = None
    pose_source: str = ""
    updated_at_unix: float = 0.0


class RosBridge:
    def __init__(self) -> None:
        self._snapshot = Snapshot(updated_at_unix=time.time())
        self._lock = threading.Lock()
        self._running = False
        self._thread: threading.Thread | None = None
        self._node: "_BridgeNode | None" = None

    def start(self) -> None:
        if not ROS_OK or self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._spin, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        if self._node is not None:
            try:
                self._node.destroy_node()
            except Exception:
                pass

    def publish_gui_command(self, text: str) -> tuple[bool, str]:
        if not ROS_OK:
            return False, "ROS not available in this environment"
        node = self._node
        if node is None:
            return False, "ROS bridge is not running yet"
        msg = String()
        msg.data = text
        node.command_pub.publish(msg)
        return True, "Published to /assistant/command_text"

    def publish_manual_wake(self) -> tuple[bool, str]:
        if not ROS_OK:
            return False, "ROS not available in this environment"
        node = self._node
        if node is None:
            return False, "ROS bridge is not running yet"
        msg = Bool()
        msg.data = True
        node.manual_wake_pub.publish(msg)
        return True, "Published to /assistant/manual_wake"

    def publish_navigate_xy(self, x_m: float, y_m: float) -> tuple[bool, str]:
        # Keep parity with desktop GUI command format used in existing orchestrator flow.
        command = f"navigate:x={x_m:.3f},y={y_m:.3f}"
        return self.publish_gui_command(command)

    def get_snapshot(self) -> dict:
        with self._lock:
            return asdict(self._snapshot)

    def _touch(self) -> None:
        with self._lock:
            self._snapshot.updated_at_unix = time.time()

    def _set_status_text(self, text: str) -> None:
        with self._lock:
            self._snapshot.status_text = text
            self._snapshot.updated_at_unix = time.time()

    def _set_assistant_state(self, value: str) -> None:
        with self._lock:
            self._snapshot.assistant_state = value
            self._snapshot.updated_at_unix = time.time()

    def _set_battery(self, percent: int | None, charging: bool | None = None) -> None:
        with self._lock:
            self._snapshot.battery_percent = percent
            if charging is not None:
                self._snapshot.charging = charging
            self._snapshot.updated_at_unix = time.time()

    def _set_pose(self, x: float, y: float, source: str) -> None:
        with self._lock:
            self._snapshot.pose_x_m = round(x, 3)
            self._snapshot.pose_y_m = round(y, 3)
            self._snapshot.pose_source = source
            self._snapshot.updated_at_unix = time.time()

    def _spin(self) -> None:
        try:
            if not rclpy.ok():
                rclpy.init()
            node = _BridgeNode(self)
            self._node = node
            while self._running and rclpy.ok():
                rclpy.spin_once(node, timeout_sec=0.2)
        except Exception as exc:
            self._set_status_text(f"ROS bridge error: {exc}")
        finally:
            self._running = False


if ROS_OK:

    class _BridgeNode(Node):
        def __init__(self, bridge: RosBridge) -> None:
            super().__init__("assistant_web_bridge")
            self._bridge = bridge

            self.command_pub = self.create_publisher(String, "/assistant/command_text", 10)
            self.manual_wake_pub = self.create_publisher(Bool, "/assistant/manual_wake", 10)

            self.create_subscription(String, "/assistant/status_text", self._on_status, 10)
            self.create_subscription(String, "/assistant/orchestrator/status", self._on_status, 10)
            self.create_subscription(String, "/assistant/gui_status", self._on_status, 10)
            self.create_subscription(Float32, "/assistant/battery_percent", self._on_battery_percent, 10)
            self.create_subscription(Bool, "/assistant/charging", self._on_charging, 10)
            self.create_subscription(BatteryState, "/battery_state", self._on_battery_state, qos_profile_sensor_data)
            self.create_subscription(PoseWithCovarianceStamped, "/amcl_pose", self._on_amcl, qos_profile_sensor_data)
            self.create_subscription(Odometry, "/odom", self._on_odom, qos_profile_sensor_data)

            try:
                from assistant_interfaces.msg import AssistantState

                self.create_subscription(AssistantState, "/assistant/state", self._on_assistant_state, 10)
            except Exception:
                pass

        def _on_status(self, msg: String) -> None:
            self._bridge._set_status_text(msg.data)

        def _on_assistant_state(self, msg: object) -> None:
            self._bridge._set_assistant_state(str(msg.state))  # type: ignore[attr-defined]

        def _on_battery_percent(self, msg: Float32) -> None:
            value = max(0, min(100, int(round(float(msg.data)))))
            self._bridge._set_battery(value)

        def _on_charging(self, msg: Bool) -> None:
            snap = self._bridge.get_snapshot()
            self._bridge._set_battery(snap.get("battery_percent"), bool(msg.data))

        def _on_battery_state(self, msg: BatteryState) -> None:
            pct: int | None = None
            try:
                raw = float(msg.percentage)
                if raw >= 0:
                    pct = max(0, min(100, int(round(raw * 100.0 if raw <= 1.0 else raw))))
            except Exception:
                pct = None

            charging = msg.power_supply_status in (
                BatteryState.POWER_SUPPLY_STATUS_CHARGING,
                BatteryState.POWER_SUPPLY_STATUS_FULL,
            )
            self._bridge._set_battery(pct, charging)

        def _on_amcl(self, msg: PoseWithCovarianceStamped) -> None:
            p = msg.pose.pose.position
            self._bridge._set_pose(float(p.x), float(p.y), "/amcl_pose")

        def _on_odom(self, msg: Odometry) -> None:
            p = msg.pose.pose.position
            self._bridge._set_pose(float(p.x), float(p.y), "/odom")
