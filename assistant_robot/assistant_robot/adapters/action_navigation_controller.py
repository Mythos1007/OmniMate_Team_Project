from __future__ import annotations

from action_msgs.msg import GoalStatus
from assistant_interfaces.action import GuideToNamedPlace

from rclpy.action import ActionClient
from rclpy.node import Node

from assistant_robot.interfaces.navigation_controller import (
    BaseNavigationController,
    NavigationHandle,
    NavigationState,
)


class ActionNavigationController(BaseNavigationController):
    def __init__(self, node: Node, *, action_name: str = '/assistant/guide_to_named_place') -> None:
        self._node = node
        self._client = ActionClient(node, GuideToNamedPlace, action_name)

    def start_navigation(self, target_location: str, *, metadata: dict[str, object] | None = None) -> NavigationHandle:
        merged_metadata = dict(metadata or {})
        handle = NavigationHandle(
            navigation_id=f'action:{target_location}',
            target_location=target_location,
            status=NavigationState.NAVIGATING,
            steps_remaining=0,
            metadata=merged_metadata,
        )

        if not self._client.wait_for_server(timeout_sec=1.0):
            handle.status = NavigationState.FAILED
            handle.metadata['error'] = 'guide_to_named_place action server unavailable'
            return handle

        goal = GuideToNamedPlace.Goal()
        goal.place_name = target_location
        handle.metadata['send_goal_future'] = self._client.send_goal_async(goal)
        return handle

    def poll_navigation(self, handle: NavigationHandle) -> NavigationHandle:
        if handle.status != NavigationState.NAVIGATING:
            return handle

        send_goal_future = handle.metadata.get('send_goal_future')
        if send_goal_future is not None and send_goal_future.done():
            goal_handle = send_goal_future.result()
            handle.metadata.pop('send_goal_future', None)
            if goal_handle is None or not goal_handle.accepted:
                handle.status = NavigationState.FAILED
                return handle
            handle.metadata['goal_handle'] = goal_handle
            handle.metadata['result_future'] = goal_handle.get_result_async()
            return handle

        result_future = handle.metadata.get('result_future')
        if result_future is not None and result_future.done():
            result = result_future.result()
            status = getattr(result, 'status', None)
            if status == GoalStatus.STATUS_SUCCEEDED:
                handle.status = NavigationState.ARRIVED
            elif status == GoalStatus.STATUS_CANCELED:
                handle.status = NavigationState.CANCELLED
            else:
                handle.status = NavigationState.FAILED
        return handle

    def cancel_navigation(self, handle: NavigationHandle) -> None:
        goal_handle = handle.metadata.get('goal_handle')
        if goal_handle is not None:
            goal_handle.cancel_goal_async()
        handle.status = NavigationState.CANCELLED

    def get_current_location(self) -> str:
        return 'unknown'
