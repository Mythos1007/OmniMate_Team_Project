from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class DispatchResult:
    handled: bool
    status_text: str
    speak_text: str
    metadata: dict[str, Any] = field(default_factory=dict)
