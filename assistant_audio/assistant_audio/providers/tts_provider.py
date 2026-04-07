from __future__ import annotations

from abc import ABC, abstractmethod
import asyncio
from dataclasses import dataclass
from importlib import import_module
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from typing import Callable

import requests


_SECRETS_CACHE: dict[str, str] | None = None


class TTSProvider(ABC):
    """음성 합성 백엔드를 위한 추상 인터페이스."""

    @abstractmethod
    def speak(self, text: str) -> None:
        """구현체 백엔드를 사용해 전달된 텍스트를 발화한다."""


@dataclass(frozen=True)
class ElevenLabsTTSConfig:
    api_key: str
    voice_id: str
    model_id: str
    output_format: str = 'mp3_44100_128'


@dataclass(frozen=True)
class CartesiaTTSConfig:
    api_key: str
    voice_id: str
    model_id: str = 'sonic-3'
    output_container: str = 'wav'
    output_encoding: str = 'pcm_f32le'
    sample_rate: int = 44100


class MockTTSProvider(TTSProvider):
    """합성 결과를 콜백으로 전달하는 개발용 백엔드."""

    def __init__(self, log_callback: Callable[[str], None]) -> None:
        self._log_callback = log_callback

    def speak(self, text: str) -> None:
        self._log_callback(text)


class GeneratedAudioTTSProvider(TTSProvider, ABC):
    """오디오 파일을 생성한 뒤 로컬 재생기로 재생하는 공통 베이스 클래스."""

    backend_display_name = 'generated_audio'

    def __init__(
        self,
        playback_command: str = 'gst-play-1.0',
        fallback_provider: TTSProvider | None = None,
    ) -> None:
        self._playback_command = playback_command
        self._fallback_provider = fallback_provider

    def speak(self, text: str) -> None:
        try:
            self._speak_with_generated_audio(text)
        except Exception as exc:
            if self._fallback_provider is not None:
                self._fallback_provider.speak(text)
                return
            if isinstance(exc, RuntimeError):
                raise
            raise RuntimeError(f'{self.backend_display_name} 합성 실패: {exc}') from exc

    def _speak_with_generated_audio(self, text: str) -> None:
        playback_command = self._resolve_playback_command()
        with tempfile.TemporaryDirectory(prefix='assistant_tts_') as temp_dir:
            audio_path = Path(temp_dir) / f'utterance{self._audio_suffix()}'
            self._generate_audio_file(text, audio_path)
            self._play_audio_file(playback_command, audio_path)

    @abstractmethod
    def _audio_suffix(self) -> str:
        """생성할 오디오 파일 확장자를 반환한다."""

    @abstractmethod
    def _generate_audio_file(self, text: str, audio_path: Path) -> None:
        """text를 audio_path 파일로 생성한다."""

    def _play_audio_file(self, playback_command: str, audio_path: Path) -> None:
        subprocess.run(self._build_playback_command(playback_command, audio_path), check=True)

    def _resolve_playback_command(self) -> str:
        if self._playback_command and shutil.which(self._playback_command):
            return self._playback_command
        for candidate in ('gst-play-1.0', 'ffplay', 'mpg123', 'aplay'):
            if shutil.which(candidate):
                return candidate
        raise RuntimeError('재생 명령을 찾을 수 없습니다. gst-play-1.0/ffplay/mpg123/aplay 중 하나가 필요합니다.')

    def _build_playback_command(self, playback_command: str, audio_path: Path) -> list[str]:
        if playback_command == 'gst-play-1.0':
            return [playback_command, '-q', str(audio_path)]
        if playback_command == 'ffplay':
            return [playback_command, '-nodisp', '-autoexit', '-loglevel', 'error', str(audio_path)]
        if playback_command == 'mpg123':
            return [playback_command, '-q', str(audio_path)]
        if playback_command == 'aplay':
            return [playback_command, str(audio_path)]
        return [playback_command, str(audio_path)]


