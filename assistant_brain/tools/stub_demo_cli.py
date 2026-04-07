from __future__ import annotations

import argparse
from dataclasses import asdict
import json

from assistant_brain.command_dispatcher import CommandDispatcher
from assistant_commands import CanonicalCommand


def build_demo_commands(scenario: str) -> list[CanonicalCommand]:
    commands_by_scenario: dict[str, list[CanonicalCommand]] = {
        'motion': [
            CanonicalCommand(command='move_forward', args={'distance': 1.0, 'unit': 'meter'}),
            CanonicalCommand(command='move_backward', args={'duration': 2.0, 'unit': 'second'}),
            CanonicalCommand(command='turn_left'),
            CanonicalCommand(command='stop'),
        ],
        'info': [
            CanonicalCommand(command='weather_query'),
        ],
        'task': [
            CanonicalCommand(command='alarm_create', args={'time': '07:30', 'label': '기상'}),
            CanonicalCommand(command='alarm_list'),
            CanonicalCommand(
                command='schedule_create',
                args={'date': '내일', 'time': '10:00', 'title': '팀 미팅'},
            ),
            CanonicalCommand(command='schedule_list'),
        ],
        'navigation': [
            CanonicalCommand(command='guide_to_location', args={'location': '회의실'}),
            CanonicalCommand(command='deliver_mail', args={'item': '우편물', 'destination': '안내데스크'}),
        ],
    }

    if scenario == 'all':
        ordered_commands: list[CanonicalCommand] = []
        for key in ('motion', 'info', 'task', 'navigation'):
            ordered_commands.extend(commands_by_scenario[key])
        return ordered_commands

    return commands_by_scenario[scenario]


def print_result(command: CanonicalCommand, status_text: str, speak_text: str) -> None:
    print(f"[COMMAND] {command.command}")
    print(f"[ARGS] {json.dumps(command.args, ensure_ascii=False)}")
    print(f"[STATUS] {status_text}")
    print(f"[SPEAK] {speak_text}")
    print()


def print_registry_snapshot(dispatcher: CommandDispatcher) -> None:
    snapshot = {
        'alarms': [asdict(entry) for entry in dispatcher.registry.alarms],
        'schedules': [asdict(entry) for entry in dispatcher.registry.schedules],
        'delivery_requests': [asdict(entry) for entry in dispatcher.registry.delivery_requests],
        'guidance_history': list(dispatcher.registry.guidance_history),
    }
    print(f"[REGISTRY] {json.dumps(snapshot, ensure_ascii=False)}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Run assistant_brain stub command scenarios.')
    parser.add_argument(
        '--scenario',
        choices=('all', 'motion', 'info', 'task', 'navigation'),
        default='all',
        help='Choose which stub scenario set to run.',
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    dispatcher = CommandDispatcher()

    for command in build_demo_commands(args.scenario):
        result = dispatcher.dispatch(command)
        print_result(command, result.status_text, result.speak_text)

    print_registry_snapshot(dispatcher)


if __name__ == '__main__':
    main()
