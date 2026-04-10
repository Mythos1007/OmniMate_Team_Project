from __future__ import annotations

import asyncio
import math
from typing import Any

from assistant_interfaces.action import GuideToNamedPlace
from action_msgs.msg import GoalStatus
from geometry_msgs.msg import PoseStamped, PoseWithCovarianceStamped, Quaternion
from nav2_msgs.action import NavigateToPose

import rclpy
from rclpy.action import ActionClient, ActionServer, CancelResponse, GoalResponse
from rclpy.action.server import ServerGoalHandle
from rclpy.node import Node
from std_msgs.msg import Bool

from assistant_robot.services.navigation_target_parser import parse_coordinate_target
from assistant_robot.services.place_catalog import PlaceCatalog


class NavBridgeNode(Node):
    """이름 기반 목적지를 로컬 액션 서버를 통해 Nav2 목표로 변환 기능."""

    def __init__(self) -> None:
        super().__init__('nav_bridge_node')
        self.declare_parameter('require_goal_orientation', False)
        self._require_goal_orientation = bool(self.get_parameter('require_goal_orientation').value)
        self.declare_parameter('arrival_distance_m', 0.10)
        self._arrival_distance_m: float = float(self.get_parameter('arrival_distance_m').value)
        self._robot_x: float = 0.0
        self._robot_y: float = 0.0
        self._has_robot_pose: bool = False

        self._nav_client = ActionClient(self, NavigateToPose, 'navigate_to_pose')
        self._orientation_mode_sub = self.create_subscription(
            Bool,
            '/assistant/navigation/require_goal_orientation',
            self._on_orientation_mode,
            10,
        )
        self._amcl_pose_sub = self.create_subscription(
            PoseWithCovarianceStamped,
            '/amcl_pose',
            self._on_amcl_pose,
            10,
        )
        self._active_nav_goal_handles: dict[int, Any] = {}
        self._action_server = ActionServer(
            self,
            GuideToNamedPlace,
            '/assistant/guide_to_named_place',
            execute_callback=self._execute_goal,
            goal_callback=self._on_goal_request,
            cancel_callback=self._on_cancel_request,
        )

        self.get_logger().info('Nav bridge ready.')

    def _on_amcl_pose(self, message: PoseWithCovarianceStamped) -> None:
        self._robot_x = message.pose.pose.position.x
        self._robot_y = message.pose.pose.position.y
        self._has_robot_pose = True

    def _on_orientation_mode(self, message: Bool) -> None:
        self._require_goal_orientation = bool(message.data)
        mode = 'enabled' if self._require_goal_orientation else 'disabled'
        self.get_logger().info(f'Goal orientation requirement updated: {mode}')

    def _on_goal_request(self, goal_request: GuideToNamedPlace.Goal) -> GoalResponse:
        place_name = goal_request.place_name.strip()
        if not self._named_place_exists(place_name):
            self.get_logger().warn(f'Unknown place requested: {place_name}')
            return GoalResponse.REJECT
        return GoalResponse.ACCEPT

    def _on_cancel_request(self, goal_handle: ServerGoalHandle) -> CancelResponse:
        self.get_logger().warn(f'Cancel requested for named-place goal: {goal_handle.request.place_name}')
        nav_goal_handle = self._active_nav_goal_handles.get(id(goal_handle))
        if nav_goal_handle is not None:
            try:
                nav_goal_handle.cancel_goal_async()
            except Exception as exc:
                self.get_logger().warn(f'Failed to propagate cancel to Nav2: {exc}')
        return CancelResponse.ACCEPT

    async def _execute_goal(self, goal_handle: ServerGoalHandle) -> GuideToNamedPlace.Result:
        place_name = goal_handle.request.place_name.strip()
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
        goal_x = target_pose.pose.position.x
        goal_y = target_pose.pose.position.y

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

        self._active_nav_goal_handles[id(goal_handle)] = nav_goal_handle
        nav_result_future = nav_goal_handle.get_result_async()
        while not nav_result_future.done():
            if goal_handle.is_cancel_requested:
                try:
                    await nav_goal_handle.cancel_goal_async()
                except Exception as exc:
                    self.get_logger().warn(f'Nav2 cancel request failed: {exc}')
                goal_handle.canceled()
                result = GuideToNamedPlace.Result()
                result.success = False
                result.message = f'Navigation cancelled for {place_name}.'
                self._active_nav_goal_handles.pop(id(goal_handle), None)
                return result
            if self._has_robot_pose:
                dist = math.sqrt((self._robot_x - goal_x) ** 2 + (self._robot_y - goal_y) ** 2)
                if dist <= self._arrival_distance_m:
                    self.get_logger().info(
                        f'Proximity arrival at {place_name}: dist={dist:.2f}m <= {self._arrival_distance_m}m'
                    )
                    try:
                        await nav_goal_handle.cancel_goal_async()
                    except Exception:
                        pass
                    self._active_nav_goal_handles.pop(id(goal_handle), None)
                    goal_handle.succeed()
                    result = GuideToNamedPlace.Result()
                    result.success = True
                    result.message = f'Arrived at {place_name} (proximity).'
                    return result
            await asyncio.sleep(0.1)

        nav_result = await nav_result_future
        self._active_nav_goal_handles.pop(id(goal_handle), None)

        result = GuideToNamedPlace.Result()
        if nav_result.status == GoalStatus.STATUS_CANCELED:
            goal_handle.canceled()
            result.success = False
            result.message = f'Navigation cancelled for {place_name}.'
            return result
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
        if parse_coordinate_target(place_name) is not None:
            return True
        place_catalog = PlaceCatalog()
        return place_catalog.resolve(place_name) in place_catalog.named_places()

    def _build_pose(self, place_name: str) -> PoseStamped:
        coordinate_target = parse_coordinate_target(place_name)
        if coordinate_target is not None:
            pose = PoseStamped()
            pose.header.frame_id = coordinate_target.frame_id
            pose.header.stamp = self.get_clock().now().to_msg()
            pose.pose.position.x = coordinate_target.x
            pose.pose.position.y = coordinate_target.y
            pose.pose.position.z = 0.0
            if self._require_goal_orientation:
                pose.pose.orientation = self._quaternion_from_yaw(coordinate_target.yaw)
            else:
                pose.pose.orientation.w = 1.0
            return pose

        place_catalog = PlaceCatalog()
        canonical_name = place_catalog.resolve(place_name)
        metadata = place_catalog.place_metadata()[canonical_name]
        frame_id = str(metadata.get('frame_id', 'map'))
        x_value = float(metadata.get('x', 0.0))
        y_value = float(metadata.get('y', 0.0))

        pose = PoseStamped()
        pose.header.frame_id = frame_id
        pose.header.stamp = self.get_clock().now().to_msg()
        pose.pose.position.x = x_value
        pose.pose.position.y = y_value
        pose.pose.position.z = 0.0
        require_orientation = self._resolve_goal_orientation_requirement(metadata)
        if require_orientation:
            if 'orientation_z' in metadata and 'orientation_w' in metadata:
                pose.pose.orientation.z = float(metadata.get('orientation_z', 0.0))
                pose.pose.orientation.w = float(metadata.get('orientation_w', 1.0))
            else:
                yaw_value = float(metadata.get('yaw', 0.0))
                pose.pose.orientation = self._quaternion_from_yaw(yaw_value)
        else:
            pose.pose.orientation.w = 1.0
        return pose

    def _resolve_goal_orientation_requirement(self, metadata: dict[str, object]) -> bool:
        raw = metadata.get('require_goal_orientation')
        if isinstance(raw, bool):
            return raw
        if isinstance(raw, (int, float)):
            return bool(raw)
        if isinstance(raw, str):
            normalized = raw.strip().lower()
            if normalized in {'1', 'true', 'yes', 'on'}:
                return True
            if normalized in {'0', 'false', 'no', 'off'}:
                return False
        # Named places default to position-only arrival unless explicitly opted in.
        # This avoids Nav2 RotateToGoal stalls at desks/waypoints near the goal.
        return False

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
