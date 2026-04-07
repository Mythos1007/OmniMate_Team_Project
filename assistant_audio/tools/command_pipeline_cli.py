from __future__ import annotations

import argparse
import json

from assistant_audio.input_providers import ButtonAudioInputProvider, TextInputProvider
from assistant_audio.stt_service import MockSTTService
from assistant_commands import CommandNormalizer, MockCommandExecutor
from assistant_commands.interfaces import InputPayload, InputProvider, STTService


def build_provider(name: str) -> InputProvider:
    providers: dict[str, InputProvider] = {
        'text': TextInputProvider(),
        'button-audio': ButtonAudioInputProvider(),
    }
    return providers[name]


def resolve_text(payload: InputPayload, stt_service: STTService) -> str:
    if payload.input_type == 'text':
        return payload.raw_input.strip()
    return stt_service.transcribe(payload)


def run_once(provider: InputProvider, stt_service: STTService) -> bool:
    payload = provider.get_input()
    text = resolve_text(payload, stt_service)

    if text.lower() in {'quit', 'exit', '종료'}:
        print('Exiting...')
        return False

    normalizer = CommandNormalizer()
    executor = MockCommandExecutor()

    normalized = normalizer.normalize(text)
    result = executor.execute(normalized)

    print(f'[INPUT TYPE] {payload.input_type}')
    print(f'[RAW INPUT] {payload.raw_input}')
    print(f'[TEXT] {text}')
    print(f"[NORMALIZED] {json.dumps(normalized.to_dict(), ensure_ascii=False)}")
    print(result)
    print()
    return True


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Assistant voice command MVP pipeline')
    parser.add_argument(
        '--provider',
        choices=('text', 'button-audio'),
        default='text',
        help='Select input provider.',
    )
    parser.add_argument(
        '--once',
        action='store_true',
        help='Run only one command and exit.',
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    provider = build_provider(args.provider)
    stt_service = MockSTTService()

    try:
        while True:
            should_continue = run_once(provider, stt_service)
            if not should_continue or args.once:
                break
    except KeyboardInterrupt:
        print('\nInterrupted by user.')


if __name__ == '__main__':
    main()
