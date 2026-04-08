from __future__ import annotations


def main(args: list[str] | None = None) -> None:
    try:
        from assistant_audio.stt_node import main as audio_main
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            'assistant_audio 패키지가 필요합니다. robot 전용 STT 엔트리포인트는 assistant_audio.stt_node를 위임 호출합니다.'
        ) from exc
    audio_main(args=args)
