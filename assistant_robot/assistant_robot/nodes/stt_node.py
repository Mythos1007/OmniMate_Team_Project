from __future__ import annotations

from std_msgs.msg import String

import rclpy
from rclpy.node import Node


class STTNode(Node):
    def __init__(self) -> None:
        super().__init__("stt_node")
        self._publisher = self.create_publisher(String, "/assistant/voice_text", 10)
        self.get_logger().info("STT node ready.")

    def publish_transcript(self, transcript: str) -> None:
        # TODO: Attach the real STT backend and publish final transcripts here.
        self._publisher.publish(String(data=transcript))


def main(args: list[str] | None = None) -> None:
    rclpy.init(args=args)
    node = STTNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()
