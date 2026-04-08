from __future__ import annotations

import json

from std_msgs.msg import String

import rclpy
from rclpy.node import Node

from assistant_robot.adapters.mock_intent_parser import MockIntentParser
from assistant_robot.constants import ASSISTANT_COMMAND_TOPIC


class IntentParserNode(Node):
    def __init__(self) -> None:
        super().__init__("intent_parser_node")
        self._parser = MockIntentParser()
        self._publisher = self.create_publisher(String, "/assistant/parsed_intent", 10)
        self.create_subscription(String, ASSISTANT_COMMAND_TOPIC, self._on_voice_text, 10)
        self.get_logger().info("Intent parser node ready.")

    def _on_voice_text(self, message: String) -> None:
        result = self._parser.parse(message.data)
        payload = {
            "primary_command": result.primary_command.parsed_intent if result.primary_command else None,
            "rejected_count": len(result.rejected_commands),
            "rejection_message_key": result.rejection_message_key,
        }
        self._publisher.publish(String(data=json.dumps(payload, ensure_ascii=False)))


def main(args: list[str] | None = None) -> None:
    rclpy.init(args=args)
    node = IntentParserNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()
