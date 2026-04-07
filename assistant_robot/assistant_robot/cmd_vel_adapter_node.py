from __future__ import annotations

from geometry_msgs.msg import Twist, TwistStamped

import rclpy
from rclpy.node import Node


class CmdVelAdapterNode(Node):
    """Twist와 TwistStamped 사이를 변환해 로봇 구동 토픽으로 전달 기능."""

    def __init__(self) -> None:
        super().__init__('cmd_vel_adapter_node')

        self.declare_parameter('output_type', 'twist')
        self.declare_parameter('input_twist_topic', '/assistant/cmd_vel')
        self.declare_parameter('input_twist_stamped_topic', '/assistant/cmd_vel_stamped')
        self.declare_parameter('output_twist_topic', '/cmd_vel')
        self.declare_parameter('output_twist_stamped_topic', '/cmd_vel_stamped')
        self.declare_parameter('stamp_frame_id', 'base_link')

        self._output_type = str(self.get_parameter('output_type').value).strip().lower()
        self._stamp_frame_id = str(self.get_parameter('stamp_frame_id').value)

        input_twist_topic = str(self.get_parameter('input_twist_topic').value)
        input_twist_stamped_topic = str(self.get_parameter('input_twist_stamped_topic').value)
        output_twist_topic = str(self.get_parameter('output_twist_topic').value)
        output_twist_stamped_topic = str(self.get_parameter('output_twist_stamped_topic').value)

        if self._output_type not in {'twist', 'twist_stamped'}:
            self.get_logger().warn(
                f'Unsupported output_type {self._output_type}. Falling back to twist.'
            )
            self._output_type = 'twist'

        self._twist_publisher = self.create_publisher(Twist, output_twist_topic, 10)
        self._twist_stamped_publisher = self.create_publisher(
            TwistStamped, output_twist_stamped_topic, 10
        )

        self.create_subscription(Twist, input_twist_topic, self._on_twist, 10)
        self.create_subscription(
            TwistStamped, input_twist_stamped_topic, self._on_twist_stamped, 10
        )

        self.get_logger().info(
            'CmdVel adapter ready. '
            f'input_twist={input_twist_topic}, '
            f'input_twist_stamped={input_twist_stamped_topic}, '
            f'output_type={self._output_type}'
        )

    def _on_twist(self, message: Twist) -> None:
        if self._output_type == 'twist':
            self._twist_publisher.publish(message)
            return

        converted = TwistStamped()
        converted.header.stamp = self.get_clock().now().to_msg()
        converted.header.frame_id = self._stamp_frame_id
        converted.twist = message
        self._twist_stamped_publisher.publish(converted)

    def _on_twist_stamped(self, message: TwistStamped) -> None:
        if self._output_type == 'twist_stamped':
            self._twist_stamped_publisher.publish(message)
            return

        self._twist_publisher.publish(message.twist)


def main(args: list[str] | None = None) -> None:
    rclpy.init(args=args)
    node = CmdVelAdapterNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()
