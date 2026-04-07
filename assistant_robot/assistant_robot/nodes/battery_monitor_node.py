from __future__ import annotations

from std_msgs.msg import Bool, Float32

import rclpy
from rclpy.node import Node


class BatteryMonitorNode(Node):
    def __init__(self) -> None:
        super().__init__("battery_monitor_node")
        self._battery_publisher = self.create_publisher(Float32, "/assistant/battery_percent", 10)
        self._charging_publisher = self.create_publisher(Bool, "/assistant/charging", 10)
        self.get_logger().info("Battery monitor node ready.")

    def publish_status(self, *, battery_percent: float, charging: bool) -> None:
        # TODO: Replace with real battery telemetry from robot hardware or diagnostics.
        self._battery_publisher.publish(Float32(data=battery_percent))
        self._charging_publisher.publish(Bool(data=charging))


def main(args: list[str] | None = None) -> None:
    rclpy.init(args=args)
    node = BatteryMonitorNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()
