from __future__ import annotations

from assistant_interfaces.msg import AssistantIntent
from geometry_msgs.msg import Twist

from std_msgs.msg import Bool, String
from std_srvs.srv import Trigger

import rclpy
from rclpy.node import Node
from rclpy.timer import Timer


class TaskManagerNode(Node):
    """현재 활성화된 로봇 작업을 추적하고 취소 요청을 처리한다."""

    def __init__(self) -> None:
        super().__init__('task_manager_node')

        self.declare_parameter('guide_forward_speed_mps', 0.12)
        self.declare_parameter('guide_forward_duration_sec', 3.0)
        self.declare_parameter('guide_motion_publish_period_sec', 0.1)

        self._active_task = ''
        self._motion_stop_time = None
        self._motion_timer: Timer | None = None
        self._task_status_publisher = self.create_publisher(String, '/assistant/task_status', 10)
        self._status_publisher = self.create_publisher(String, '/assistant/status_text', 10)
        self._cmd_vel_publisher = self.create_publisher(Twist, '/assistant/cmd_vel', 10)

        self.create_subscription(AssistantIntent, '/assistant/intent', self._on_intent, 10)
        self.create_subscription(Bool, '/assistant/emergency_stop', self._on_emergency_stop, 10)
        self.create_service(Trigger, '/assistant/cancel_current_task', self._handle_cancel_current_task)

        self.get_logger().info('Task manager ready.')

    def _on_intent(self, message: AssistantIntent) -> None:
        requested_intent = message.intent_name
        if requested_intent not in {'guide_to_place', 'move_forward', 'follow_me', 'go_home'}:
            return

        if self._active_task:
            self.get_logger().warn(
                f'Ignoring task request {requested_intent} because {self._active_task} is already active.'
            )
            self._task_status_publisher.publish(
                String(data=f'rejected:{requested_intent}:busy_with:{self._active_task}')
            )
            return

        self._active_task = requested_intent
        self._task_status_publisher.publish(String(data=f'started:{requested_intent}'))
        self._status_publisher.publish(String(data=f'Active task started: {requested_intent}'))
        self.get_logger().info(f'Active task set to {requested_intent}.')

        if requested_intent in {'guide_to_place', 'move_forward'}:
            self._start_forward_motion()

    def _on_emergency_stop(self, message: Bool) -> None:
        if not message.data or not self._active_task:
            return
        self.get_logger().warn(f'Emergency stop canceling active task: {self._active_task}')
        self._stop_motion()
        self._task_status_publisher.publish(String(data=f'canceled:{self._active_task}:emergency_stop'))
        self._status_publisher.publish(String(data='Emergency stop canceled the active task.'))
        self._active_task = ''

    def _handle_cancel_current_task(self, request: Trigger.Request, response: Trigger.Response) -> Trigger.Response:
        del request
        if not self._active_task:
            response.success = False
            response.message = 'No active task to cancel.'
            return response

        canceled_task = self._active_task
        self._stop_motion()
        self._active_task = ''
        self._task_status_publisher.publish(String(data=f'canceled:{canceled_task}:service_request'))
        response.success = True
        response.message = f'Canceled task: {canceled_task}'
        return response

    def _start_forward_motion(self) -> None:
        self._stop_motion()

        duration_seconds = float(self.get_parameter('guide_forward_duration_sec').value)
        publish_period_seconds = float(self.get_parameter('guide_motion_publish_period_sec').value)
        self._motion_stop_time = self.get_clock().now().nanoseconds / 1e9 + max(0.1, duration_seconds)
        self._motion_timer = self.create_timer(publish_period_seconds, self._publish_forward_motion)
        self._status_publisher.publish(String(data='안내용 임시 직진을 시작합니다.'))

    def _publish_forward_motion(self) -> None:
        if self._active_task not in {'guide_to_place', 'move_forward'}:
            self._stop_motion()
            return

        now_seconds = self.get_clock().now().nanoseconds / 1e9
        if self._motion_stop_time is not None and now_seconds >= self._motion_stop_time:
            self._stop_motion()
            completed_task = self._active_task
            self._task_status_publisher.publish(String(data=f'completed:{completed_task}:straight_motion'))
            self._status_publisher.publish(String(data='임시 직진 안내를 완료했습니다.'))
            self._active_task = ''
            return

        twist = Twist()
        twist.linear.x = float(self.get_parameter('guide_forward_speed_mps').value)
        self._cmd_vel_publisher.publish(twist)

    def _stop_motion(self) -> None:
        if self._motion_timer is not None:
            self._motion_timer.cancel()
            self.destroy_timer(self._motion_timer)
            self._motion_timer = None

        self._motion_stop_time = None
        self._cmd_vel_publisher.publish(Twist())


def main(args: list[str] | None = None) -> None:
    rclpy.init(args=args)
    node = TaskManagerNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()
