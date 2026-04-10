import collections
import math
import os
import threading

import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from std_msgs.msg import Bool, Float32
from sensor_msgs.msg import BatteryState
from PySide6.QtCore import QObject, Signal

try:
    from assistant_gui.integrations.ros_runtime import get_shared_ros_runtime
except ModuleNotFoundError:
    from integrations.ros_runtime import get_shared_ros_runtime


class BatteryEngine(QObject, threading.Thread):
    """ROS2 battery_state를 수신해 Qt 시그널로 전달 기능."""

    battery_changed = Signal(int, bool)

    def __init__(self):
        QObject.__init__(self)
        threading.Thread.__init__(self)
        self.daemon = True
        self._stopped = threading.Event()
        self._ros_runtime = get_shared_ros_runtime()

        if not rclpy.ok():
            rclpy.init()
        self.node = Node("battery_engine_node")
        battery_topic = os.getenv("ASSISTANT_BATTERY_TOPIC", "/battery_state").strip() or "/battery_state"

        # Compatibility:
        # - /battery_state (sensor_msgs/BatteryState)
        # - /assistant/battery_percent + /assistant/charging (assistant_robot)
        self.subscription = self.node.create_subscription(
            BatteryState,
            battery_topic,
            self.battery_callback,
            qos_profile_sensor_data,
        )
        self._assistant_battery_sub = self.node.create_subscription(
            Float32,
            "/assistant/battery_percent",
            self._assistant_battery_callback,
            10,
        )
        self._assistant_charging_sub = self.node.create_subscription(
            Bool,
            "/assistant/charging",
            self._assistant_charging_callback,
            10,
        )

        self._running = True
        self.last_percent = -1
        self.last_charging = False
        window_size = max(1, int(os.getenv("ASSISTANT_BATTERY_AVERAGE_WINDOW", "50")))
        self._percent_window: collections.deque[int] = collections.deque(maxlen=window_size)

    def _emit_if_changed(self, percent: int, is_charging: bool) -> None:
        safe_percent = max(0, min(100, int(percent)))
        self._percent_window.append(safe_percent)
        averaged_percent = round(sum(self._percent_window) / len(self._percent_window))

        if averaged_percent != self.last_percent or is_charging != self.last_charging:
            self.last_percent = averaged_percent
            self.last_charging = is_charging
            self.battery_changed.emit(averaged_percent, is_charging)

    @staticmethod
    def _extract_percent(msg: BatteryState) -> int | None:
        value = float(msg.percentage)
        if not math.isfinite(value):
            return None
        if value < 0:
            # sensor_msgs/BatteryState: unknown percentage is typically negative.
            return None
        if value <= 1.0:
            return int(round(value * 100))
        return int(round(value))

    @staticmethod
    def _is_charging(msg: BatteryState) -> bool:
        return msg.power_supply_status in {
            BatteryState.POWER_SUPPLY_STATUS_CHARGING,
            BatteryState.POWER_SUPPLY_STATUS_FULL,
        }

    def battery_callback(self, msg):
        raw = self._extract_percent(msg)
        if raw is None:
            return
        is_charging = self._is_charging(msg)
        self._emit_if_changed(raw, is_charging)

    def _assistant_battery_callback(self, msg: Float32) -> None:
        self._emit_if_changed(int(msg.data), self.last_charging)

    def _assistant_charging_callback(self, msg: Bool) -> None:
        self._emit_if_changed(self.last_percent if self.last_percent >= 0 else 0, bool(msg.data))

    def run(self):
        if not self._ros_runtime.add_node(self.node):
            return
        self._stopped.wait()

    def stop(self):
        self._running = False
        self._stopped.set()
        self._ros_runtime.remove_node(self.node)
