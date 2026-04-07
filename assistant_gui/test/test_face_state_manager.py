from __future__ import annotations

from datetime import datetime, timedelta

from assistant_gui.face.face_models import FaceBaseState, TempExpression
from assistant_gui.face.face_state_manager import FaceStateManager


def test_temp_expression_auto_restore() -> None:
    sm = FaceStateManager()
    now = datetime.utcnow()
    sm.set_temp_expression(TempExpression.GREETING, 0.5, now=now)
    assert sm.context.temp_expression == TempExpression.GREETING

    sm.resolve(now=now + timedelta(seconds=0.6))
    assert sm.context.temp_expression == TempExpression.NONE


def test_state_priority_keeps_higher_state() -> None:
    sm = FaceStateManager()
    sm.force_base_state(FaceBaseState.ERROR)
    sm.set_base_state(FaceBaseState.IDLE)
    assert sm.context.base_state == FaceBaseState.ERROR


def test_tts_active_toggle() -> None:
    sm = FaceStateManager()
    sm.set_tts_active(True)
    assert sm.context.tts_active is True
    sm.set_tts_active(False)
    assert sm.context.tts_active is False
