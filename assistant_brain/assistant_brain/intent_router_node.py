from __future__ import annotations

from datetime import datetime

from assistant_brain.chat_responder import ChatResponder
from assistant_brain.intent_rules import (
    INTENT_CATEGORIES,
    IntentClassification,
    classify_intent,
)
from assistant_brain.command_dispatcher import CommandDispatcher
from assistant_commands import CanonicalCommand, CommandNormalizer
from assistant_interfaces.msg import AssistantIntent, VoiceTranscript
from assistant_interfaces.srv import GetRobotStatus

from std_msgs.msg import String

import rclpy
from rclpy.node import Node
from rclpy.task import Future


class IntentRouterNode(Node):
    """전사 텍스트를 의도로 분류하고 command / query / chat 으로 라우팅한다.

    분류 흐름:
        transcript → CommandNormalizer (규칙 기반) → CanonicalCommand
                   → 매칭 실패 → IntentRules (키워드 기반) → IntentClassification
        → intent_category 에 따라 command / query / chat 분기
    """

    def __init__(self) -> None:
        super().__init__('intent_router_node')

        self._intent_publisher = self.create_publisher(AssistantIntent, '/assistant/intent', 10)
        self._speak_publisher = self.create_publisher(String, '/assistant/speak', 10)
        self._status_publisher = self.create_publisher(String, '/assistant/status_text', 10)
        self._status_client = self.create_client(GetRobotStatus, '/assistant/get_robot_status')

        self._command_normalizer = CommandNormalizer()
        self._command_dispatcher = CommandDispatcher()
        self._chat_responder = ChatResponder()

        self.create_subscription(VoiceTranscript, '/assistant/transcript', self._on_transcript, 10)
        self.get_logger().info('Intent router ready.')

    # ─── 수신 ───────────────────────────────────────────────────────────────

    def _on_transcript(self, message: VoiceTranscript) -> None:
        classification = self._classify_transcript(message.text)
        self._publish_intent(classification)
        self._route_by_category(classification)

    # ─── 분류 ───────────────────────────────────────────────────────────────

    def _classify_transcript(self, text: str) -> IntentClassification:
        """CommandNormalizer 먼저 시도, 실패 시 키워드 규칙으로 분류."""
        normalized = self._command_normalizer.normalize(text)
        if normalized.command != 'unknown':
            return IntentClassification(
                intent_name=normalized.command,
                confidence=0.98,
                slots={k: str(v) for k, v in normalized.args.items()},
                intent_category=INTENT_CATEGORIES.get(normalized.command, 'command'),
            )
        return classify_intent(text)

    # ─── 발행 ───────────────────────────────────────────────────────────────

    def _publish_intent(self, c: IntentClassification) -> None:
        msg = AssistantIntent()
        msg.intent_name = c.intent_name
        msg.slot_keys = list(c.slots.keys())
        msg.slot_values = list(c.slots.values())
        msg.confidence = c.confidence
        msg.intent_category = c.intent_category  # added field
        self._intent_publisher.publish(msg)
        self.get_logger().info(
            f'Intent: {c.intent_name} [{c.intent_category}] ({c.confidence:.2f})'
        )

    # ─── 카테고리 기반 라우팅 ───────────────────────────────────────────────

    def _route_by_category(self, c: IntentClassification) -> None:
        if c.intent_category == 'command':
            self._handle_command(c)
        elif c.intent_category == 'query':
            self._handle_query(c)
        else:  # 'chat' (unknown 포함)
            self._handle_chat(c)

    # ─── command 처리 ───────────────────────────────────────────────────────

    def _handle_command(self, c: IntentClassification) -> None:
        intent_name = c.intent_name

        # guide_to_place는 command_schema 이름이 다름
        if intent_name == 'guide_to_place':
            place = c.slots.get('place_name', 'unknown')
            result = self._command_dispatcher.dispatch(
                CanonicalCommand(command='guide_to_location', args={'location': place})
            )
            self._status_publisher.publish(String(data=result.status_text))
            self._speak(result.speak_text)
            return

        if intent_name == 'follow_me':
            self._status_publisher.publish(String(data='Routing follow-me request.'))
            return

        if intent_name == 'go_home':
            self._status_publisher.publish(String(data='Routing go-home request.'))
            return

        # 나머지 command intent는 intent_name == CanonicalCommandName 이므로 직접 dispatch
        if intent_name == 'stop':
            # stop은 safety_gate 가 emergency_stop 을 발행하므로 여기서 별도 처리 불필요.
            # dialog_manager 에게만 intent를 전달하면 된다.
            return

        result = self._command_dispatcher.dispatch(
            CanonicalCommand(command=intent_name, args=self._coerce_slots(c.slots))  # type: ignore[arg-type]
        )
        self._status_publisher.publish(String(data=result.status_text))
        self._speak(result.speak_text)

    # ─── query 처리 ─────────────────────────────────────────────────────────

    def _handle_query(self, c: IntentClassification) -> None:
        intent_name = c.intent_name

        if intent_name == 'get_current_time':
            self._speak(f'현재 시각은 {datetime.now().strftime("%H:%M")}입니다.')
            return

        if intent_name in {'get_robot_status', 'get_battery_status', 'status_query'}:
            self._request_robot_status(intent_name)
            return

        if intent_name == 'weather_query':
            result = self._command_dispatcher.dispatch(
                CanonicalCommand(command='weather_query')
            )
            self._speak(result.speak_text)
            return

        if intent_name in {'alarm_list', 'schedule_list'}:
            result = self._command_dispatcher.dispatch(CanonicalCommand(command=intent_name))
            self._speak(result.speak_text)
            return

        # 기타 query
        self._speak('조회 중입니다. 잠시 기다려 주세요.')

    # ─── chat 처리 ──────────────────────────────────────────────────────────

    def _handle_chat(self, c: IntentClassification) -> None:
        response = self._chat_responder.respond(c)
        self._speak(response)

    # ─── 공통 헬퍼 ─────────────────────────────────────────────────────────

    def _coerce_slots(self, slots: dict[str, str]) -> dict[str, object]:
        coerced: dict[str, object] = {}
        for key, value in slots.items():
            coerced[key] = float(value) if key in {'distance', 'duration'} else value
        return coerced

    def _request_robot_status(self, intent_name: str) -> None:
        if not self._status_client.wait_for_service(timeout_sec=0.5):
            self._speak('로봇 상태 서비스를 아직 사용할 수 없어요.')
            return
        future = self._status_client.call_async(GetRobotStatus.Request())
        future.add_done_callback(
            lambda f, req=intent_name: self._on_status_response(f, req)
        )

    def _on_status_response(self, future: Future, requested_intent: str) -> None:
        try:
            response = future.result()
        except Exception as error:  # noqa: BLE001
            self.get_logger().error(f'Failed to query robot status: {error}')
            self._speak('로봇 상태를 읽지 못했어요.')
            return

        if requested_intent == 'get_battery_status':
            self._speak(f'배터리는 {response.battery_percent:.0f}퍼센트입니다.')
            return

        self._speak(
            f'로봇 모드는 {response.robot_mode}이고, '
            f'현재 위치는 {response.location_name}입니다. '
            f'배터리는 {response.battery_percent:.0f}퍼센트입니다.'
        )

    def _speak(self, text: str) -> None:
        self._speak_publisher.publish(String(data=text))
        self._status_publisher.publish(String(data=f'TTS: {text}'))


