from __future__ import annotations

import math
from typing import Any

from assistant_interfaces.action import GuideToNamedPlace
from action_msgs.msg import GoalStatus
from geometry_msgs.msg import PoseStamped, Quaternion
from nav2_msgs.action import NavigateToPose

import rclpy
from rclpy.action import ActionClient, ActionServer, CancelResponse, GoalResponse
from rclpy.action.server import ServerGoalHandle
from rclpy.node import Node

from assistant_robot.services.place_catalog import PlaceCatalog


class NavBridgeNode(Node):
    """이름 기반 목적지를 로컬 액션 서버를 통해 Nav2 목표로 변환 기능."""

    def __init__(self) -> None:
        super().__init__('nav_bridge_node')
        self._place_catalog = PlaceCatalog()

        self._nav_client = ActionClient(self, NavigateToPose, 'navigate_to_pose')
        self._action_server = ActionServer(
            self,
            GuideToNamedPlace,
            '/assistant/guide_to_named_place',
            execute_callback=self._execute_goal,
            goal_callback=self._on_goal_request,
            cancel_callback=self._on_cancel_request,
        )

        self.get_logger().info('Nav bridge ready.')

    def _on_goal_request(self, goal_request: GuideToNamedPlace.Goal) -> GoalResponse:
        place_name = goal_request.place_name.strip().lower()
        if not self._named_place_exists(place_name):
            self.get_logger().warn(f'Unknown place requested: {place_name}')
            return GoalResponse.REJECT
        return GoalResponse.ACCEPT

    def _on_cancel_request(self, goal_handle: ServerGoalHandle) -> CancelResponse:
        self.get_logger().warn(f'Cancel requested for named-place goal: {goal_handle.request.place_name}')
        # TODO: 전체 연동이 완료되면 취소 요청을 Nav2 goal handle까지 전달 기능.
        return CancelResponse.ACCEPT

    async def _execute_goal(self, goal_handle: ServerGoalHandle) -> GuideToNamedPlace.Result:
        place_name = goal_handle.request.place_name.strip().lower()
        target_pose = self._build_pose(place_name)

        feedback = GuideToNamedPlace.Feedback()
        feedback.current_phase = 'validating_destination'
        feedback.progress = 0.1
        goal_handle.publish_feedback(feedback)

        if not self._nav_client.wait_for_server(timeout_sec=1.0):
            goal_handle.abort()
            result = GuideToNamedPlace.Result()
            result.success = False
            result.message = 'Nav2 NavigateToPose action server is not available.'
            return result

        nav_goal = NavigateToPose.Goal()
        nav_goal.pose = target_pose

        feedback.current_phase = 'sending_nav2_goal'
        feedback.progress = 0.4
        goal_handle.publish_feedback(feedback)

        # TODO: Nav2의 피드백을 받아 GuideToNamedPlace 피드백으로 중계 기능.
        nav_goal_handle_future = self._nav_client.send_goal_async(nav_goal)
        nav_goal_handle = await nav_goal_handle_future
        if not nav_goal_handle.accepted:
            goal_handle.abort()
            result = GuideToNamedPlace.Result()
            result.success = False
            result.message = f'Nav2 rejected destination {place_name}.'
            return result

        feedback.current_phase = 'navigating'
        feedback.progress = 0.7
        goal_handle.publish_feedback(feedback)

        nav_result_future = nav_goal_handle.get_result_async()
        nav_result = await nav_result_future

        result = GuideToNamedPlace.Result()
        if nav_result.status != GoalStatus.STATUS_SUCCEEDED:
            goal_handle.abort()
            result.success = False
            result.message = f'Navigation failed for {place_name}. status={nav_result.status}'
            return result

        goal_handle.succeed()
        result.success = True
        result.message = f'Arrived at {place_name}.'
        return result

    def _named_place_exists(self, place_name: str) -> bool:
        return self._place_catalog.resolve(place_name) in self._place_catalog.named_places()

    def _build_pose(self, place_name: str) -> PoseStamped:
        canonical_name = self._place_catalog.resolve(place_name)
        metadata = self._place_catalog.place_metadata()[canonical_name]
        frame_id = str(metadata.get('frame_id', 'map'))
        x_value = float(metadata.get('x', 0.0))
        y_value = float(metadata.get('y', 0.0))

        pose = PoseStamped()
        pose.header.frame_id = frame_id
        pose.header.stamp = self.get_clock().now().to_msg()
        pose.pose.position.x = x_value
        pose.pose.position.y = y_value
        pose.pose.position.z = 0.0
        if 'orientation_z' in metadata and 'orientation_w' in metadata:
            pose.pose.orientation.z = float(metadata.get('orientation_z', 0.0))
            pose.pose.orientation.w = float(metadata.get('orientation_w', 1.0))
        else:
            yaw_value = float(metadata.get('yaw', 0.0))
            pose.pose.orientation = self._quaternion_from_yaw(yaw_value)
        return pose

    def _quaternion_from_yaw(self, yaw: float) -> Quaternion:
        quaternion = Quaternion()
        quaternion.z = math.sin(yaw / 2.0)
        quaternion.w = math.cos(yaw / 2.0)
        return quaternion


def main(args: list[str] | None = None) -> None:
    rclpy.init(args=args)
    node = NavBridgeNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()
