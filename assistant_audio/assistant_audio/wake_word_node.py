from __future__ import annotations

import json
import importlib
import os
from pathlib import Path
import queue
import re
from typing import Any

from std_msgs.msg import Bool, String

import rclpy
from rclpy.node import Node

try:
    sd = importlib.import_module('sounddevice')
except Exception as exc:  # pragma: no cover - depends on local audio stack
    sd = None
    _SOUNDDEVICE_IMPORT_ERROR = exc
else:
    _SOUNDDEVICE_IMPORT_ERROR = None

try:
    _vosk_module = importlib.import_module('vosk')
    KaldiRecognizer = _vosk_module.KaldiRecognizer
    Model = _vosk_module.Model
except Exception as exc:  # pragma: no cover - optional runtime dependency
    KaldiRecognizer = None
    Model = None
    _VOSK_IMPORT_ERROR = exc
else:
    _VOSK_IMPORT_ERROR = None


_DEFAULT_WAKE_WORDS = (
    '김루이엘리자베스돌쇠에드워드3세',
    '김루이',
    '루이',
    '김엘리자베스',
    '엘리자베스',
    '김돌쇠',
    '돌쇠',
    '돌쇠야',
    '돌세',
    '김에드워드',
    '에드워드',
    '김에드워드3세',
    '에드워드3세',
)


