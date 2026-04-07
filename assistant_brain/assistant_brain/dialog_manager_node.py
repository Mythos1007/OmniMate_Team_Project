from __future__ import annotations

from assistant_brain.state_machine import (
    ACTING,
    EMERGENCY_STOP,
    IDLE,
    LISTENING,
    PROCESSING,
    RESPONDING,
    SLEEPING,
    ERROR,
    # backward-compat aliases (기존 코드와의 호환)
    UNDERSTANDING,
    SPEAKING,
    AssistantStateMachine,
)
from assistant_interfaces.msg import AssistantIntent, AssistantState, VoiceTranscript

from std_msgs.msg import Bool, String

import rclpy
from rclpy.node import Node
from rclpy.timer import Timer


class DialogManagerNode(Node):
    """어시스턴트 대화/작업 상태 머신 관리 기능.

    상태 흐름:
        SLEEPING ─(wake word)→ LISTENING ─(transcript)→ PROCESSING
        PROCESSING ─(command intent)→ ACTING ─(done)→ IDLE
        PROCESSING ─(query/chat intent)→ RESPONDING ─(done)→ IDLE
        IDLE ─(sleep timeout)→ SLEEPING
    """

    def __init__(self) -> None:
        super().__init__('dialog_manager_node')

        self.declare_parameter('speech_reset_delay_sec', 2.0)
        self.declare_parameter('emergency_reset_delay_sec', 1.0)
        self.declare_parameter('sleep_timeout_sec', 30.0)   # IDLE → SLEEPING 타임아웃

        self._state_machine = AssistantStateMachine()
        self._pending_reset_timer: Timer | None = None
        self._sleep_timer: Timer | None = None

        self._state_publisher = self.create_publisher(AssistantState, '/assistant/state', 10)
        self._speak_publisher = self.create_publisher(String, '/assistant/speak', 10)
        self._status_publisher = self.create_publisher(String, '/assistant/status_text', 10)

        self.create_subscription(Bool, '/assistant/wake_detected', self._on_wake_detected, 10)
        self.create_subscription(VoiceTranscript, '/assistant/transcript', self._on_transcript, 10)
        self.create_subscription(AssistantIntent, '/assistant/intent', self._on_intent, 10)
        self.create_subscription(Bool, '/assistant/emergency_stop', self._on_emergency_stop, 10)
        self.create_subscription(String, '/assistant/task_status', self._on_task_status, 10)

        # 시작 시 SLEEPING 으로 진입
        self._state_machine.transition(SLEEPING)
        self._publish_state('Assistant started. Entering sleep mode.')

    # ─── 외부 이벤트 핸들러 ─────────────────────────────────────────────────

    def _on_wake_detected(self, message: Bool) -> None:
        if not message.data:
            return
        self._cancel_pending_reset()
        self._cancel_sleep_timer()
        # SLEEPING 또는 IDLE 모두 LISTENING 으로
        self._transition(LISTENING, '', 'Wake word detected.')

    def _on_transcript(self, message: VoiceTranscript) -> None:
        if not message.text:
            return
        self._cancel_sleep_timer()
        self._transition(PROCESSING, '', f'Processing transcript: {message.text}')

    def _on_intent(self, message: AssistantIntent) -> None:
        intent_name = message.intent_name
        intent_category = getattr(message, 'intent_category', '')

        if intent_name == 'stop':
            self.get_logger().info('Stop intent: waiting for safety gate emergency stop.')
            return

        # command intent → ACTING
        if intent_category == 'command' or intent_name in {
            'guide_to_place', 'move_forward', 'move_backward',
            'turn_left', 'turn_right', 'follow_me', 'go_home',
            'start_patrol', 'pause_patrol', 'resume_patrol', 'deliver_mail',
        }:
            self._cancel_pending_reset()
            self._transition(ACTING, intent_name, f'Acting on command: {intent_name}')
            return

        # query / chat intent → RESPONDING
        self._transition(RESPONDING, intent_name, f'Responding to {intent_category or "intent"}: {intent_name}')
        self._schedule_reset(float(self.get_parameter('speech_reset_delay_sec').value))

    def _on_emergency_stop(self, message: Bool) -> None:
        if not message.data:
            return
        self._cancel_pending_reset()
        self._cancel_sleep_timer()
        self._transition(EMERGENCY_STOP, 'stop', 'Emergency stop active.')
        self._speak_publisher.publish(String(data='정지했습니다.'))
        self._schedule_reset(float(self.get_parameter('emergency_reset_delay_sec').value))

    def _on_task_status(self, message: String) -> None:
        if message.data.startswith(('completed:', 'canceled:', 'failed:')):
            self._transition(IDLE, '', f'Task status: {message.data}')
            self._start_sleep_timer()

    # ─── 타이머 관리 ────────────────────────────────────────────────────────

    def _schedule_reset(self, delay_sec: float) -> None:
        self._cancel_pending_reset()
        self._pending_reset_timer = self.create_timer(delay_sec, self._reset_to_idle_once)

    def _reset_to_idle_once(self) -> None:
        self._cancel_pending_reset()
        self._transition(IDLE, '', 'Returned to idle.')
        self._start_sleep_timer()

    def _cancel_pending_reset(self) -> None:
        if self._pending_reset_timer is not None:
            self._pending_reset_timer.cancel()
            self.destroy_timer(self._pending_reset_timer)
            self._pending_reset_timer = None

    def _start_sleep_timer(self) -> None:
        """IDLE 상태 유지 후 sleep_timeout_sec 초 경과 시 SLEEPING 으로 전이."""
        self._cancel_sleep_timer()
        timeout = float(self.get_parameter('sleep_timeout_sec').value)
        if timeout > 0:
            self._sleep_timer = self.create_timer(timeout, self._enter_sleep_once)

    def _enter_sleep_once(self) -> None:
        self._cancel_sleep_timer()
        if self._state_machine.snapshot.state == IDLE:
            self._transition(SLEEPING, '', 'No activity. Entering sleep mode.')

    def _cancel_sleep_timer(self) -> None:
        if self._sleep_timer is not None:
            self._sleep_timer.cancel()
            self.destroy_timer(self._sleep_timer)
            self._sleep_timer = None

    def _transition(self, next_state: str, current_task: str, status_text: str) -> None:
        if not self._state_machine.transition(next_state, current_task=current_task):
            current_state = self._state_machine.snapshot.state
            self.get_logger().warn(f'Invalid state transition: {current_state} -> {next_state}')
            return
        self._publish_state(status_text)

    def _publish_state(self, status_text: str) -> None:
        self._state_publisher.publish(self._state_machine.as_message())
        self._status_publisher.publish(String(data=status_text))
        snapshot = self._state_machine.snapshot
        self.get_logger().info(
            f'State={snapshot.state}, current_task={snapshot.current_task}, busy={snapshot.busy}'
        )


def main(args: list[str] | None = None) -> None:
    rclpy.init(args=args)
    node = DialogManagerNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()
