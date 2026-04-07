from __future__ import annotations

from std_msgs.msg import String

import rclpy
from rclpy.node import Node


class GUIBridgeNode(Node):
    def __init__(self) -> None:
        super().__init__("gui_bridge_node")
        self._publisher = self.create_publisher(String, "/assistant/gui_status", 10)
        self.create_subscription(String, "/assistant/orchestrator/status", self._forward_status, 10)
        self.get_logger().info("GUI bridge node ready.")

    def _forward_status(self, message: String) -> None:
        # TODO: Convert this transport into a dedicated GUI DTO or custom ROS message when the GUI contract is finalized.
        self._publisher.publish(message)


def main(args: list[str] | None = None) -> None:
    rclpy.init(args=args)
    node = GUIBridgeNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()
