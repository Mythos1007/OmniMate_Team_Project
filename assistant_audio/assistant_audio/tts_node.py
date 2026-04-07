from __future__ import annotations

from assistant_audio.providers.tts_provider import (
    CartesiaTTSProvider,
    EdgeTTSProvider,
    ElevenLabsTTSProvider,
    MockTTSProvider,
    SpeechDispatcherTTSProvider,
    TTSProvider,
)

from std_msgs.msg import String

import rclpy
from rclpy.node import Node


class TTSNode(Node):
    """음성 출력 요청을 받아 TTS 백엔드로 전달한다.

    1단계에서는 오디오 재생 대신 로그만 남긴다.
    TODO: 실제 음성 합성을 위해 오디오 재생과 백엔드 선택 기능을 추가한다.
    """

    def __init__(self) -> None:
        super().__init__('tts_node')

        self.declare_parameter('tts_backend', 'mock')
        self.declare_parameter('voice_name', 'default')
        self.declare_parameter('language', 'ko')
        self.declare_parameter('fallback_voice_name', 'female1')
        self.declare_parameter('playback_command', 'gst-play-1.0')
        self.declare_parameter('elevenlabs_api_key', '')
        self.declare_parameter('elevenlabs_voice_id', '')
        self.declare_parameter('elevenlabs_model_id', 'eleven_multilingual_v2')
        self.declare_parameter('elevenlabs_output_format', 'mp3_44100_128')
        self.declare_parameter('cartesia_api_key', '')
        self.declare_parameter('cartesia_voice_id', '')
        self.declare_parameter('cartesia_model_id', 'sonic-3')
        self.declare_parameter('cartesia_output_container', 'wav')
        self.declare_parameter('cartesia_output_encoding', 'pcm_f32le')
        self.declare_parameter('cartesia_sample_rate', 44100)

        self._provider = self._create_provider()
        self._status_publisher = self.create_publisher(String, '/assistant/status_text', 10)
        self.create_subscription(String, '/assistant/speak', self._on_speak_request, 10)

        backend = self.get_parameter('tts_backend').value
        voice_name = self.get_parameter('voice_name').value
        language = self.get_parameter('language').value
        elevenlabs_voice_id = self.get_parameter('elevenlabs_voice_id').value
        elevenlabs_model_id = self.get_parameter('elevenlabs_model_id').value
        cartesia_voice_id = self.get_parameter('cartesia_voice_id').value
        cartesia_model_id = self.get_parameter('cartesia_model_id').value
        self.get_logger().info(
            'TTS node ready. '
            f'backend={backend}, voice={voice_name}, language={language}, '
            f'elevenlabs_voice_id={elevenlabs_voice_id}, elevenlabs_model_id={elevenlabs_model_id}, '
            f'cartesia_voice_id={cartesia_voice_id}, cartesia_model_id={cartesia_model_id}'
        )

    def _create_provider(self) -> TTSProvider:
        backend = str(self.get_parameter('tts_backend').value).strip().lower()
        voice_name = str(self.get_parameter('voice_name').value)
        language = str(self.get_parameter('language').value)
        fallback_voice_name = str(self.get_parameter('fallback_voice_name').value)
        playback_command = str(self.get_parameter('playback_command').value)
        elevenlabs_api_key = str(self.get_parameter('elevenlabs_api_key').value)
        elevenlabs_voice_id = str(self.get_parameter('elevenlabs_voice_id').value)
        elevenlabs_model_id = str(self.get_parameter('elevenlabs_model_id').value)
        elevenlabs_output_format = str(self.get_parameter('elevenlabs_output_format').value)
        cartesia_api_key = str(self.get_parameter('cartesia_api_key').value)
        cartesia_voice_id = str(self.get_parameter('cartesia_voice_id').value)
        cartesia_model_id = str(self.get_parameter('cartesia_model_id').value)
        cartesia_output_container = str(self.get_parameter('cartesia_output_container').value)
        cartesia_output_encoding = str(self.get_parameter('cartesia_output_encoding').value)
        cartesia_sample_rate = int(self.get_parameter('cartesia_sample_rate').value)

        fallback_provider = SpeechDispatcherTTSProvider(
            voice_name=fallback_voice_name,
            language='',
        )

        if backend == 'edge_tts':
            return EdgeTTSProvider(
                voice_name=voice_name,
                playback_command=playback_command,
                fallback_provider=fallback_provider,
            )

        if backend == 'elevenlabs':
            return ElevenLabsTTSProvider(
                api_key=elevenlabs_api_key,
                voice_id=elevenlabs_voice_id,
                model_id=elevenlabs_model_id,
                playback_command=playback_command,
                output_format=elevenlabs_output_format,
                fallback_provider=fallback_provider,
            )

        if backend == 'cartesia':
            return CartesiaTTSProvider(
                api_key=cartesia_api_key,
                voice_id=cartesia_voice_id,
                model_id=cartesia_model_id,
                playback_command=playback_command,
                output_container=cartesia_output_container,
                output_encoding=cartesia_output_encoding,
                sample_rate=cartesia_sample_rate,
                fallback_provider=fallback_provider,
            )

        if backend == 'speech_dispatcher':
            return SpeechDispatcherTTSProvider(voice_name=voice_name, language=language)

        return MockTTSProvider(self._log_synthesized_text)

    def _on_speak_request(self, message: String) -> None:
        if not message.data:
            return

        try:
            self._status_publisher.publish(String(data=f'음성 응답 처리 시작: {message.data}'))
            self._provider.speak(message.data)
            self._status_publisher.publish(String(data=f'음성 응답 출력 중: {message.data}'))
        except Exception as exc:
            error_text = f'TTS 실패: {exc}'
            self.get_logger().error(error_text)
            self._status_publisher.publish(String(data=error_text))

    def _log_synthesized_text(self, text: str) -> None:
        self.get_logger().info(f'[MockTTS] {text}')


def main(args: list[str] | None = None) -> None:
    rclpy.init(args=args)
    node = TTSNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()
