from __future__ import annotations

import re

from assistant_robot.interfaces.intent_parser import BaseIntentParser, IntentParseResult
from assistant_robot.models.command_request import CommandRequest
from assistant_robot.models.enums import CommandSource, MissionType


class MockIntentParser(BaseIntentParser):
    """기능: 테스트용 규칙 기반 intent parser.

    정책:
    - 한 문장에 여러 요청이 있으면 첫 번째만 primary
    - 나머지는 rejected_commands로 반환
    """

    def parse(self, raw_text: str) -> IntentParseResult:
        wakeword_detected = bool(re.search(r"옴니(\s*야)?", raw_text))
        cleaned = re.sub(r"옴니\s*야?", "", raw_text).strip()
        commands = self._extract_commands(cleaned)
        if wakeword_detected and not commands:
            return IntentParseResult(
                primary_command=CommandRequest(
                    source=CommandSource.VOICE,
                    raw_text=raw_text,
                    parsed_intent={"intent_name": MissionType.STATUS_BRIEF.value},
                    requires_movement=False,
                    payload={"action": "wakeword_ack"},
                )
            )
        if not commands:
            return IntentParseResult(primary_command=None)
        primary = commands[0]
        rejected = commands[1:]
        return IntentParseResult(
            primary_command=primary,
            rejected_commands=rejected,
            rejection_message_key="rejection.multi_command" if rejected else None,
        )

    def _extract_commands(self, text: str) -> list[CommandRequest]:
        commands: list[CommandRequest] = []
        # 기능: 연결어(그리고, 쉼표) 기준으로 문장을 분리해 발화 순서를 최대한 보존한다.
        segments = [segment.strip() for segment in re.split(r"그리고|,", text) if segment.strip()]
        for segment in segments:
            schedule_match = re.search(r"(오늘\s*)?일정\s*(알려\s*줘|보여\s*줘|확인\s*해\s*줘)?", segment)
            if schedule_match:
                commands.append(
                    CommandRequest(
                        source=CommandSource.VOICE,
                        raw_text=segment,
                        parsed_intent={"intent_name": MissionType.STATUS_BRIEF.value},
                        requires_movement=False,
                        payload={"action": "schedule_info"},
                    )
                )
                continue

            alarm_set_match = re.search(r"알람\s*(맞춰\s*줘|설정\s*해\s*줘|추가\s*해\s*줘)", segment)
            if alarm_set_match:
                commands.append(
                    CommandRequest(
                        source=CommandSource.VOICE,
                        raw_text=segment,
                        parsed_intent={"intent_name": MissionType.STATUS_BRIEF.value},
                        requires_movement=False,
                        payload={"action": "alarm_set"},
                    )
                )
                continue

            alarm_info_match = re.search(r"알람\s*(알려\s*줘|보여\s*줘|확인\s*해\s*줘)", segment)
            if alarm_info_match:
                commands.append(
                    CommandRequest(
                        source=CommandSource.VOICE,
                        raw_text=segment,
                        parsed_intent={"intent_name": MissionType.STATUS_BRIEF.value},
                        requires_movement=False,
                        payload={"action": "alarm_info"},
                    )
                )
                continue

            medication_match = re.search(r"(복약|약)\s*(알려\s*줘|확인\s*해\s*줘|체크\s*해\s*줘)", segment)
            if medication_match:
                commands.append(
                    CommandRequest(
                        source=CommandSource.VOICE,
                        raw_text=segment,
                        parsed_intent={"intent_name": MissionType.STATUS_BRIEF.value},
                        requires_movement=False,
                        payload={"action": "medication_info"},
                    )
                )
                continue

            cancel_match = re.search(r"(취소|중지|멈춰)\s*(해\s*줘)?", segment)
            if cancel_match:
                commands.append(
                    CommandRequest(
                        source=CommandSource.VOICE,
                        raw_text=segment,
                        parsed_intent={"intent_name": MissionType.STATUS_BRIEF.value},
                        requires_movement=False,
                        payload={"action": "cancel_request"},
                    )
                )
                continue

            status_match = re.search(r"어디\s*가\??", segment)
            if status_match:
                commands.append(
                    CommandRequest(
                        source=CommandSource.VOICE,
                        raw_text=segment,
                        parsed_intent={"intent_name": MissionType.STATUS_BRIEF.value},
                        requires_movement=False,
                    )
                )
                continue

            # STT 흔들림("날 씨")도 흡수하도록 공백 허용 패턴을 사용한다.
            weather_match = re.search(r"날\s*씨", segment)
            if weather_match:
                commands.append(
                    CommandRequest(
                        source=CommandSource.VOICE,
                        raw_text=segment,
                        parsed_intent={"intent_name": MissionType.WEATHER_TTS.value},
                        requires_movement=False,
                    )
                )
                continue

            move_match = re.search(r"(?P<target>[가-힣A-Za-z0-9_ ]+?)로 가", segment)
            if move_match:
                target = move_match.group("target").strip()
                commands.append(
                    CommandRequest(
                        source=CommandSource.VOICE,
                        raw_text=segment,
                        parsed_intent={"intent_name": MissionType.CALL.value},
                        requires_movement=True,
                        target_location=target,
                    )
                )
                continue

            guide_match = re.search(r"(?P<target>[가-힣A-Za-z0-9_ ]+?)\s*안내\s*해\s*줘", segment)
            if guide_match:
                target = guide_match.group("target").strip()
                commands.append(
                    CommandRequest(
                        source=CommandSource.VOICE,
                        raw_text=segment,
                        parsed_intent={"intent_name": MissionType.CALL.value},
                        requires_movement=True,
                        target_location=target,
                    )
                )
                continue

            # 우편/배달/배송/전달 — "~에 가져다줘", "~에 배달해줘", "~에 배달", "배달해줘" 단독 포함
            _DELIVERY_KEYWORDS = r"(?:우편|배달|배송|전달)"
            delivery_match = re.search(
                rf"(?P<target>[가-힣A-Za-z0-9_ ]+?)(?:에|로|으로)\s*{_DELIVERY_KEYWORDS}"
                rf"|{_DELIVERY_KEYWORDS}(?:\s*해\s*줘|\s*해\s*주세요|\s*시작)?",
                segment,
            )
            if delivery_match:
                target = delivery_match.group("target").strip()
                commands.append(
                    CommandRequest(
                        source=CommandSource.VOICE,
                        raw_text=segment,
                        parsed_intent={"intent_name": MissionType.DELIVERY.value, "requires_confirmation": True},
                        requires_movement=True,
                        target_location=target,
                    )
                )
                continue
        return commands
