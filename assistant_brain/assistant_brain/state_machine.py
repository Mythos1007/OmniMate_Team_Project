from __future__ import annotations

from dataclasses import dataclass

from assistant_interfaces.msg import AssistantState


# ─── canonical state names ──────────────────────────────────────────────────
SLEEPING = 'SLEEPING'       # 절전 모드 — wake word 대기 중
IDLE = 'IDLE'               # 깨어있음, 입력 대기
LISTENING = 'LISTENING'     # 사용자 발화 수신 중
PROCESSING = 'PROCESSING'   # 전사 결과 이해 / intent 분류 중
RESPONDING = 'RESPONDING'   # 응답(TTS) 출력 중
ACTING = 'ACTING'           # 로봇 물리 동작 수행 중
ERROR = 'ERROR'             # 처리 오류
EMERGENCY_STOP = 'EMERGENCY_STOP'

# ─── backward-compat aliases (기존 코드 수정 최소화) ────────────────────────
UNDERSTANDING = PROCESSING
SPEAKING = RESPONDING


VALID_TRANSITIONS: dict[str, set[str]] = {
    SLEEPING:       {IDLE, LISTENING, EMERGENCY_STOP},
    IDLE:           {SLEEPING, LISTENING, RESPONDING, EMERGENCY_STOP},
    LISTENING:      {PROCESSING, IDLE, SLEEPING, EMERGENCY_STOP},
    PROCESSING:     {ACTING, RESPONDING, IDLE, SLEEPING, ERROR, EMERGENCY_STOP},
    RESPONDING:     {IDLE, LISTENING, SLEEPING, EMERGENCY_STOP},
    ACTING:         {RESPONDING, IDLE, SLEEPING, ERROR, EMERGENCY_STOP},
    ERROR:          {IDLE, SLEEPING, EMERGENCY_STOP},
    EMERGENCY_STOP: {IDLE, SLEEPING},
}


@dataclass
class AssistantSnapshot:
    state: str = IDLE
    current_task: str = ''

    @property
    def busy(self) -> bool:
        return self.state not in {IDLE}


class AssistantStateMachine:
    """상위 수준의 어시스턴트 상태를 추적하고 전이 가능 여부를 검사 기능."""

    def __init__(self) -> None:
        self._snapshot = AssistantSnapshot()

    @property
    def snapshot(self) -> AssistantSnapshot:
        return self._snapshot

    def can_transition(self, next_state: str) -> bool:
        if next_state == self._snapshot.state:
            return True
        if next_state == EMERGENCY_STOP:
            return True
        return next_state in VALID_TRANSITIONS.get(self._snapshot.state, set())

    def transition(self, next_state: str, current_task: str = '') -> bool:
        if not self.can_transition(next_state):
            return False

        self._snapshot = AssistantSnapshot(state=next_state, current_task=current_task)
        return True

    def as_message(self) -> AssistantState:
        message = AssistantState()
        message.state = self._snapshot.state
        message.current_task = self._snapshot.current_task
        message.busy = self._snapshot.busy
        return message