class WakeWordNode(Node):
    """Vosk 기반 실시간 웨이크 워드 감지 노드.

    기본 동작은 마이크 입력을 계속 받아 웨이크 워드를 감지하고
    /assistant/wake_detected 를 발행한다. 실환경 라이브러리가 없거나
    모델 경로가 없을 때도 노드는 살아 있으며 /assistant/manual_wake 로
    수동 테스트가 가능하다.
    """

    def __init__(self) -> None:
        super().__init__('wake_word_node')

        self.declare_parameter('wake_word_enabled', True)
        self.declare_parameter('wake_words', ','.join(_DEFAULT_WAKE_WORDS))
        self.declare_parameter('wake_word_text', '')
        self.declare_parameter('model_path', 'models/vosk-model-small-ko-0.22')
        self.declare_parameter('audio_device', 'default')
        self.declare_parameter('audio_block_size', 4000)
        self.declare_parameter('confidence_threshold', 0.70)
        self.declare_parameter('strict_vocabulary', False)
        self.declare_parameter('mock_mode', False)
        self.declare_parameter('mock_trigger_period_sec', 0.0)
        self.declare_parameter('wake_topic', '/assistant/wake_detected')
        self.declare_parameter('status_topic', '/assistant/status_text')
        self.declare_parameter('enabled_topic', '')
        self.declare_parameter('availability_topic', '')
        self.declare_parameter('voice_input_enabled', True)

        self._wake_topic = str(self.get_parameter('wake_topic').value)
        self._status_topic = str(self.get_parameter('status_topic').value)
        self._enabled_topic = str(self.get_parameter('enabled_topic').value).strip()
        self._availability_topic = str(self.get_parameter('availability_topic').value).strip()
        self._voice_input_enabled = bool(self.get_parameter('voice_input_enabled').value)

        self._wake_publisher = self.create_publisher(Bool, self._wake_topic, 10)
        self._status_publisher = self.create_publisher(String, self._status_topic, 10)
        self._availability_publisher = (
            self.create_publisher(Bool, self._availability_topic, 10)
            if self._availability_topic
            else None
        )
        self.create_subscription(Bool, '/assistant/manual_wake', self._on_manual_wake, 10)
        if self._enabled_topic:
            self.create_subscription(Bool, self._enabled_topic, self._on_voice_input_enabled, 10)

        self._wake_word_enabled = bool(self.get_parameter('wake_word_enabled').value)
        self._mock_mode = bool(self.get_parameter('mock_mode').value)
        self._mock_trigger_period_sec = float(self.get_parameter('mock_trigger_period_sec').value)
        self._confidence_threshold = float(self.get_parameter('confidence_threshold').value)
        self._strict_vocabulary = bool(self.get_parameter('strict_vocabulary').value)
        self._audio_block_size = int(self.get_parameter('audio_block_size').value)
        self._audio_device = self._parse_audio_device(str(self.get_parameter('audio_device').value))
        self._resolved_audio_device = None
        self._wake_words = self._parse_wake_words()
        self._normalized_wake_words = {self._normalize_text(word): word for word in self._wake_words}
        self._input_queue: queue.Queue[bytes] = queue.Queue()
        self._stream = None
        self._model = None
        self._recognizer = None
        self._samplerate = 16000

        if not self._wake_word_enabled:
            self.get_logger().info('Wake-word detection disabled by parameter.')
            return

        if self._mock_mode and self._mock_trigger_period_sec > 0.0:
            self.create_timer(self._mock_trigger_period_sec, self._publish_mock_wake)
            self._publish_availability(True)
            self.get_logger().info(
                f'Mock wake-word mode enabled. Triggering every '
                f'{self._mock_trigger_period_sec:.1f}s. Wake words: {sorted(self._wake_words)}'
            )
            return

        self._initialize_audio_backend()
        if self._recognizer is None:
            self.get_logger().warn('Wake-word backend is unavailable. Manual wake only mode is active.')
            return

        self.create_timer(0.05, self._process_audio)
        self._publish_availability(True)
        self.get_logger().info(
            f'Wake-word node listening with Vosk. Wake words: {sorted(self._wake_words)} '
            f'| threshold={self._confidence_threshold:.2f}'
        )
        self._status_publisher.publish(String(data='Wake-word detector listening.'))

    def trigger_wake(self, matched_word: str = 'manual', confidence: float | None = None) -> None:
        if not self._wake_word_enabled or not self._voice_input_enabled:
            return

        self._wake_publisher.publish(Bool(data=True))
        status = f'Wake word detected: {matched_word}'
        if confidence is not None:
            status = f'{status} ({confidence:.2f})'
        self._status_publisher.publish(String(data=status))
        self.get_logger().info(status)

    def destroy_node(self) -> bool:
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception as exc:  # pragma: no cover - cleanup is best effort
                self.get_logger().warn(f'Failed to close wake-word stream cleanly: {exc}')
        return super().destroy_node()

    def _initialize_audio_backend(self) -> None:
        if sd is None:
            self._report_backend_unavailable(
                f'sounddevice import failed: {_SOUNDDEVICE_IMPORT_ERROR}'
            )
            return
        if Model is None or KaldiRecognizer is None:
            self._report_backend_unavailable(f'vosk import failed: {_VOSK_IMPORT_ERROR}')
            return

        model_path = self._resolve_model_path(str(self.get_parameter('model_path').value))
        if model_path is None:
            configured_path = str(self.get_parameter('model_path').value)
            self._report_backend_unavailable(
                f'Vosk model path not found: {configured_path}. Set wake_word_node.model_path.'
            )
            return

        try:
            self._model = Model(str(model_path))
            self._resolved_audio_device = self._resolve_input_device(self._audio_device)
            if self._resolved_audio_device is None:
                raise RuntimeError(
                    'No input audio device available. Connect a microphone or set '
                    'wake_word_node.audio_device to an input-capable device.'
                )
            device_info = sd.query_devices(self._resolved_audio_device, 'input')
            self._samplerate = int(device_info['default_samplerate'])
            if self._strict_vocabulary:
                vocabulary = json.dumps([*sorted(self._wake_words), '[unk]'], ensure_ascii=False)
                self._recognizer = KaldiRecognizer(self._model, self._samplerate, vocabulary)
            else:
                self._recognizer = KaldiRecognizer(self._model, self._samplerate)
            self._recognizer.SetWords(True)
            self._stream = sd.RawInputStream(
                device=self._resolved_audio_device,
                samplerate=self._samplerate,
                blocksize=self._audio_block_size,
                dtype='int16',
                channels=1,
                callback=self._audio_callback,
            )
            self._stream.start()
            self.get_logger().info(
                f'Wake-word mic connected. device={self._resolved_audio_device} '
                f'samplerate={self._samplerate}'
            )
        except Exception as exc:
            self._recognizer = None
            self._model = None
            self._stream = None
            self._report_backend_unavailable(f'Wake-word backend init failed: {exc}')

    def _report_backend_unavailable(self, message: str) -> None:
        self._voice_input_enabled = False
        self.get_logger().error(message)
        self._status_publisher.publish(String(data=message))
        self._publish_availability(False)

    def _publish_availability(self, available: bool) -> None:
        if self._availability_publisher is not None:
            self._availability_publisher.publish(Bool(data=bool(available)))

    def _audio_callback(self, indata: bytes, frames: int, time_info: Any, status: Any) -> None:
        if status:
            self.get_logger().warn(f'Wake-word audio callback status: {status}')
        if not self._voice_input_enabled:
            return
        self._input_queue.put(bytes(indata))

    def _process_audio(self) -> None:
        if self._recognizer is None:
            return

        while not self._input_queue.empty():
            data = self._input_queue.get()
            if not self._recognizer.AcceptWaveform(data):
                continue

            try:
                result = json.loads(self._recognizer.Result())
            except json.JSONDecodeError:
                continue

            transcript_text = str(result.get('text', '')).strip()
            matched_phrase = self._match_wake_phrase(transcript_text)
            if matched_phrase is not None:
                self.trigger_wake(matched_phrase)
                continue

            for token in result.get('result', []):
                word = str(token.get('word', '')).strip()
                confidence = float(token.get('conf', 0.0) or 0.0)
                if word in self._wake_words and confidence >= self._confidence_threshold:
                    self.trigger_wake(word, confidence)
                    break
                if word and word != '[unk]':
                    self.get_logger().info(
                        f'Filtered similar word: {word} ({confidence * 100.0:.1f}%)'
                    )

    def _on_manual_wake(self, message: Bool) -> None:
        if message.data and self._voice_input_enabled:
            self.trigger_wake('manual')

    def _on_voice_input_enabled(self, message: Bool) -> None:
        self._voice_input_enabled = bool(message.data)
        if not self._voice_input_enabled:
            self._input_queue = queue.Queue()
        state_text = 'enabled' if self._voice_input_enabled else 'disabled'
        self.get_logger().info(f'Wake-word voice input {state_text}.')

    def _publish_mock_wake(self) -> None:
        first_word = next(iter(sorted(self._wake_words)), 'manual')
        self.trigger_wake(first_word, 1.0)

    def _parse_wake_words(self) -> frozenset[str]:
        raw = str(self.get_parameter('wake_words').value).strip()
        legacy = str(self.get_parameter('wake_word_text').value).strip()
        words = {token.strip() for token in raw.split(',') if token.strip()}
        if legacy:
            words.add(legacy)
        return frozenset(words) or frozenset(_DEFAULT_WAKE_WORDS)

    def _match_wake_phrase(self, transcript_text: str) -> str | None:
        compact = self._normalize_text(transcript_text)
        if not compact:
            return None

        matched = [original for normalized, original in self._normalized_wake_words.items() if normalized and normalized in compact]
        if not matched:
            return None
        return max(matched, key=len)

    @staticmethod
    def _normalize_text(value: str) -> str:
        return re.sub(r'[^0-9A-Za-z가-힣]+', '', value).lower()

    @staticmethod
    def _parse_audio_device(raw_value: str) -> int | str | None:
        token = raw_value.strip()
        if not token or token.lower() == 'default':
            return None
        if token.isdigit():
            return int(token)
        return token

    @staticmethod
    def _resolve_input_device(requested_device: int | str | None) -> int | str | None:
        if requested_device is not None:
            return requested_device

        default_devices = getattr(sd, 'default').device
        if isinstance(default_devices, (list, tuple)) and default_devices:
            input_device = default_devices[0]
            if input_device not in (None, -1):
                return input_device

        try:
            for index, device_info in enumerate(sd.query_devices()):
                if int(device_info.get('max_input_channels', 0)) > 0:
                    return index
        except Exception:
            return None

        return None

    @staticmethod
    def _resolve_model_path(raw_value: str) -> Path | None:
        raw = str(raw_value).strip()
        env_override = os.getenv('ASSISTANT_VOSK_MODEL_PATH', '').strip()
        configured = Path(raw or 'models/vosk-model-small-ko-0.22').expanduser()
        module_path = Path(__file__).resolve()
        workspace_root = module_path.parents[4]
        candidates: list[Path] = []

        if env_override:
            candidates.append(Path(env_override).expanduser())

        candidates.append(configured)
        if not configured.is_absolute():
            candidates.extend(
                [
                    Path.cwd() / configured,
                    workspace_root / configured,
                    workspace_root / 'models' / 'vosk-model-small-ko-0.22',
                ]
            )

        for candidate in candidates:
            if candidate.exists() and candidate.is_dir():
                return candidate.resolve()
        return None


def main(args: list[str] | None = None) -> None:
    rclpy.init(args=args)
    node = WakeWordNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()

