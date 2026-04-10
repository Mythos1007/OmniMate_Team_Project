from __future__ import annotations

import shutil
import subprocess


class SystemVolumeController:
    """Apply speaker volume using whichever system mixer is available."""

    def __init__(self, *, backend: str = 'auto', device_name: str = 'Master') -> None:
        self._backend = str(backend or 'auto').strip().lower() or 'auto'
        self._device_name = str(device_name or 'Master').strip() or 'Master'

    def set_volume(self, percent: int) -> str:
        clamped = max(0, min(100, int(percent)))
        backend, command = self._resolve_command(clamped)
        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode != 0:
            detail = result.stderr.strip() or result.stdout.strip() or 'unknown error'
            raise RuntimeError(f'{backend} 볼륨 적용 실패: {detail}')
        return backend

    def _resolve_command(self, percent: int) -> tuple[str, list[str]]:
        candidates = self._candidate_backends()
        for backend in candidates:
            command = self._build_command(backend, percent)
            if command is not None:
                return backend, command
        if self._backend != 'auto':
            raise RuntimeError(
                f'요청한 볼륨 백엔드({self._backend})를 사용할 수 없고, '
                '대체 가능한 볼륨 제어 명령도 찾지 못했습니다.'
            )
        raise RuntimeError('사용 가능한 볼륨 제어 명령을 찾지 못했습니다. wpctl/pactl/amixer 중 하나가 필요합니다.')

    def _candidate_backends(self) -> list[str]:
        if self._backend == 'auto':
            return ['wpctl', 'pactl', 'amixer']
        candidates = [self._backend, 'wpctl', 'pactl', 'amixer']
        deduped: list[str] = []
        for backend in candidates:
            if backend not in deduped:
                deduped.append(backend)
        return deduped

    def _build_command(self, backend: str, percent: int) -> list[str] | None:
        if backend == 'wpctl':
            if shutil.which('wpctl'):
                return ['wpctl', 'set-volume', '@DEFAULT_AUDIO_SINK@', f'{percent}%']
            return None
        if backend == 'pactl':
            if shutil.which('pactl'):
                return ['pactl', 'set-sink-volume', '@DEFAULT_SINK@', f'{percent}%']
            return None
        if backend == 'amixer':
            if shutil.which('amixer'):
                return ['amixer', 'sset', self._device_name, f'{percent}%']
            return None
        raise RuntimeError(f'지원하지 않는 볼륨 백엔드입니다: {backend}')
