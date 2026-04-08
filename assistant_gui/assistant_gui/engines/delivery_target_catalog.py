from __future__ import annotations


DELIVERY_TARGET_KEYWORDS: tuple[str, ...] = (
    "마케팅팀",
    "영업팀",
    "개발팀",
    "기획팀",
    "인사팀",
    "회계팀",
    "희정님",
)


def match_delivery_target(text: str) -> str:
    compact = "".join(str(text or "").split())
    for keyword in DELIVERY_TARGET_KEYWORDS:
        if keyword in compact:
            return keyword
    return ""
