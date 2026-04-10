from __future__ import annotations

import os
from pathlib import Path


def resolve_runtime_data_path(current_file: str | Path, env_name: str, filename: str) -> Path:
    configured = os.environ.get(env_name, "").strip()
    if configured:
        candidate = Path(configured).expanduser().resolve()
        if candidate.exists() or candidate.parent.exists():
            return candidate

    here = Path(current_file).resolve()
    candidates: list[Path] = [here.parent / filename]
    for parent in here.parents:
        candidates.extend(
            [
                parent / "assistant_gui" / "assistant_gui" / filename,
                parent / "src" / "assistant" / "assistant_gui" / "assistant_gui" / filename,
            ]
        )

    seen: set[Path] = set()
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        if candidate.exists():
            return candidate

    for candidate in candidates:
        if candidate.parent.exists():
            return candidate
    return candidates[0]