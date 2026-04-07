from __future__ import annotations

from abc import ABC, abstractmethod
import re

from assistant_commands.command_schema import CanonicalCommand
from assistant_commands.parser_utils import clean_text


class AuxiliaryNormalizer(ABC):
    @abstractmethod
    def normalize(self, text: str) -> CanonicalCommand | None:
        """Return a canonical command suggestion or None when no confident match exists."""


class DisabledAuxiliaryNormalizer(AuxiliaryNormalizer):
    def normalize(self, text: str) -> CanonicalCommand | None:
        return None


class HeuristicAuxiliaryNormalizer(AuxiliaryNormalizer):
    """LLM fallback placeholder.

    This keeps the same interface a real GPT-backed normalizer would use, but
    relies on broader paraphrase heuristics so the rest of the pipeline can be
    exercised today without API credentials.
    """

    WEATHER_KEYWORDS = ('날씨', '기온', '비', '눈', '우산', '덥', '춥')
    WEATHER_QUESTION_HINTS = ('어때', '어떻', '오나', '올까', '필요', '어때요', '궁금')
    ALARM_LIST_HINTS = ('알람', '깨워', '목록', '리스트', '보여', '불러')
    SCHEDULE_LIST_HINTS = ('일정', '스케줄', '캘린더', '목록', '리스트', '보여', '불러')

    def normalize(self, text: str) -> CanonicalCommand | None:
        normalized = clean_text(text)

        weather_command = self._match_weather(normalized, text)
        if weather_command is not None:
            return weather_command

        alarm_command = self._match_alarm(normalized, text)
        if alarm_command is not None:
            return alarm_command

        schedule_command = self._match_schedule(normalized, text)
        if schedule_command is not None:
            return schedule_command

        guide_command = self._match_guidance(normalized, text)
        if guide_command is not None:
            return guide_command

        delivery_command = self._match_delivery(normalized, text)
        if delivery_command is not None:
            return delivery_command

        return None

    def _match_weather(self, normalized: str, text: str) -> CanonicalCommand | None:
        has_weather_signal = any(keyword in normalized for keyword in self.WEATHER_KEYWORDS)
        has_weather_question = any(keyword in normalized for keyword in self.WEATHER_QUESTION_HINTS)
        if has_weather_signal and (has_weather_question or '날씨' in normalized):
            return CanonicalCommand(command='weather_query', original_text=text)
        return None

    def _match_alarm(self, normalized: str, text: str) -> CanonicalCommand | None:
        if '알람' not in normalized and '깨워' not in normalized:
            return None

        if any(keyword in normalized for keyword in ('목록', '리스트', '보여', '불러')):
            return CanonicalCommand(command='alarm_list', original_text=text)

        time_match = re.search(r'(?P<hour>\d{1,2})\s*시(?:\s*(?P<minute>\d{1,2})\s*분)?', text)
        if any(keyword in normalized for keyword in ('설정', '맞춰', '저장', '깨워')) or time_match:
            hour = int(time_match.group('hour')) if time_match else 7
            minute = int(time_match.group('minute') or 0) if time_match else 0
            return CanonicalCommand(
                command='alarm_create',
                args={'time': f'{hour:02d}:{minute:02d}', 'label': '보조 정규화 알람'},
                original_text=text,
            )

        return None

    def _match_schedule(self, normalized: str, text: str) -> CanonicalCommand | None:
        if not any(keyword in normalized for keyword in ('일정', '스케줄', '캘린더')):
            return None

        if any(keyword in normalized for keyword in ('목록', '리스트', '보여', '불러')):
            return CanonicalCommand(command='schedule_list', original_text=text)

        if any(keyword in normalized for keyword in ('추가', '등록', '저장', '설정', '잡아')):
            time_match = re.search(r'(?P<hour>\d{1,2})\s*시(?:\s*(?P<minute>\d{1,2})\s*분)?', text)
            hour = int(time_match.group('hour')) if time_match else 9
            minute = int(time_match.group('minute') or 0) if time_match else 0
            date = '내일' if '내일' in normalized else '오늘'
            return CanonicalCommand(
                command='schedule_create',
                args={
                    'date': date,
                    'time': f'{hour:02d}:{minute:02d}',
                    'title': '보조 정규화 일정',
                },
                original_text=text,
            )

        return None

    def _match_guidance(self, normalized: str, text: str) -> CanonicalCommand | None:
        if not any(keyword in normalized for keyword in ('안내', '데려다', '데려가', '길', '위치')):
            return None

        location_match = re.search(r'(?P<location>.+?)(?:로|으로).*(?:안내|데려다|데려가)', text)
        location = location_match.group('location').strip() if location_match else '미지정 위치'
        return CanonicalCommand(command='guide_to_location', args={'location': location}, original_text=text)

    def _match_delivery(self, normalized: str, text: str) -> CanonicalCommand | None:
        if '우편물' not in normalized and not any(keyword in normalized for keyword in ('배달', '전달')):
            return None

        if not any(keyword in normalized for keyword in ('배달', '전달')):
            return None

        destination_match = re.search(r'(?P<destination>.+?)(?:으로|로).*(?:배달|전달)', text)
        destination = destination_match.group('destination').strip() if destination_match else '안내데스크'
        return CanonicalCommand(
            command='deliver_mail',
            args={'item': '우편물', 'destination': destination},
            original_text=text,
        )
