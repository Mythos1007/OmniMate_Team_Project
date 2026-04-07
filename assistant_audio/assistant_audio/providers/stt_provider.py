from __future__ import annotations

from abc import ABC, abstractmethod
from importlib import import_module
import math
from pathlib import Path
import subprocess
import sys
import tempfile


class STTProvider(ABC):
    """음성 인식 백엔드를 위한 추상 인터페이스."""

    @abstractmethod
    def transcribe(self) -> tuple[str, float]:
        """인식된 텍스트와 신뢰도를 반환한다."""


class MockSTTProvider(STTProvider):
    """설정된 문장을 그대로 반환하는 개발용 STT 백엔드."""

    def __init__(self, sample_text: str, confidence: float) -> None:
        self._sample_text = sample_text
        self._confidence = confidence

    def transcribe(self) -> tuple[str, float]:
        return self._sample_text, self._confidence


def _record_audio(
    wav_path: Path,
    record_seconds: float,
    sample_rate_hz: int,
    channels: int,
    audio_device: str,
) -> None:
    rounded_seconds = max(1, math.ceil(record_seconds))
    command = [
        'arecord',
        '-q',
        '-d',
        str(rounded_seconds),
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
    subprocess.run(command, check=True)


class PocketsphinxSTTProvider(STTProvider):
    """arecord와 pocketsphinx_continuous를 사용해 로컬에서 음성을 텍스트로 변환한다."""

    def __init__(
        self,
        record_seconds: float,
        sample_rate_hz: int,
        channels: int,
        audio_device: str,
        acoustic_model_dir: str,
        language_model_path: str,
        dictionary_path: str,
    ) -> None:
        self._record_seconds = record_seconds
        self._sample_rate_hz = sample_rate_hz
        self._channels = channels
        self._audio_device = audio_device
        self._acoustic_model_dir = acoustic_model_dir
        self._language_model_path = language_model_path
        self._dictionary_path = dictionary_path

    def transcribe(self) -> tuple[str, float]:
        with tempfile.TemporaryDirectory(prefix='assistant_stt_') as temp_dir:
            wav_path = Path(temp_dir) / 'utterance.wav'
            self._record_audio(wav_path)
            text = self._decode_audio(wav_path)
            confidence = 0.85 if text else 0.0
            return text, confidence

    def _record_audio(self, wav_path: Path) -> None:
        _record_audio(
            wav_path=wav_path,
            record_seconds=self._record_seconds,
            sample_rate_hz=self._sample_rate_hz,
            channels=self._channels,
            audio_device=self._audio_device,
        )

    def _decode_audio(self, wav_path: Path) -> str:
        command = [
            'pocketsphinx_continuous',
            '-infile',
            str(wav_path),
            '-hmm',
            self._acoustic_model_dir,
            '-lm',
            self._language_model_path,
            '-dict',
            self._dictionary_path,
        ]
        result = subprocess.run(command, check=True, capture_output=True, text=True)
        transcript_lines = []
        for line in result.stdout.splitlines():
            cleaned = line.strip()
            if not cleaned:
                continue
            if cleaned.startswith('INFO:') or cleaned.startswith('READY'):
                continue
            transcript_lines.append(cleaned)

        if not transcript_lines:
            return ''

        return ' '.join(transcript_lines).strip()


class FasterWhisperSTTProvider(STTProvider):
    """faster-whisper를 사용해 한국어 음성을 텍스트로 변환한다."""

    def __init__(
        self,
        record_seconds: float,
        sample_rate_hz: int,
        channels: int,
        audio_device: str,
        model_size: str,
        language: str,
        compute_type: str,
        device: str,
        beam_size: int,
    ) -> None:
        self._record_seconds = record_seconds
        self._sample_rate_hz = sample_rate_hz
        self._channels = channels
        self._audio_device = audio_device
        self._model_size = model_size
        self._language = language
        self._compute_type = compute_type
        self._device = device
        self._beam_size = beam_size
        self._model = None

    def transcribe(self) -> tuple[str, float]:
        with tempfile.TemporaryDirectory(prefix='assistant_stt_') as temp_dir:
            wav_path = Path(temp_dir) / 'utterance.wav'
            _record_audio(
                wav_path=wav_path,
                record_seconds=self._record_seconds,
                sample_rate_hz=self._sample_rate_hz,
                channels=self._channels,
                audio_device=self._audio_device,
            )
            return self.transcribe_file(wav_path)

    def transcribe_file(self, audio_path: str | Path) -> tuple[str, float]:
        model = self._get_model()
        segments, info = model.transcribe(
            str(audio_path),
            language=self._language,
            beam_size=self._beam_size,
            vad_filter=True,
            task='transcribe',
        )

        transcript_parts = []
        confidences = []
        for segment in segments:
            cleaned_text = segment.text.strip()
            if not cleaned_text:
                continue
            transcript_parts.append(cleaned_text)
            avg_logprob = getattr(segment, 'avg_logprob', None)
            if avg_logprob is not None:
                confidences.append(max(0.0, min(math.exp(avg_logprob), 1.0)))

        transcript_text = ' '.join(transcript_parts).strip()
        if not transcript_text:
            return '', 0.0

        if confidences:
            confidence = sum(confidences) / len(confidences)
        else:
            confidence = float(getattr(info, 'language_probability', 0.0) or 0.0)

        return transcript_text, max(0.0, min(confidence, 1.0))

    def _get_model(self):
        if self._model is not None:
            return self._model

        whisper_module = self._load_faster_whisper_module()
        self._model = whisper_module.WhisperModel(
            self._model_size,
            device=self._device,
            compute_type=self._compute_type,
        )
        return self._model

    def _load_faster_whisper_module(self):
        try:
            return import_module('faster_whisper')
        except ModuleNotFoundError:
            self._append_workspace_venv_site_packages()
            return import_module('faster_whisper')

    def _append_workspace_venv_site_packages(self) -> None:
        version_dir = f'python{sys.version_info.major}.{sys.version_info.minor}'
        candidate_suffix = Path('.venv') / 'lib' / version_dir / 'site-packages'
        search_roots = [Path.cwd(), *Path(__file__).resolve().parents]

        for root in search_roots:
            candidate = root / candidate_suffix
            if candidate.exists():
                candidate_str = str(candidate)
                if candidate_str not in sys.path:
                    sys.path.append(candidate_str)
                return

        raise ModuleNotFoundError(
            'faster_whisper is not installed and no workspace .venv site-packages was found.'
        )
