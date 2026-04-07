from __future__ import annotations

from assistant_commands.interfaces import InputPayload, InputProvider


class ButtonAudioInputProvider(InputProvider):
    def get_input(self) -> InputPayload:
        input('Press Enter to start recording...')
        spoken_text = input('Recording... type simulated speech and press Enter to stop: ').strip()
        return InputPayload(
            input_type='audio',
            raw_input=spoken_text,
            metadata={
                'provider': 'button_audio',
                'mode': 'mock_recording',
            },
        )
