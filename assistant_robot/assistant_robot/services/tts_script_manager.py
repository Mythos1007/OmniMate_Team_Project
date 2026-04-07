from __future__ import annotations

from collections import defaultdict
from importlib.resources import files
from typing import Any

import yaml


class TTSScriptManager:
    """기능: 상황별 TTS 문구를 key 기반으로 중앙 조회/포맷 기능."""

    def __init__(self, *, profile: str = "default", resource_file: str | None = None) -> None:
        self.profile = profile
        self._messages = self._load_messages(resource_file)
        self._round_robin_index: dict[str, int] = defaultdict(int)

    def _load_messages(self, resource_file: str | None) -> dict[str, Any]:
        # 기능: profile(dev/demo/default)에 맞는 YAML 세트를 로딩 기능.
        file_name = resource_file or {
            "default": "tts_messages.yaml",
            "dev": "tts_messages_dev.yaml",
            "demo": "tts_messages_demo.yaml",
        }.get(self.profile, "tts_messages.yaml")
        resource_path = files("assistant_robot.resources").joinpath(file_name)
        with resource_path.open("r", encoding="utf-8") as stream:
            loaded = yaml.safe_load(stream) or {}
        return loaded.get("messages", loaded)

    def get_message(self, key: str, **kwargs: Any) -> str:
        # 기능: 기본 문구 조회. 리스트면 첫 번째 후보를 사용 기능.
        value = self._messages.get(key)
        if value is None:
            fallback = self._messages.get("error.general", key)
            return str(fallback).format(**kwargs) if "{" in str(fallback) else str(fallback)
        if isinstance(value, list):
            value = value[0]
        return str(value).format(**kwargs)

    def get_random_message(self, key: str, **kwargs: Any) -> str:
        # 기능: 후보가 여러 개면 round-robin으로 문구를 번갈아 선택 기능.
        value = self._messages.get(key)
        if value is None:
            return self.get_message("error.general", **kwargs)
        if not isinstance(value, list):
            return str(value).format(**kwargs)
        index = self._round_robin_index[key] % len(value)
        self._round_robin_index[key] += 1
        return str(value[index]).format(**kwargs)

    def format_message(self, key: str, **kwargs: Any) -> str:
        return self.get_random_message(key, **kwargs)
