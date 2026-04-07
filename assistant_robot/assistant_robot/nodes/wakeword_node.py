from __future__ import annotations

from std_msgs.msg import String

import rclpy
from rclpy.node import Node


class WakewordNode(Node):
    def __init__(self) -> None:
        super().__init__("wakeword_node")
        self._publisher = self.create_publisher(String, "/assistant/wakeword", 10)
        self.get_logger().info("Wakeword node ready.")

    def publish_detected(self, text: str = "옴니야") -> None:
        # TODO: Connect the real wake word detector here.
        self._publisher.publish(String(data=text))


def main(args: list[str] | None = None) -> None:
    rclpy.init(args=args)
    node = WakewordNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()
