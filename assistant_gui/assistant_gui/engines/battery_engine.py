import collections
import threading

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import BatteryState
from PySide6.QtCore import QObject, Signal


class BatteryEngine(QObject, threading.Thread):
    """ROS2 battery_state를 수신해 Qt 시그널로 전달한다."""

    battery_changed = Signal(int, bool)

    def __init__(self):
        QObject.__init__(self)
        threading.Thread.__init__(self)
        self.daemon = True

        if not rclpy.ok():
            rclpy.init()
        self.node = Node("battery_engine_node")
        self.subscription = self.node.create_subscription(BatteryState, "/battery_state", self.battery_callback, 10)

        self._running = True
        self.last_percent = -1
        self.last_charging = False
        self._percent_window: collections.deque[int] = collections.deque(maxlen=30)

    def battery_callback(self, msg):
        raw = int(msg.percentage * 100) if msg.percentage <= 1.0 else int(msg.percentage)
        self._percent_window.append(raw)
        percent = round(sum(self._percent_window) / len(self._percent_window))
        is_charging = msg.power_supply_status == BatteryState.POWER_SUPPLY_STATUS_CHARGING

        if percent != self.last_percent or is_charging != self.last_charging:
            self.last_percent = percent
            self.last_charging = is_charging
            self.battery_changed.emit(percent, is_charging)

    def run(self):
        while self._running and rclpy.ok():
            rclpy.spin_once(self.node, timeout_sec=0.2)

    def stop(self):
        self._running = False
        try:
            self.node.destroy_node()
        except Exception:
            pass
