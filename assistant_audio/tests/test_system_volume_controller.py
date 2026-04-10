from __future__ import annotations

from assistant_audio.system_volume_controller import SystemVolumeController


class _Result:
    def __init__(self, returncode: int = 0, stdout: str = '', stderr: str = '') -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def test_auto_prefers_wpctl(monkeypatch):
    commands: list[list[str]] = []

    def fake_which(name: str) -> str | None:
        return '/usr/bin/wpctl' if name == 'wpctl' else None

    def fake_run(command, capture_output, text):
        commands.append(command)
        return _Result()

    monkeypatch.setattr('assistant_audio.system_volume_controller.shutil.which', fake_which)
    monkeypatch.setattr('assistant_audio.system_volume_controller.subprocess.run', fake_run)

    backend = SystemVolumeController().set_volume(33)

    assert backend == 'wpctl'
    assert commands == [['wpctl', 'set-volume', '@DEFAULT_AUDIO_SINK@', '33%']]


def test_amixer_uses_device_name(monkeypatch):
    commands: list[list[str]] = []

    def fake_which(name: str) -> str | None:
        return '/usr/bin/amixer' if name == 'amixer' else None

    def fake_run(command, capture_output, text):
        commands.append(command)
        return _Result()

    monkeypatch.setattr('assistant_audio.system_volume_controller.shutil.which', fake_which)
    monkeypatch.setattr('assistant_audio.system_volume_controller.subprocess.run', fake_run)

    backend = SystemVolumeController(backend='amixer', device_name='Speaker').set_volume(61)

    assert backend == 'amixer'
    assert commands == [['amixer', 'sset', 'Speaker', '61%']]


def test_raises_when_no_backend_available(monkeypatch):
    monkeypatch.setattr('assistant_audio.system_volume_controller.shutil.which', lambda _name: None)

    controller = SystemVolumeController()

    try:
        controller.set_volume(50)
    except RuntimeError as exc:
        assert '볼륨 제어 명령' in str(exc)
    else:
        raise AssertionError('RuntimeError was not raised')


def test_explicit_backend_falls_back_when_unavailable(monkeypatch):
    commands: list[list[str]] = []

    def fake_which(name: str) -> str | None:
        if name == 'pactl':
            return '/usr/bin/pactl'
        return None

    def fake_run(command, capture_output, text):
        commands.append(command)
        return _Result()

    monkeypatch.setattr('assistant_audio.system_volume_controller.shutil.which', fake_which)
    monkeypatch.setattr('assistant_audio.system_volume_controller.subprocess.run', fake_run)

    backend = SystemVolumeController(backend='wpctl').set_volume(47)

    assert backend == 'pactl'
    assert commands == [['pactl', 'set-sink-volume', '@DEFAULT_SINK@', '47%']]
