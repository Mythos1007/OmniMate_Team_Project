from __future__ import annotations

from assistant_commands.command_schema import CanonicalCommand, CanonicalCommandName
from assistant_commands.parser_utils import clean_text, parse_command_args, strip_measurements_for_matching
from assistant_commands.synonyms import PHRASE_LOOKUP


class CommandNormalizer:
    def normalize(self, text: str) -> CanonicalCommand:
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
        for phrase, command in PHRASE_LOOKUP:
            if phrase in text:
                return command
        return "unknown"
