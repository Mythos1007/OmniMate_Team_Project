"""chat 카테고리 intent 에 대한 응답 생성 모듈.

실행 권한 없이 응답 텍스트만 생성한다.
향후 LLM 기반 응답이 필요하면 이 모듈의 _generate() 메서드를 교체한다.
"""
from __future__ import annotations

from assistant_brain.intent_rules import IntentClassification


_SMALLTALK_RESPONSES: dict[str, str] = {
    'hello':   '안녕하세요! 무엇을 도와드릴까요?',
    'hi':      '안녕하세요! 무엇을 도와드릴까요?',
    '안녕':    '안녕하세요! 부르셨나요?',
    '반가워':  '저도 반가워요! 뭔가 도움이 필요하신가요?',
}

_CAPABILITY_HINTS: tuple[str, ...] = (
    '뭐 할 수 있', '뭘 할 수 있', '어떤 기능', '뭘 해줄',
    '어떤 걸 해', '기능 알려', '도움말',
)

_CAPABILITY_RESPONSE = (
    '안내, 순찰, 우편 배달, 날씨 조회, 일정 및 알람 관리를 도와드릴 수 있어요. '
    '"회의실로 안내해줘", "순찰 시작해", "배터리 얼마나 남았어?" 처럼 말씀해 보세요.'
)

_WHY_NOT_MOVING = ('왜', '안 움직', '멈춰', '고장')
_WHY_NOT_RESPONSE = '현재 정지 상태거나 수행 중인 작업이 없어요. 명령을 말씀해 주세요.'


class ChatResponder:
    """chat intent 를 받아 응답 문자열을 반환 기능."""

    def respond(self, classification: IntentClassification) -> str:
        text = classification.slots.get('original_text', '')
        return self._generate(classification.intent_name, text)

    def _generate(self, intent_name: str, raw_text: str) -> str:
        normalized = raw_text.strip().lower()

        if intent_name == 'smalltalk':
            for keyword, response in _SMALLTALK_RESPONSES.items():
                if keyword in normalized:
                    return response
            return '안녕하세요! 무엇을 도와드릴까요?'

        if any(hint in normalized for hint in _CAPABILITY_HINTS):
            return _CAPABILITY_RESPONSE

        if any(hint in normalized for hint in _WHY_NOT_MOVING):
            return _WHY_NOT_RESPONSE

        if intent_name == 'unknown' and normalized:
            return f'죄송해요, "{raw_text.strip()}"은(는) 아직 이해하지 못했어요.'

        return '아직 그 요청은 이해하지 못했어요. 다시 말씀해 주시겠어요?'
