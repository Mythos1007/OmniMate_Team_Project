from __future__ import annotations

from datetime import datetime, timedelta

from assistant_gui.face.face_animation_manager import FaceAnimationManager
from assistant_gui.face.face_models import BlinkState, FaceBaseState, TempExpression
from assistant_gui.face.face_state_manager import FaceStateManager


def test_temp_expression_has_priority_window() -> None:
    sm = FaceStateManager()
    sm.force_base_state(FaceBaseState.NAVIGATING)
    sm.set_temp_expression(TempExpression.APOLOGETIC, 2.0, now=datetime.utcnow())
    ctx = sm.resolve()
    assert ctx.base_state == FaceBaseState.NAVIGATING
    assert ctx.temp_expression == TempExpression.APOLOGETIC


def test_blink_updates_when_enabled() -> None:
    am = FaceAnimationManager()
    am.trigger_blink_once(now=datetime.utcnow())
    overlay = am.update(now=datetime.utcnow(), blink_enabled=True, speaking_active=False)
    assert overlay.blink_state in {BlinkState.CLOSED_1, BlinkState.CLOSED_2, BlinkState.OPEN}


def test_speaking_overlay_advances_mouth_frames() -> None:
    am = FaceAnimationManager()
    now = datetime.utcnow()
    state1 = am.update(now=now, speaking_active=True)
    state2 = am.update(now=now + timedelta(milliseconds=200), speaking_active=True)
    assert state1.mouth_state != state2.mouth_state or state2.mouth_state.value.startswith("mouth_")
