from __future__ import annotations

import argparse
from datetime import datetime
import json
import re

from assistant_audio.providers.stt_provider import FasterWhisperSTTProvider
from assistant_brain.command_dispatcher import CommandDispatcher
from assistant_brain.dispatch_types import DispatchResult
from assistant_brain.intent_rules import classify_intent, normalize_text
from assistant_commands import (
    AuxiliaryNormalizer,
    CanonicalCommand,
    CommandNormalizer,
    DisabledAuxiliaryNormalizer,
    HeuristicAuxiliaryNormalizer,
)


def create_stt_provider(model_size: str) -> FasterWhisperSTTProvider:
    return FasterWhisperSTTProvider(
        record_seconds=4.0,
        sample_rate_hz=16000,
        channels=1,
        audio_device='default',
        model_size=model_size,
        language='ko',
        compute_type='int8',
        device='cpu',
        beam_size=5,
    )


def parse_alarm_create_args(text: str) -> dict[str, object]:
    match = re.search(r'(?P<hour>\d{1,2})\s*시(?:\s*(?P<minute>\d{1,2})\s*분)?', text)
    if not match:
        return {'time': '07:00', 'label': '기본 알람'}

    hour = int(match.group('hour'))
    minute = int(match.group('minute') or 0)
    return {
        'time': f'{hour:02d}:{minute:02d}',
        'label': '음성 알람',
    }


def parse_schedule_create_args(text: str) -> dict[str, object]:
    date = '오늘'
    if '내일' in text:
        date = '내일'

    time_match = re.search(r'(?P<hour>\d{1,2})\s*시(?:\s*(?P<minute>\d{1,2})\s*분)?', text)
    if time_match:
        hour = int(time_match.group('hour'))
        minute = int(time_match.group('minute') or 0)
        time = f'{hour:02d}:{minute:02d}'
    else:
        time = '09:00'

    title = '음성 일정'
    title_match = re.search(r'(?P<title>.+?)\s*일정', text)
    if title_match:
        candidate = title_match.group('title').strip()
        if candidate:
            title = candidate

    return {
        'date': date,
        'time': time,
        'title': title,
    }


def parse_delivery_args(text: str) -> dict[str, object]:
    destination = '안내데스크'
    destination_match = re.search(r'(?P<destination>.+?)(?:으로|로).*(?:배달|전달)', text)
    if destination_match:
        destination = destination_match.group('destination').strip()

    return {
        'item': '우편물',
        'destination': destination,
    }


def infer_stub_command(text: str) -> CanonicalCommand | None:
    normalized = normalize_text(text)

    if '날씨' in normalized:
        return CanonicalCommand(command='weather_query', original_text=text)

    if '알람' in normalized and any(keyword in normalized for keyword in ('목록', '리스트', '불러', '보여')):
        return CanonicalCommand(command='alarm_list', original_text=text)

    if '알람' in normalized and any(keyword in normalized for keyword in ('설정', '맞춰', '저장')):
        return CanonicalCommand(command='alarm_create', args=parse_alarm_create_args(text), original_text=text)

    if '일정' in normalized and any(keyword in normalized for keyword in ('목록', '리스트', '불러', '보여')):
        return CanonicalCommand(command='schedule_list', original_text=text)

    if '일정' in normalized and any(keyword in normalized for keyword in ('추가', '등록', '저장', '설정')):
        return CanonicalCommand(command='schedule_create', args=parse_schedule_create_args(text), original_text=text)

    if '우편물' in normalized and any(keyword in normalized for keyword in ('배달', '전달')):
        return CanonicalCommand(command='deliver_mail', args=parse_delivery_args(text), original_text=text)

    return None


