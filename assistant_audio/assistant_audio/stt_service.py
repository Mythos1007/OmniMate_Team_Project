from __future__ import annotations

from assistant_commands.interfaces import InputPayload, STTService


class MockSTTService(STTService):
    """오디오 입력을 그대로 텍스트로 반환하는 테스트용 STT 서비스."""

    def transcribe(self, payload: InputPayload) -> str:
        """audio 타입 입력만 허용하고 raw_input 문자열을 반환한다."""
        if payload.input_type != 'audio':
            raise ValueError('MockSTTService can only transcribe audio payloads.')

        return payload.raw_input.strip()
