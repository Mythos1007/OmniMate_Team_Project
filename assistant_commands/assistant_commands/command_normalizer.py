from __future__ import annotations

from assistant_commands.command_schema import CanonicalCommand, CanonicalCommandName
from assistant_commands.parser_utils import clean_text, parse_command_args, strip_measurements_for_matching
from assistant_commands.synonyms import PHRASE_LOOKUP


class CommandNormalizer:
    """규칙 기반으로 자연어 명령을 정규 명령으로 변환한다."""

    def normalize(self, text: str) -> CanonicalCommand:
        """입력 문장을 CanonicalCommand로 변환한다.

        1) 기본 정제 문장으로 패턴 매칭
        2) 실패 시 단위/측정치 제거 문장으로 재시도
        3) 미매칭 시 unknown 명령 반환
        """
        cleaned_text = clean_text(text)
        command = self._match_command(cleaned_text)
        if command == "unknown":
            command = self._match_command(strip_measurements_for_matching(cleaned_text))

        if command == "unknown":
            original_text = text.strip()
            return CanonicalCommand(
                command="unknown",
                args={"original_text": original_text},
                original_text=original_text,
            )

        args = parse_command_args(cleaned_text)
        return CanonicalCommand(command=command, args=args, original_text=text.strip())

    def _match_command(self, text: str) -> CanonicalCommandName:
        """동의어 사전(PHRASE_LOOKUP) 순회로 명령 키를 찾는다."""
        for phrase, command in PHRASE_LOOKUP:
            if phrase in text:
                return command
        return "unknown"
