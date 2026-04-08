from __future__ import annotations

from assistant_robot.interfaces.tts_provider import BaseTTSProvider, TTSRequest

from std_msgs.msg import String

from rclpy.node import Node


class RosTopicTTSProvider(BaseTTSProvider):
    def __init__(self, node: Node, *, topic_name: str = '/assistant/speak') -> None:
        self._publisher = node.create_publisher(String, topic_name, 10)

    def speak(self, request: TTSRequest) -> None:
        text = str(request.text).strip()
        if not text:
            return
        self._publisher.publish(String(data=text))

    def stop(self) -> None:
        return None
