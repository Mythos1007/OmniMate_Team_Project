from __future__ import annotations

from assistant_interfaces.srv import GetRobotStatus

import rclpy
from rclpy.node import Node


class StatusProviderNode(Node):
    """로봇 상태 조회를 위한 간단한 서비스 엔드포인트를 제공한다."""

    def __init__(self) -> None:
        super().__init__('status_provider_node')

        self.declare_parameter('battery_percent', 87.5)
        self.declare_parameter('location_name', 'home')
        self.declare_parameter('robot_mode', 'idle')

        self.create_service(GetRobotStatus, '/assistant/get_robot_status', self._handle_get_robot_status)
        self.get_logger().info('Status provider ready.')

    def _handle_get_robot_status(
        self,
        request: GetRobotStatus.Request,
        response: GetRobotStatus.Response,
    ) -> GetRobotStatus.Response:
        del request
        response.battery_percent = float(self.get_parameter('battery_percent').value)
        response.location_name = str(self.get_parameter('location_name').value)
        response.robot_mode = str(self.get_parameter('robot_mode').value)
        return response


def main(args: list[str] | None = None) -> None:
    rclpy.init(args=args)
    node = StatusProviderNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()
