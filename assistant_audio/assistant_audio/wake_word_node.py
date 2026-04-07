from __future__ import annotations

from std_msgs.msg import Bool, String

import rclpy
from rclpy.node import Node


# 기본으로 인식할 wake word 목록 (소문자 정규화 후 매칭)
_DEFAULT_WAKE_WORDS = ('omni', '옴니', '옴니야')


class WakeWordNode(Node):
    """웨이크 워드 이벤트를 발행한다.

    real 모드에서는 마이크 + VAD + 키워드 감지 엔진(pvporcupine 등)으로 교체한다.
    현재는 타이머 기반 mock 또는 /assistant/manual_wake 토픽으로 수동 트리거 가능.

    지원 파라미터:
        wake_word_enabled   (bool)  : false 면 감지 비활성화
        wake_words          (string): 콤마로 구분된 인식 키워드 목록
                                      기본값 = "omni,옴니,옴니야"
        mock_mode           (bool)  : true 면 타이머로 자동 트리거
        mock_trigger_period_sec (double): mock 트리거 간격(0 = 비활성)
    """

    def __init__(self) -> None:
        super().__init__('wake_word_node')

        self.declare_parameter('wake_word_enabled', True)
        self.declare_parameter('wake_words', ','.join(_DEFAULT_WAKE_WORDS))
        # legacy 단일 키워드 파라미터 호환 유지
        self.declare_parameter('wake_word_text', '')
        self.declare_parameter('mock_mode', True)
        self.declare_parameter('mock_trigger_period_sec', 0.0)

        self._wake_publisher = self.create_publisher(Bool, '/assistant/wake_detected', 10)
        self._status_publisher = self.create_publisher(String, '/assistant/status_text', 10)

        self._wake_word_enabled: bool = self.get_parameter('wake_word_enabled').value

        # wake_words 파라미터(콤마 구분) + legacy wake_word_text 통합
        raw: str = str(self.get_parameter('wake_words').value).strip()
        legacy: str = str(self.get_parameter('wake_word_text').value).strip().lower()
        words = {w.strip().lower() for w in raw.split(',') if w.strip()}
        if legacy:
            words.add(legacy)
        self._wake_words: frozenset[str] = frozenset(words) or frozenset(_DEFAULT_WAKE_WORDS)

        self._mock_mode: bool = self.get_parameter('mock_mode').value
        self._mock_trigger_period_sec: float = float(
            self.get_parameter('mock_trigger_period_sec').value
        )

        # 수동 트리거 토픽 (ROS2 publish /assistant/manual_wake true 로 테스트 가능)
        self.create_subscription(Bool, '/assistant/manual_wake', self._on_manual_wake, 10)

        if self._mock_mode and self._mock_trigger_period_sec > 0.0:
            self.create_timer(self._mock_trigger_period_sec, self._publish_mock_wake)
            self.get_logger().info(
                f'Mock wake-word mode enabled. '
                f'Triggering every {self._mock_trigger_period_sec:.1f}s. '
                f'Wake words: {sorted(self._wake_words)}'
            )
        else:
            self.get_logger().info(
                f'Wake-word node ready. '
                f'Recognized words: {sorted(self._wake_words)}. '
                f'Waiting for real backend integration.'
            )

    def trigger_wake(self, matched_word: str = 'omni') -> None:
        """외부(real STT/VAD 백엔드)에서 wake word 매칭 시 호출하는 공개 메서드."""
        if not self._wake_word_enabled:
            return
        self._wake_publisher.publish(Bool(data=True))
        self._status_publisher.publish(String(data=f'Wake word detected: {matched_word}'))
        self.get_logger().info(f'Wake detected: "{matched_word}"')

    def _on_manual_wake(self, message: Bool) -> None:
        if message.data:
            self.trigger_wake('manual')

    def _publish_mock_wake(self) -> None:
        self.trigger_wake('omni')


def main(args: list[str] | None = None) -> None:
    rclpy.init(args=args)
    node = WakeWordNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()

