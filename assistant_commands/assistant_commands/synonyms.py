from __future__ import annotations

from assistant_commands.command_schema import CanonicalCommandName


SYNONYM_TABLE: dict[CanonicalCommandName, tuple[str, ...]] = {
    "start_patrol": (
        "순찰 시작해",
        "순찰 시작",
        "순찰 돌기 시작해",
    ),
    "pause_patrol": (
        "순찰 멈춰",
        "순찰 중지해",
        "순찰 일시정지",
    ),
    "resume_patrol": (
        "순찰 재개해",
        "순찰 다시 시작해",
        "순찰 이어서 해",
    ),
    "status_query": (
        "현재 상태 알려줘",
        "지금 상태 알려줘",
        "상태 알려줘",
        "현재 상태",
    ),
    "move_forward": (
        "앞쪽으로 이동해",
        "앞으로 이동해",
        "앞으로 가",
        "전진해",
        "직진해",
    ),
    "move_backward": (
        "뒤쪽으로 이동해",
        "뒤로 이동해",
        "뒤로 가",
        "후진해",
    ),
    "turn_left": (
        "왼쪽으로 돌아",
        "왼쪽으로 회전해",
        "좌회전해",
    ),
    "turn_right": (
        "오른쪽으로 돌아",
        "오른쪽으로 회전해",
        "우회전해",
    ),
    "stop": (
        "멈춰",
        "정지",
        "멈추어",
        "서",
    ),
    "unknown": (),
}


def build_phrase_lookup() -> list[tuple[str, CanonicalCommandName]]:
    pairs: list[tuple[str, CanonicalCommandName]] = []
    for command, phrases in SYNONYM_TABLE.items():
        for phrase in phrases:
            pairs.append((phrase, command))

    return sorted(pairs, key=lambda item: len(item[0]), reverse=True)


PHRASE_LOOKUP = build_phrase_lookup()