def fallback_result_from_intent(text: str) -> tuple[CanonicalCommand, DispatchResult | None]:
    classification = classify_intent(text)

    if classification.intent_name == 'guide_to_place':
        location = classification.slots.get('place_name', 'unknown')
        return CanonicalCommand(command='guide_to_location', args={'location': location}, original_text=text), None

    if classification.intent_name == 'get_current_time':
        now_text = datetime.now().strftime('%H:%M')
        return CanonicalCommand(command='unknown', args={'original_text': text}, original_text=text), DispatchResult(
            handled=True,
            status_text=f'[STUB] Current time: {now_text}',
            speak_text=f'현재 시각은 {now_text}입니다.',
        )

    if classification.intent_name in {'get_robot_status', 'get_battery_status'}:
        return CanonicalCommand(command='unknown', args={'original_text': text}, original_text=text), DispatchResult(
            handled=True,
            status_text='[STUB] Robot status service is not connected in live CLI mode.',
            speak_text='지금은 로봇 상태 서비스가 연결되지 않았어요.',
        )

    return CanonicalCommand(command='unknown', args={'original_text': text}, original_text=text), None


def resolve_command(
    text: str,
    normalizer: CommandNormalizer,
    auxiliary_normalizer: AuxiliaryNormalizer,
) -> tuple[CanonicalCommand, DispatchResult | None]:
    normalized_command = normalizer.normalize(text)
    if normalized_command.command != 'unknown':
        return normalized_command, None

    inferred_command = infer_stub_command(text)
    if inferred_command is not None:
        return inferred_command, None

    auxiliary_command = auxiliary_normalizer.normalize(text)
    if auxiliary_command is not None:
        return auxiliary_command, None

    return fallback_result_from_intent(text)


def print_output(
    input_mode: str,
    text: str,
    command: CanonicalCommand,
    result: DispatchResult,
) -> None:
    print(f'[INPUT MODE] {input_mode}')
    print(f'[TEXT] {text}')
    print(f'[NORMALIZED] {json.dumps(command.to_dict(), ensure_ascii=False)}')
    print(f'[STATUS] {result.status_text}')
    print(f'[SPEAK] {result.speak_text}')
    print()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Run live microphone input through stub handlers.')
    parser.add_argument(
        '--text',
        help='Skip microphone recording and use the provided text directly.',
    )
    parser.add_argument(
        '--once',
        action='store_true',
        help='Run one iteration and exit.',
    )
    parser.add_argument(
        '--aux-normalizer',
        choices=('off', 'heuristic'),
        default='heuristic',
        help='Choose the auxiliary normalization backend. heuristic is a stand-in for future GPT fallback.',
    )
    parser.add_argument(
        '--model-size',
        default='medium',
        help='faster-whisper model size for live microphone STT. Default is medium for better recognition.',
    )
    return parser.parse_args()


def build_auxiliary_normalizer(name: str) -> AuxiliaryNormalizer:
    if name == 'heuristic':
        return HeuristicAuxiliaryNormalizer()
    return DisabledAuxiliaryNormalizer()


def main() -> None:
    args = parse_args()
    normalizer = CommandNormalizer()
    auxiliary_normalizer = build_auxiliary_normalizer(args.aux_normalizer)
    dispatcher = CommandDispatcher()
    stt_provider = None if args.text else create_stt_provider(args.model_size)

    print('실시간 음성 -> 임시 기능 출력 테스트')
    if args.text:
        print('텍스트 우회 모드입니다.')
    else:
        print(
            f'엔터: 마이크 녹음 (4초, model={args.model_size}) | '
            f'텍스트 입력 후 엔터: 텍스트 직접 처리'
        )
        print("종료하려면 'q'를 입력하고 엔터를 누르세요.")

    while True:
        if args.text:
            text = args.text.strip()
            input_mode = 'text'
        else:
            user_input = input('> ').strip()
            if user_input.lower() == 'q':
                print('종료합니다.')
                return

            if user_input:
                text = user_input
                input_mode = 'text'
            else:
                print('녹음 중입니다... 지금 말씀하세요.')
                text, confidence = stt_provider.transcribe()
                input_mode = 'voice'
                print(f'[STT CONFIDENCE] {confidence:.2f}')

        if not text:
            print('인식된 텍스트가 없습니다.\n')
            if args.text or args.once:
                return
            continue

        command, fallback_result = resolve_command(text, normalizer, auxiliary_normalizer)
        result = fallback_result or dispatcher.dispatch(command)
        print_output(input_mode, text, command, result)

        if args.text or args.once:
            return


if __name__ == '__main__':
    main()
