from __future__ import annotations

from assistant_commands.interfaces import InputPayload, STTService


class MockSTTService(STTService):
    """오디오 입력 기반 테스트용 STT 서비스."""

    def transcribe(self, payload: InputPayload) -> str:
        """audio 타입 입력 검증 후 raw_input 문자열 반환."""
        if payload.input_type != 'audio':
            raise ValueError('MockSTTService can only transcribe audio payloads.')

        return payload.raw_input.strip()
