from __future__ import annotations

from assistant_interfaces.msg import AssistantIntent

from std_msgs.msg import Bool, String
from std_srvs.srv import Trigger

import rclpy
from rclpy.node import Node


class SafetyGateNode(Node):
    """비상 정지 요청이 다른 모든 동작보다 우선되도록 보장한다."""

    def __init__(self) -> None:
        super().__init__('safety_gate_node')

        self._emergency_publisher = self.create_publisher(Bool, '/assistant/emergency_stop', 10)
        self._status_publisher = self.create_publisher(String, '/assistant/status_text', 10)
        self._cancel_client = self.create_client(Trigger, '/assistant/cancel_current_task')

        self.create_subscription(AssistantIntent, '/assistant/intent', self._on_intent, 10)
        self.create_subscription(Bool, '/assistant/emergency_stop', self._on_emergency_broadcast, 10)

        self.get_logger().info('Safety gate ready.')

    def _on_intent(self, message: AssistantIntent) -> None:
        if message.intent_name != 'stop':
            return
        self._publish_emergency_stop('Stop intent detected from classifier.')
        self._cancel_current_task_if_available()

    def _on_emergency_broadcast(self, message: Bool) -> None:
        if not message.data:
            return
        self._cancel_current_task_if_available()

    def _publish_emergency_stop(self, reason: str) -> None:
        self._emergency_publisher.publish(Bool(data=True))
        self._status_publisher.publish(String(data=reason))
        self.get_logger().warn(reason)

    def _cancel_current_task_if_available(self) -> None:
        if not self._cancel_client.wait_for_service(timeout_sec=0.5):
            self.get_logger().warn('Cancel service not ready during emergency stop handling.')
            return

        future = self._cancel_client.call_async(Trigger.Request())
        future.add_done_callback(self._on_cancel_response)

    def _on_cancel_response(self, future) -> None:
        try:
            response = future.result()
        except Exception as error:  # noqa: BLE001
            self.get_logger().error(f'Failed to cancel current task: {error}')
            return
        self.get_logger().info(f'Cancel task response: success={response.success}, message={response.message}')


def main(args: list[str] | None = None) -> None:
    rclpy.init(args=args)
    node = SafetyGateNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()