def main(args: list[str] | None = None) -> None:
    rclpy.init(args=args)
    node = IntentRouterNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()



class IntentRouterNode(Node):
    """전사 텍스트를 의도로 분류하고 음성 응답 또는 로봇 처리로 라우팅한다."""

    def __init__(self) -> None:
        super().__init__('intent_router_node')

        self._intent_publisher = self.create_publisher(AssistantIntent, '/assistant/intent', 10)
        self._speak_publisher = self.create_publisher(String, '/assistant/speak', 10)
        self._status_publisher = self.create_publisher(String, '/assistant/status_text', 10)
        self._status_client = self.create_client(GetRobotStatus, '/assistant/get_robot_status')
        self._command_normalizer = CommandNormalizer()
        self._command_dispatcher = CommandDispatcher()

        self.create_subscription(VoiceTranscript, '/assistant/transcript', self._on_transcript, 10)
        self.get_logger().info('Intent router ready.')

    def _on_transcript(self, message: VoiceTranscript) -> None:
        classification = self._classify_transcript(message.text)
        self._publish_intent(classification)
        self._route_intent(classification)

    def _classify_transcript(self, text: str) -> IntentClassification:
        normalized_command = self._command_normalizer.normalize(text)
        if normalized_command.command != 'unknown':
            return IntentClassification(
                intent_name=normalized_command.command,
                confidence=0.98,
                slots={key: str(value) for key, value in normalized_command.args.items()},
            )

        return classify_intent(text)

    def _publish_intent(self, classification: IntentClassification) -> None:
        message = AssistantIntent()
        message.intent_name = classification.intent_name
        message.slot_keys = list(classification.slots.keys())
        message.slot_values = list(classification.slots.values())
        message.confidence = classification.confidence
        self._intent_publisher.publish(message)
        self.get_logger().info(
            f'Intent classified: {classification.intent_name} ({classification.confidence:.2f})'
        )

    def _route_intent(self, classification: IntentClassification) -> None:
        intent_name = classification.intent_name

        if intent_name == 'smalltalk':
            self._publish_speak('안녕하세요. 무엇을 도와드릴까요?')
            return

        if intent_name == 'unknown':
            self._publish_speak('아직 그 요청은 이해하지 못했어요.')
            return

        if intent_name == 'get_current_time':
            now_text = datetime.now().strftime('%H:%M')
            self._publish_speak(f'현재 시각은 {now_text}입니다.')
            return

        if intent_name in {'get_robot_status', 'get_battery_status'}:
            self._request_robot_status(intent_name)
            return

        if intent_name == 'status_query':
            self._request_robot_status('get_robot_status')
            return

        if intent_name == 'guide_to_place':
            place_name = classification.slots.get('place_name', 'unknown')
            result = self._command_dispatcher.dispatch(
                CanonicalCommand(command='guide_to_location', args={'location': place_name})
            )
            self._status_publisher.publish(String(data=result.status_text))
            self._publish_speak(result.speak_text)
            return

        if intent_name in {
            'move_forward',
            'move_backward',
            'turn_left',
            'turn_right',
            'stop',
            'start_patrol',
            'pause_patrol',
            'resume_patrol',
        }:
            result = self._command_dispatcher.dispatch(
                CanonicalCommand(command=intent_name, args=self._coerce_slot_values(classification.slots))
            )
            self._status_publisher.publish(String(data=result.status_text))
            self._publish_speak(result.speak_text)
            return

        if intent_name == 'follow_me':
            self._status_publisher.publish(String(data='Routing follow-me request.'))
            return

        if intent_name == 'go_home':
            self._status_publisher.publish(String(data='Routing go-home request.'))
            return

    def _coerce_slot_values(self, slots: dict[str, str]) -> dict[str, object]:
        coerced: dict[str, object] = {}
        for key, value in slots.items():
            if key in {'distance', 'duration'}:
                coerced[key] = float(value)
                continue
            coerced[key] = value
        return coerced

    def _request_robot_status(self, intent_name: str) -> None:
        if not self._status_client.wait_for_service(timeout_sec=0.5):
            self._publish_speak('로봇 상태 서비스를 아직 사용할 수 없어요.')
            return

        future = self._status_client.call_async(GetRobotStatus.Request())
        future.add_done_callback(
            lambda completed_future, requested_intent=intent_name: self._on_status_response(
                completed_future,
                requested_intent,
            )
        )

    def _on_status_response(self, future: Future, requested_intent: str) -> None:
        try:
            response = future.result()
        except Exception as error:  # noqa: BLE001
            self.get_logger().error(f'Failed to query robot status: {error}')
            self._publish_speak('로봇 상태를 읽지 못했어요.')
            return

        if requested_intent == 'get_battery_status':
            self._publish_speak(f'배터리는 {response.battery_percent:.0f}퍼센트입니다.')
            return

        self._publish_speak(
            f'로봇 모드는 {response.robot_mode}이고, 현재 위치는 {response.location_name}입니다. '
            f'배터리는 {response.battery_percent:.0f}퍼센트입니다.'
        )

    def _publish_speak(self, text: str) -> None:
        self._speak_publisher.publish(String(data=text))
        self._status_publisher.publish(String(data=f'음성 응답 대기열에 추가됨: {text}'))


def main(args: list[str] | None = None) -> None:
    rclpy.init(args=args)
    node = IntentRouterNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()
