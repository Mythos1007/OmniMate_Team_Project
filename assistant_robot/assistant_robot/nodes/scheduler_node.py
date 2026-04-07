from __future__ import annotations

from datetime import datetime, timedelta

from std_msgs.msg import String

import rclpy
from rclpy.node import Node


class SchedulerNode(Node):
    def __init__(self) -> None:
        super().__init__("scheduler_node")
        self._publisher = self.create_publisher(String, "/assistant/gui_command_text", 10)
        self.create_timer(60.0, self._tick)
        self.get_logger().info("Scheduler node ready.")

    def _tick(self) -> None:
        # TODO: Replace with real schedule loading and mission generation.
        if datetime.now().minute == 0:
            self._publisher.publish(String(data="옴니야 회의실 A로 가줘"))


def main(args: list[str] | None = None) -> None:
    rclpy.init(args=args)
    node = SchedulerNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()