def _read_api_key(explicit_value: str | None, env_name: str, backend_name: str) -> str:
    secret_key = env_name.lower()
    api_key = (explicit_value or os.getenv(env_name, '') or _read_secret_value(secret_key)).strip()
    if not api_key:
        raise RuntimeError(f'{backend_name} API 키가 없습니다. {env_name} 환경변수 또는 파라미터를 설정해주세요.')
    return api_key


def _read_required_value(
    explicit_value: str | None,
    env_name: str,
    secret_key: str,
    description_ko: str,
) -> str:
    value = (explicit_value or os.getenv(env_name, '') or _read_secret_value(secret_key)).strip()
    if not value:
        raise RuntimeError(
            f'{description_ko}이(가) 비어 있습니다. '
            f'{env_name} 환경변수 또는 시크릿 파일 키({secret_key})를 설정해주세요.'
        )
    return value


def _resolve_secrets_file_path() -> Path:
    configured = os.getenv('ASSISTANT_TTS_SECRETS_FILE', '').strip()
    if configured:
        return Path(configured).expanduser()
    shared_configured = os.getenv('ASSISTANT_SECRETS_FILE', '').strip()
    if shared_configured:
        return Path(shared_configured).expanduser()
    return Path.home() / '.config' / 'assistant' / 'secrets.json'


def _load_secrets_file() -> dict[str, str]:
    global _SECRETS_CACHE
    if _SECRETS_CACHE is not None:
        return _SECRETS_CACHE

    secrets_file = _resolve_secrets_file_path()
    if not secrets_file.exists():
        _SECRETS_CACHE = {}
        return _SECRETS_CACHE

    try:
        loaded = json.loads(secrets_file.read_text(encoding='utf-8'))
    except Exception as exc:
        raise RuntimeError(f'시크릿 파일 파싱 실패: {secrets_file} ({exc})') from exc

    if not isinstance(loaded, dict):
        raise RuntimeError(f'시크릿 파일 형식 오류: {secrets_file} (JSON object 필요)')

    _SECRETS_CACHE = {
        str(key): str(value)
        for key, value in loaded.items()
        if isinstance(key, str) and isinstance(value, (str, int, float))
    }
    return _SECRETS_CACHE


def _read_secret_value(key: str) -> str:
    secrets = _load_secrets_file()
    return secrets.get(key, '')


def _raise_http_error(backend_name: str, response: requests.Response) -> None:
    detail = response.text.strip()
    if response.status_code in {401, 403}:
        raise RuntimeError(f'{backend_name} 인증 실패: API 키를 확인해주세요. {detail}')
    if response.status_code == 404:
        raise RuntimeError(f'{backend_name} voice/model 설정을 찾지 못했습니다. {detail}')
    raise RuntimeError(f'{backend_name} 요청 실패({response.status_code}): {detail}')


