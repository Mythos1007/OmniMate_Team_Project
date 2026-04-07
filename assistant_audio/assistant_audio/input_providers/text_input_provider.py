from __future__ import annotations

from assistant_commands.interfaces import InputPayload, InputProvider


class TextInputProvider(InputProvider):
    def get_input(self) -> InputPayload:
        text = input('Type a command: ').strip()
        return InputPayload(
            input_type='text',
            raw_input=text,
            metadata={'provider': 'text'},
        )
