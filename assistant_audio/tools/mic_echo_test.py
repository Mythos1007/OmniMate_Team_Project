from __future__ import annotations

from pathlib import Path
import signal
import subprocess
import tempfile
from threading import Event, Thread
import time

from assistant_audio.providers.stt_provider import FasterWhisperSTTProvider


MAX_RECORD_SECONDS = 10.0
SAMPLE_RATE_HZ = 16000
AUDIO_CHANNELS = 1
AUDIO_DEVICE = 'default'


def _create_provider() -> FasterWhisperSTTProvider:
    return FasterWhisperSTTProvider(
        record_seconds=MAX_RECORD_SECONDS,
        sample_rate_hz=SAMPLE_RATE_HZ,
        channels=AUDIO_CHANNELS,
        audio_device=AUDIO_DEVICE,
        model_size='small',
        language='ko',
        compute_type='int8',
        device='cpu',
        beam_size=5,
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


def main() -> None:
    provider = _create_provider()

    print('마이크 에코 테스트 준비 완료.')
    print(f'엔터를 누르면 녹음을 시작합니다. 최대 {MAX_RECORD_SECONDS:.0f}초까지 녹음합니다.')
    print('녹음 중에 엔터를 한 번 더 누르면 바로 종료합니다.')
    print("종료하려면 'q'를 입력하고 엔터를 누르세요.")

    while True:
        user_input = input('> ').strip().lower()
        if user_input == 'q':
            print('마이크 에코 테스트를 종료합니다.')
            return

        print('녹음 중입니다... 지금 말씀하세요. 끝나면 엔터를 한 번 더 누르세요.')
        try:
            with tempfile.TemporaryDirectory(prefix='assistant_mic_echo_') as temp_dir:
                wav_path = Path(temp_dir) / 'utterance.wav'
                _record_until_enter(
                    wav_path=wav_path,
                    max_record_seconds=MAX_RECORD_SECONDS,
                    sample_rate_hz=SAMPLE_RATE_HZ,
                    channels=AUDIO_CHANNELS,
                    audio_device=AUDIO_DEVICE,
                )
                text, confidence = provider.transcribe_file(wav_path)
        except Exception as exc:
            print(f'에코 테스트 실패: {exc}')
            continue

        if text:
            print(f'인식 결과: {text}')
            print(f'신뢰도: {confidence:.2f}')
        else:
            print('인식된 음성이 없습니다.')


if __name__ == '__main__':
    main()