class SpeechDispatcherTTSProvider(TTSProvider):
    """spd-say를 사용해 로컬 스피커로 텍스트를 발화한다."""

    def __init__(self, voice_name: str = 'default', language: str = 'ko') -> None:
        self._voice_name = voice_name
        self._language = language

    def speak(self, text: str) -> None:
        # Do not block on playback completion; some speech-dispatcher setups hang with -w.
        command = ['spd-say']
        if self._language:
            command.extend(['-l', self._language])
        if self._voice_name and self._voice_name != 'default':
            command.extend(['-y', self._voice_name])
        command.append(text)
        spd_say_path = shutil.which('spd-say')
        if spd_say_path is not None:
            # If spd-say exits immediately with non-zero, speech-dispatcher is usually broken.
            # In that case, fall back to espeak-ng which does not require speech-dispatcher.
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                start_new_session=True,
            )
            try:
                return_code = process.wait(timeout=0.8)
            except subprocess.TimeoutExpired:
                return

            if return_code == 0:
                return

            stderr_text = (process.stderr.read() or '').strip() if process.stderr else ''
            stdout_text = (process.stdout.read() or '').strip() if process.stdout else ''
            spd_say_error = stderr_text or stdout_text or f'return code {return_code}'
        else:
            spd_say_error = 'spd-say command not found'

        espeak_path = shutil.which('espeak-ng')
        if espeak_path is not None:
            espeak_command = [espeak_path, '-v', 'ko', text]
            subprocess.Popen(
                espeak_command,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            return

        raise RuntimeError(f'spd-say/espeak-ng unavailable: {spd_say_error}')


class EdgeTTSProvider(GeneratedAudioTTSProvider):
    """edge-tts를 사용해 네트워크 기반 고품질 음성으로 발화한다."""

    backend_display_name = 'edge_tts'

    def __init__(
        self,
        voice_name: str,
        playback_command: str = 'gst-play-1.0',
        fallback_provider: TTSProvider | None = None,
    ) -> None:
        super().__init__(playback_command=playback_command, fallback_provider=fallback_provider)
        self._voice_name = voice_name
        self._edge_tts_module = self._load_edge_tts_module()

    def _audio_suffix(self) -> str:
        return '.mp3'

    def _generate_audio_file(self, text: str, audio_path: Path) -> None:
        asyncio.run(self._save_audio(text, audio_path))

    async def _save_audio(self, text: str, audio_path: Path) -> None:
        communicate = self._edge_tts_module.Communicate(text, voice=self._voice_name)
        await communicate.save(str(audio_path))

    def _load_edge_tts_module(self):
        try:
            return import_module('edge_tts')
        except ModuleNotFoundError:
            self._append_workspace_venv_site_packages()
            return import_module('edge_tts')

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

        raise ModuleNotFoundError('edge_tts is not installed and no workspace .venv site-packages was found.')


class ElevenLabsTTSProvider(GeneratedAudioTTSProvider):
    """ElevenLabs REST/SDK를 이용해 고품질 음성을 생성한다."""

    backend_display_name = 'elevenlabs'

    def __init__(
        self,
        api_key: str | None,
        voice_id: str,
        model_id: str,
        playback_command: str = 'gst-play-1.0',
        output_format: str = 'mp3_44100_128',
        fallback_provider: TTSProvider | None = None,
    ) -> None:
        super().__init__(playback_command=playback_command, fallback_provider=fallback_provider)
        self._config = ElevenLabsTTSConfig(
            api_key=_read_api_key(api_key, 'ELEVENLABS_API_KEY', 'ElevenLabs'),
            voice_id=_read_required_value(
                voice_id,
                'ELEVENLABS_VOICE_ID',
                'elevenlabs_voice_id',
                'ElevenLabs voice_id',
            ),
            model_id=(model_id or 'eleven_multilingual_v2').strip(),
            output_format=output_format.strip() or 'mp3_44100_128',
        )
        if not self._config.model_id:
            raise RuntimeError('ElevenLabs model_id가 비어 있습니다.')

    def _audio_suffix(self) -> str:
        if self._config.output_format.startswith('mp3'):
            return '.mp3'
        if 'wav' in self._config.output_format or 'pcm' in self._config.output_format:
            return '.wav'
        return '.bin'

    def _generate_audio_file(self, text: str, audio_path: Path) -> None:
        try:
            if self._generate_with_sdk(text, audio_path):
                return
        except RuntimeError:
            # SDK 버전 차이 또는 런타임 이슈가 있으면 REST fallback으로 한 번 더 시도한다.
            pass
        self._generate_with_rest(text, audio_path)

    def _generate_with_sdk(self, text: str, audio_path: Path) -> bool:
        try:
            from elevenlabs.client import ElevenLabs
        except ModuleNotFoundError:
            return False

        try:
            client = ElevenLabs(api_key=self._config.api_key)
            audio_stream = client.text_to_speech.convert(
                voice_id=self._config.voice_id,
                model_id=self._config.model_id,
                output_format=self._config.output_format,
                text=text,
            )
            with audio_path.open('wb') as handle:
                if isinstance(audio_stream, (bytes, bytearray)):
                    handle.write(audio_stream)
                else:
                    for chunk in audio_stream:
                        if chunk:
                            handle.write(chunk)
            return True
        except Exception as exc:
            raise RuntimeError(f'ElevenLabs SDK 호출 실패: {exc}') from exc

    def _generate_with_rest(self, text: str, audio_path: Path) -> None:
        headers = {
            'xi-api-key': self._config.api_key,
            'Accept': 'audio/mpeg' if self._audio_suffix() == '.mp3' else 'audio/wav',
            'Content-Type': 'application/json',
        }
        payload = {
            'text': text,
            'model_id': self._config.model_id,
        }
        url = (
            f'https://api.elevenlabs.io/v1/text-to-speech/{self._config.voice_id}'
            f'?output_format={self._config.output_format}'
        )
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=60)
        except requests.Timeout as exc:
            raise RuntimeError('ElevenLabs 네트워크 타임아웃이 발생했습니다.') from exc
        except requests.RequestException as exc:
            raise RuntimeError(f'ElevenLabs 네트워크 실패: {exc}') from exc

        if not response.ok:
            _raise_http_error('ElevenLabs', response)

        audio_path.write_bytes(response.content)


