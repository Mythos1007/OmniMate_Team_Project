from __future__ import annotations

import json
import logging

from std_msgs.msg import Bool, Float32, String

import rclpy
from rclpy.node import Node

from assistant_robot.demo import build_mock_orchestrator


class OrchestratorNode(Node):
    """기능: ROS topic과 순수 Python orchestrator를 연결하는 브리지 노드."""

    def __init__(self) -> None:
        super().__init__("omni_orchestrator_node")
        self.declare_parameter("tts_profile", "demo")
        tts_profile = str(self.get_parameter("tts_profile").value)
        self._orchestrator, _ = build_mock_orchestrator(tts_profile=tts_profile)
        self._status_publisher = self.create_publisher(String, "/assistant/orchestrator/status", 10)
        self.create_subscription(String, "/assistant/voice_text", self._on_voice_text, 10)
        self.create_subscription(String, "/assistant/gui_command_text", self._on_gui_text, 10)
        self.create_subscription(Float32, "/assistant/battery_percent", self._on_battery_percent, 10)
        self.create_subscription(Bool, "/assistant/charging", self._on_charging, 10)
        self._charging = False
        # 기능: executor step을 주기적으로 진행시키는 heartbeat 타이머.
        self.create_timer(0.5, self._on_tick)
        self.get_logger().info("Omni orchestrator node ready.")

    def _on_voice_text(self, message: String) -> None:
        decision, _ = self._orchestrator.ingest_voice_text(message.data)
        self.get_logger().info("Voice intake: %s", decision)
        self._publish_state()

    def _on_gui_text(self, message: String) -> None:
        decision, _ = self._orchestrator.ingest_voice_text(message.data)
        self.get_logger().info("GUI intake: %s", decision)
        self._publish_state()

    def _on_battery_percent(self, message: Float32) -> None:
        self._orchestrator.update_battery(battery_level=float(message.data), charging=self._charging)
        self._publish_state()

    def _on_charging(self, message: Bool) -> None:
        self._charging = bool(message.data)
        self._orchestrator.update_battery(
            battery_level=self._orchestrator.state.battery_level,
            charging=self._charging,
        )
        self._publish_state()

    def _on_tick(self) -> None:
        self._orchestrator.tick()
        self._publish_state()

    def _publish_state(self) -> None:
        # 기능: GUI/외부 노드가 바로 파싱 가능한 JSON 상태 스냅샷을 publish.
        state = self._orchestrator.state
        self._status_publisher.publish(String(data=json.dumps({
            "top_state": state.top_state.value,
            "current_mission_id": state.current_mission_id,
            "battery_level": state.battery_level,
            "charging": state.charging,
            "low_battery_restricted": state.low_battery_restricted,
            "pending_count": state.pending_count,
            "status_message_for_gui": state.status_message_for_gui,
            "current_mission_type": state.current_mission_type,
        }, ensure_ascii=False)))


def main(args: list[str] | None = None) -> None:
    logging.basicConfig(level=logging.INFO)
    rclpy.init(args=args)
    node = OrchestratorNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()
