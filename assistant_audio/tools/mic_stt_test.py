from __future__ import annotations

import argparse
from pathlib import Path
import signal
import subprocess
import tempfile
from threading import Event, Thread
import time

from assistant_audio.providers.stt_provider import FasterWhisperSTTProvider
from assistant_audio.providers.tts_provider import EdgeTTSProvider, SpeechDispatcherTTSProvider
from assistant_interfaces.msg import VoiceTranscript
from builtin_interfaces.msg import Time
from std_msgs.msg import Bool, String

import rclpy
from rclpy.node import Node


MAX_RECORD_SECONDS = 10.0


def _create_provider() -> FasterWhisperSTTProvider:
    return FasterWhisperSTTProvider(
        record_seconds=4.0,
        sample_rate_hz=16000,
        channels=1,
        audio_device='default',
        model_size='small',
        language='ko',
        compute_type='int8',
        device='cpu',
        beam_size=5,
    )


def _create_tts_provider() -> EdgeTTSProvider:
    return EdgeTTSProvider(
        voice_name='ko-KR-SunHiNeural',
        playback_command='gst-play-1.0',
        fallback_provider=SpeechDispatcherTTSProvider(voice_name='female1', language=''),
    )


def _record_until_enter(
    wav_path: Path,
    max_record_seconds: float,
    sample_rate_hz: int,
    channels: int,
    audio_device: str,
) -> None:
    command = [
        'arecord',
        '-q',
        '-d',
        str(int(max_record_seconds)),
        '-f',
        'S16_LE',
        '-r',
        str(sample_rate_hz),
        '-c',
        str(channels),
    ]
    if audio_device:
        command.extend(['-D', audio_device])
    command.append(str(wav_path))

    stop_requested = Event()

    def _wait_for_stop() -> None:
        input()
        stop_requested.set()

    recorder = subprocess.Popen(command)
    stop_thread = Thread(target=_wait_for_stop, daemon=True)
    stop_thread.start()

    started_at = time.monotonic()
    stopped_early = False
    while recorder.poll() is None:
        if stop_requested.is_set():
            stopped_early = True
            recorder.send_signal(signal.SIGINT)
            break
        if time.monotonic() - started_at >= max_record_seconds + 0.2:
            break
        time.sleep(0.05)

    recorder.wait()

    if stopped_early and wav_path.exists() and wav_path.stat().st_size > 0:
        return
    if recorder.returncode not in {0, None} and not (wav_path.exists() and wav_path.stat().st_size > 0):
        raise RuntimeError(f'녹음에 실패했습니다. arecord exited with code {recorder.returncode}.')


class MicSTTTestPublisher(Node):
    """로컬 STT 테스트 결과를 ROS 토픽으로 전송하는 보조 노드."""

    def __init__(self) -> None:
        super().__init__('mic_stt_test_publisher')
        self._wake_publisher = self.create_publisher(Bool, '/assistant/wake_detected', 10)
        self._transcript_publisher = self.create_publisher(VoiceTranscript, '/assistant/transcript', 10)
        self._status_publisher = self.create_publisher(String, '/assistant/status_text', 10)

    def publish_transcript(self, text: str, confidence: float) -> None:
        self._wake_publisher.publish(Bool(data=True))
        self._status_publisher.publish(String(data='로컬 마이크 테스트가 wake 이벤트를 보냈습니다.'))

        transcript = VoiceTranscript()
        transcript.stamp = self.get_clock().now().to_msg()
        transcript.text = text
        transcript.confidence = confidence
        transcript.wake_word_used = True
        self._transcript_publisher.publish(transcript)
        self._status_publisher.publish(String(data=f'로컬 마이크 테스트 전사 발행: {text}'))


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='로컬 한국어 STT 테스트 도구')
    parser.add_argument(
        '--publish-ros',
        action='store_true',
        help='전사 결과를 ROS 토픽(/assistant/transcript)으로도 발행합니다.',
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    provider = _create_provider()
    tts_provider = _create_tts_provider()
    ros_publisher = None

    if args.publish_ros:
        rclpy.init(args=None)
        ros_publisher = MicSTTTestPublisher()

    print('로컬 한국어 STT 테스트 준비 완료.')
    print(f'엔터를 누르면 녹음을 시작합니다. 최대 {MAX_RECORD_SECONDS:.0f}초까지 녹음합니다.')
    print('녹음 중에 엔터를 한 번 더 누르면 바로 종료합니다.')
    print("종료하려면 'q'를 입력하고 엔터를 누르세요.")
    if args.publish_ros:
        print('ROS publish 모드 활성화: /assistant/wake_detected 와 /assistant/transcript 로 발행합니다.')

    try:
        while True:
            user_input = input('> ').strip().lower()
            if user_input == 'q':
                print('로컬 STT 테스트를 종료합니다.')
                return

            print('녹음 중입니다... 지금 말씀하세요. 끝나면 엔터를 한 번 더 누르세요.')
            try:
                with tempfile.TemporaryDirectory(prefix='assistant_mic_stt_') as temp_dir:
                    wav_path = Path(temp_dir) / 'utterance.wav'
                    _record_until_enter(
                        wav_path=wav_path,
                        max_record_seconds=MAX_RECORD_SECONDS,
                        sample_rate_hz=16000,
                        channels=1,
                        audio_device='default',
                    )
                    text, confidence = provider.transcribe_file(wav_path)
            except Exception as exc:
                print(f'STT failed: {exc}')
                continue

            if text:
                print(f'인식 결과: {text}')
                print(f'신뢰도: {confidence:.2f}')
                if ros_publisher is not None:
                    ros_publisher.publish_transcript(text, confidence)
                    rclpy.spin_once(ros_publisher, timeout_sec=0.1)
                    print('ROS 토픽으로 전사 결과를 발행했습니다.')
                else:
                    print('TTS로 다시 읽어줍니다.')
                    try:
                        tts_provider.speak(text)
                    except Exception as exc:
                        print(f'TTS failed: {exc}')
            else:
                print('인식된 음성이 없습니다.')
    finally:
        if ros_publisher is not None:
            ros_publisher.destroy_node()
            rclpy.shutdown()


if __name__ == '__main__':
    main()