class CartesiaTTSProvider(GeneratedAudioTTSProvider):
    """Cartesia REST API를 이용해 배치형 음성을 생성한다."""

    backend_display_name = 'cartesia'

    def __init__(
        self,
        api_key: str | None,
        voice_id: str,
        model_id: str = 'sonic-3',
        playback_command: str = 'gst-play-1.0',
        output_container: str = 'wav',
        output_encoding: str = 'pcm_f32le',
        sample_rate: int = 44100,
        fallback_provider: TTSProvider | None = None,
    ) -> None:
        super().__init__(playback_command=playback_command, fallback_provider=fallback_provider)
        self._config = CartesiaTTSConfig(
            api_key=_read_api_key(api_key, 'CARTESIA_API_KEY', 'Cartesia'),
            voice_id=_read_required_value(
                voice_id,
                'CARTESIA_VOICE_ID',
                'cartesia_voice_id',
                'Cartesia voice_id',
            ),
            model_id=model_id.strip() or 'sonic-3',
            output_container=output_container.strip() or 'wav',
            output_encoding=output_encoding.strip() or 'pcm_f32le',
            sample_rate=sample_rate,
        )

    def _audio_suffix(self) -> str:
        if self._config.output_container.lower() == 'wav':
            return '.wav'
        if self._config.output_container.lower() == 'mp3':
            return '.mp3'
        return f'.{self._config.output_container.lower()}'

    def _generate_audio_file(self, text: str, audio_path: Path) -> None:
        headers = {
            'X-API-Key': self._config.api_key,
            'Cartesia-Version': '2024-06-10',
            'Content-Type': 'application/json',
        }
        payload = {
            'model_id': self._config.model_id,
            'transcript': text,
            'voice': {
                'mode': 'id',
                'id': self._config.voice_id,
            },
            'output_format': {
                'container': self._config.output_container,
                'encoding': self._config.output_encoding,
                'sample_rate': self._config.sample_rate,
            },
        }
        try:
            response = requests.post(
                'https://api.cartesia.ai/tts/bytes',
                headers=headers,
                json=payload,
                timeout=60,
            )
        except requests.Timeout as exc:
            raise RuntimeError('Cartesia 네트워크 타임아웃이 발생했습니다.') from exc
        except requests.RequestException as exc:
            raise RuntimeError(f'Cartesia 네트워크 실패: {exc}') from exc

        if not response.ok:
            _raise_http_error('Cartesia', response)

        audio_path.write_bytes(response.content)
