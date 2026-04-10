from __future__ import annotations

from assistant_interfaces.msg import VoiceTranscript
from assistant_audio.providers.stt_provider import (
    FasterWhisperSTTProvider,
    MockSTTProvider,
    PocketsphinxSTTProvider,
    STTProvider,
    resolve_arecord_audio_device,
)

from std_msgs.msg import Bool, String

from threading import Thread
import time

import rclpy
from rclpy.node import Node


_ASSISTANT_COMMAND_TOPIC = '/assistant/command_text'


class STTNode(Node):
    """웨이크 이벤트 수신 후 음성 인식 결과 메시지 발행 기능.

    1단계: 모의 프로바이더 + 지연된 가짜 전사 발행.
    TODO: 마이크 스트리밍, VAD, Whisper/Vosk 교체형 프로바이더 연동.
    """

    def __init__(self) -> None:
        super().__init__('stt_node')

        self.declare_parameter('mock_mode', True)
        self.declare_parameter('stt_backend', 'mock')
        self.declare_parameter('mock_transcript_text', 'guide me to lab')
        self.declare_parameter('mock_confidence', 0.92)
        self.declare_parameter('transcription_delay_sec', 1.5)
        self.declare_parameter('record_duration_sec', 4.0)
        self.declare_parameter('sample_rate_hz', 16000)
        self.declare_parameter('audio_channels', 1)
        self.declare_parameter('audio_device', 'default')
        self.declare_parameter('acoustic_model_dir', '/usr/share/pocketsphinx/model/en-us/en-us')
        self.declare_parameter('language_model_path', '/usr/share/pocketsphinx/model/en-us/en-us.lm.bin')
        self.declare_parameter('dictionary_path', '/usr/share/pocketsphinx/model/en-us/cmudict-en-us.dict')
        self.declare_parameter('stt_language', 'ko')
        self.declare_parameter('whisper_model_size', 'small')
        self.declare_parameter('whisper_compute_type', 'int8')
        self.declare_parameter('whisper_device', 'cpu')
        self.declare_parameter('whisper_beam_size', 5)
        self.declare_parameter('wake_topic', '/assistant/wake_detected')
        self.declare_parameter('command_topic', _ASSISTANT_COMMAND_TOPIC)
        self.declare_parameter('status_topic', '/assistant/status_text')
        self.declare_parameter('enabled_topic', '')
        self.declare_parameter('voice_input_enabled', True)

        self._voice_input_enabled = bool(self.get_parameter('voice_input_enabled').value)
        self._wake_topic = str(self.get_parameter('wake_topic').value)
        self._command_topic = str(self.get_parameter('command_topic').value)
        self._status_topic = str(self.get_parameter('status_topic').value)
        self._enabled_topic = str(self.get_parameter('enabled_topic').value).strip()
        self._provider = self._create_provider()
        self._transcript_publisher = self.create_publisher(VoiceTranscript, '/assistant/transcript', 10)
        self._command_text_publisher = self.create_publisher(String, self._command_topic, 10)
        self._status_publisher = self.create_publisher(String, self._status_topic, 10)
        self.create_subscription(Bool, self._wake_topic, self._on_wake_detected, 10)
        if self._enabled_topic:
            self.create_subscription(Bool, self._enabled_topic, self._on_voice_input_enabled, 10)

        self._pending_timer = None
        self._transcription_thread = None
        self._listening_active = False
        self._wake_started_monotonic = None
        self.get_logger().info('STT node ready.')

    def _create_provider(self) -> STTProvider:
        backend = str(self.get_parameter('stt_backend').value).strip().lower()
        mock_mode = bool(self.get_parameter('mock_mode').value)
        mock_transcript = self.get_parameter('mock_transcript_text').value
        mock_confidence = float(self.get_parameter('mock_confidence').value)
        requested_audio_device = str(self.get_parameter('audio_device').value)
        resolved_audio_device = resolve_arecord_audio_device(requested_audio_device)

        self.get_logger().info(
            f'STT audio device resolved: requested="{requested_audio_device}" '
            f'-> using="{resolved_audio_device}"'
        )

        if mock_mode or backend == 'mock':
            return MockSTTProvider(sample_text=mock_transcript, confidence=mock_confidence)

        if backend == 'pocketsphinx':
            return PocketsphinxSTTProvider(
                record_seconds=float(self.get_parameter('record_duration_sec').value),
                sample_rate_hz=int(self.get_parameter('sample_rate_hz').value),
                channels=int(self.get_parameter('audio_channels').value),
                audio_device=resolved_audio_device,
                acoustic_model_dir=str(self.get_parameter('acoustic_model_dir').value),
                language_model_path=str(self.get_parameter('language_model_path').value),
                dictionary_path=str(self.get_parameter('dictionary_path').value),
            )

        if backend == 'faster_whisper':
            return FasterWhisperSTTProvider(
                record_seconds=float(self.get_parameter('record_duration_sec').value),
                sample_rate_hz=int(self.get_parameter('sample_rate_hz').value),
                channels=int(self.get_parameter('audio_channels').value),
                audio_device=resolved_audio_device,
                model_size=str(self.get_parameter('whisper_model_size').value),
                language=str(self.get_parameter('stt_language').value),
                compute_type=str(self.get_parameter('whisper_compute_type').value),
                device=str(self.get_parameter('whisper_device').value),
                beam_size=int(self.get_parameter('whisper_beam_size').value),
            )

        self.get_logger().warn(f'Unknown stt_backend {backend}. Falling back to mock mode.')
        return MockSTTProvider(sample_text=mock_transcript, confidence=mock_confidence)

    def _on_wake_detected(self, message: Bool) -> None:
        if not self._voice_input_enabled:
            return
        if not message.data:
            return
        if self._listening_active:
            self.get_logger().warn('Wake word received while an STT request is still active. Ignoring duplicate.')
            return

        delay = float(self.get_parameter('transcription_delay_sec').value)
        self._listening_active = True
        self._wake_started_monotonic = time.monotonic()
        self._status_publisher.publish(String(data='STATE:LISTENING'))
        if self._uses_mock_provider() and delay > 0.0:
            self.get_logger().info(f'Wake word received. Mock transcription will be published in {delay:.1f}s.')
            self._pending_timer = self.create_timer(delay, self._begin_transcription)
            return

        self.get_logger().info('Wake word received. Starting transcription immediately.')
        self._begin_transcription()

    def _begin_transcription(self) -> None:
        if self._pending_timer is not None:
            self._pending_timer.cancel()
            self.destroy_timer(self._pending_timer)
            self._pending_timer = None

        self._transcription_thread = Thread(target=self._publish_transcript_once, daemon=True)
        self._transcription_thread.start()

    def _publish_transcript_once(self) -> None:
        try:
            text, confidence = self._provider.transcribe()
        except Exception as exc:
            self._log_transcription_latency('failed')
            self.get_logger().error(f'STT backend failed: {exc}')
            self._status_publisher.publish(String(data=f'STT backend failed: {exc}'))
            self._listening_active = False
            return

        if not self._voice_input_enabled:
            self.get_logger().info('STT result ignored because voice input is disabled.')
            self._listening_active = False
            self._wake_started_monotonic = None
            return

        transcript = VoiceTranscript()
        transcript.stamp = self.get_clock().now().to_msg()
        transcript.text = text
        transcript.confidence = confidence
        transcript.wake_word_used = True

        self._transcript_publisher.publish(transcript)
        self._command_text_publisher.publish(String(data=text))
        self._status_publisher.publish(String(data='STATE:PROCESSING'))
        self._status_publisher.publish(String(data=f'Transcript ready: {text}'))
        self._log_transcription_latency('completed')
        self.get_logger().info(f'Published transcript: "{text}" ({confidence:.2f})')
        self._listening_active = False

    def _on_voice_input_enabled(self, message: Bool) -> None:
        self._voice_input_enabled = bool(message.data)
        if not self._voice_input_enabled:
            if self._pending_timer is not None:
                self._pending_timer.cancel()
                self.destroy_timer(self._pending_timer)
                self._pending_timer = None
            self._listening_active = False
            self._wake_started_monotonic = None
        state_text = 'enabled' if self._voice_input_enabled else 'disabled'
        self.get_logger().info(f'STT voice input {state_text}.')

    def _uses_mock_provider(self) -> bool:
        return isinstance(self._provider, MockSTTProvider)

    def _log_transcription_latency(self, outcome: str) -> None:
        if self._wake_started_monotonic is None:
            return

        elapsed_seconds = time.monotonic() - self._wake_started_monotonic
        self.get_logger().info(f'STT latency {outcome}: {elapsed_seconds:.2f}s from wake to result.')
        self._wake_started_monotonic = None


def main(args: list[str] | None = None) -> None:
    rclpy.init(args=args)
    node = STTNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
