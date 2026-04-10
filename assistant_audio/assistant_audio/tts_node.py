from __future__ import annotations

from assistant_audio.providers.tts_provider import (
    CartesiaTTSProvider,
    EdgeTTSProvider,
    ElevenLabsTTSProvider,
    MockTTSProvider,
    SpeechDispatcherTTSProvider,
    TTSProvider,
)
from assistant_audio.system_volume_controller import SystemVolumeController

from std_msgs.msg import Int32, String

import json
import rclpy
from rclpy.node import Node


class TTSNode(Node):
    """음성 출력 요청 수신 후 TTS 백엔드 전달 기능.

    1단계: 오디오 재생 대신 로그 출력.
    TODO: 실제 음성 합성용 오디오 재생/백엔드 선택 기능 연동.
    """

    def __init__(self) -> None:
        super().__init__('tts_node')
        self._runtime_tts_overrides: dict[str, object] = {}

        self.declare_parameter('tts_backend', 'edge_tts')
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
        self.declare_parameter('speaker_volume_backend', 'auto')
        self.declare_parameter('speaker_volume_device', 'Master')
        self.declare_parameter('speaker_volume_percent', 70)

        self._provider = self._create_provider()
        self._status_publisher = self.create_publisher(String, '/assistant/status_text', 10)
        self._volume_controller = SystemVolumeController(
            backend=str(self.get_parameter('speaker_volume_backend').value),
            device_name=str(self.get_parameter('speaker_volume_device').value),
        )
        self.create_subscription(String, '/assistant/speak', self._on_speak_request, 10)
        self.create_subscription(String, '/assistant/audio/tts_config', self._on_tts_config_request, 10)
        self.create_subscription(Int32, '/assistant/audio/set_volume', self._on_set_volume_request, 10)
        self._apply_initial_volume()

        backend = self._config_value('tts_backend')
        voice_name = self._config_value('voice_name')
        language = self._config_value('language')
        elevenlabs_voice_id = self._config_value('elevenlabs_voice_id')
        elevenlabs_model_id = self._config_value('elevenlabs_model_id')
        cartesia_voice_id = self._config_value('cartesia_voice_id')
        cartesia_model_id = self._config_value('cartesia_model_id')
        self.get_logger().info(
            'TTS node ready. '
            f'backend={backend}, voice={voice_name}, language={language}, '
            f'elevenlabs_voice_id={elevenlabs_voice_id}, elevenlabs_model_id={elevenlabs_model_id}, '
            f'cartesia_voice_id={cartesia_voice_id}, cartesia_model_id={cartesia_model_id}'
        )

    def _config_value(self, name: str) -> object:
        if name in self._runtime_tts_overrides:
            return self._runtime_tts_overrides[name]
        return self.get_parameter(name).value

    def _create_provider(self) -> TTSProvider:
        backend = str(self._config_value('tts_backend')).strip().lower()
        voice_name = str(self._config_value('voice_name'))
        language = str(self._config_value('language'))
        fallback_voice_name = str(self._config_value('fallback_voice_name'))
        playback_command = str(self._config_value('playback_command'))
        elevenlabs_api_key = str(self._config_value('elevenlabs_api_key'))
        elevenlabs_voice_id = str(self._config_value('elevenlabs_voice_id'))
        elevenlabs_model_id = str(self._config_value('elevenlabs_model_id'))
        elevenlabs_output_format = str(self._config_value('elevenlabs_output_format'))
        cartesia_api_key = str(self._config_value('cartesia_api_key'))
        cartesia_voice_id = str(self._config_value('cartesia_voice_id'))
        cartesia_model_id = str(self._config_value('cartesia_model_id'))
        cartesia_output_container = str(self._config_value('cartesia_output_container'))
        cartesia_output_encoding = str(self._config_value('cartesia_output_encoding'))
        cartesia_sample_rate = int(self._config_value('cartesia_sample_rate'))

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

    def _on_tts_config_request(self, message: String) -> None:
        raw_payload = str(message.data).strip()
        if not raw_payload:
            return

        try:
            payload = json.loads(raw_payload)
        except json.JSONDecodeError as exc:
            error_text = f'로봇 TTS 설정 파싱 실패: {exc}'
            self.get_logger().warning(error_text)
            self._status_publisher.publish(String(data=error_text))
            return

        if not isinstance(payload, dict):
            error_text = '로봇 TTS 설정 형식이 올바르지 않습니다.'
            self.get_logger().warning(error_text)
            self._status_publisher.publish(String(data=error_text))
            return

        overrides: dict[str, object] = {}
        backend = str(payload.get('tts_backend', '')).strip().lower()
        if backend:
            if backend not in {'edge_tts', 'speech_dispatcher', 'elevenlabs', 'cartesia', 'mock'}:
                error_text = f'지원하지 않는 로봇 TTS 엔진: {backend}'
                self.get_logger().warning(error_text)
                self._status_publisher.publish(String(data=error_text))
                return
            overrides['tts_backend'] = backend

        for key in (
            'voice_name',
            'language',
            'fallback_voice_name',
            'playback_command',
            'elevenlabs_api_key',
            'elevenlabs_voice_id',
            'elevenlabs_model_id',
            'elevenlabs_output_format',
            'cartesia_api_key',
            'cartesia_voice_id',
            'cartesia_model_id',
            'cartesia_output_container',
            'cartesia_output_encoding',
        ):
            value = payload.get(key)
            if value is None:
                continue
            normalized = str(value).strip()
            if normalized:
                overrides[key] = normalized

        sample_rate = payload.get('cartesia_sample_rate')
        if sample_rate is not None:
            try:
                overrides['cartesia_sample_rate'] = int(sample_rate)
            except (TypeError, ValueError):
                self.get_logger().warning(f'Ignoring invalid cartesia sample rate: {sample_rate!r}')

        volume_percent = payload.get('speaker_volume_percent')
        if volume_percent is not None:
            try:
                overrides['speaker_volume_percent'] = max(0, min(100, int(volume_percent)))
            except (TypeError, ValueError):
                self.get_logger().warning(f'Ignoring invalid runtime speaker volume: {volume_percent!r}')

        if not overrides:
            return

        previous_overrides = dict(self._runtime_tts_overrides)
        self._runtime_tts_overrides.update(overrides)
        try:
            self._provider = self._create_provider()
        except Exception as exc:
            self._runtime_tts_overrides = previous_overrides
            self._provider = self._create_provider()
            error_text = f'로봇 TTS 설정 반영 실패: {exc}'
            self.get_logger().warning(error_text)
            self._status_publisher.publish(String(data=error_text))
            return

        if 'speaker_volume_percent' in overrides:
            try:
                backend_name = self._volume_controller.set_volume(int(overrides['speaker_volume_percent']))
                self.get_logger().info(
                    f"Runtime speaker volume updated to {overrides['speaker_volume_percent']}% via {backend_name}"
                )
            except Exception as exc:
                self.get_logger().warning(f'Failed to update runtime speaker volume: {exc}')

        active_backend = str(self._config_value('tts_backend'))
        active_voice = str(self._config_value('voice_name'))
        self._status_publisher.publish(String(data=f'로봇 TTS 설정 적용: {active_backend} / {active_voice}'))
        self.get_logger().info(f'Applied runtime TTS config: backend={active_backend}, voice={active_voice}')

    def _on_speak_request(self, message: String) -> None:
        if not message.data:
            return

        preview = str(message.data).strip().replace('\n', ' ')
        if len(preview) > 100:
            preview = preview[:100] + '...'
        self.get_logger().info(f'Received /assistant/speak: {preview}')

        try:
            self._status_publisher.publish(String(data='STATE:RESPONDING'))
            self._status_publisher.publish(String(data=f'음성 응답 처리 시작: {message.data}'))
            self._provider.speak(message.data)
            self._status_publisher.publish(String(data=f'음성 응답 출력 중: {message.data}'))
            self._status_publisher.publish(String(data='STATE:IDLE'))
            self.get_logger().info('Completed /assistant/speak request')
        except Exception as exc:
            error_text = f'TTS 실패: {exc}'
            self.get_logger().error(error_text)
            self._status_publisher.publish(String(data=error_text))

    def _apply_initial_volume(self) -> None:
        initial_volume = int(self.get_parameter('speaker_volume_percent').value)
        try:
            backend = self._volume_controller.set_volume(initial_volume)
            self.get_logger().info(f'Initial speaker volume applied: {initial_volume}% via {backend}')
        except Exception as exc:
            self.get_logger().warn(f'Initial speaker volume apply skipped: {exc}')

    def _on_set_volume_request(self, message: Int32) -> None:
        percent = max(0, min(100, int(message.data)))
        try:
            backend = self._volume_controller.set_volume(percent)
            self._status_publisher.publish(String(data=f'로봇 스피커 볼륨 {percent}% 적용'))
            self.get_logger().info(f'Speaker volume updated to {percent}% via {backend}')
        except Exception as exc:
            error_text = f'로봇 스피커 볼륨 변경 실패: {exc}'
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
        if rclpy.ok():
            rclpy.shutdown()
