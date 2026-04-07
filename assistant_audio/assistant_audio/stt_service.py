from __future__ import annotations

from assistant_commands.interfaces import InputPayload, STTService


class MockSTTService(STTService):
    def transcribe(self, payload: InputPayload) -> str:
        if payload.input_type != 'audio':
            raise ValueError('MockSTTService can only transcribe audio payloads.')

        return payload.raw_input.strip()
