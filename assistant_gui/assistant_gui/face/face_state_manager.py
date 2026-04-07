from __future__ import annotations

import logging
from datetime import datetime, timedelta

from .face_models import FaceBaseState, FaceContext, TempExpression


class FaceStateManager:
    """system/transient/temp를 분리해 최종 display 상태를 계산한다."""

    LOW_BATTERY_ENTER_THRESHOLD = 15.0
    LOW_BATTERY_EXIT_THRESHOLD = 25.0

    def __init__(self, context: FaceContext | None = None, logger: logging.Logger | None = None) -> None:
        self.context = context or FaceContext()
        self._logger = logger or logging.getLogger(__name__)

    def set_system_base_state(self, state: FaceBaseState, *, now: datetime | None = None) -> None:
        now = now or datetime.utcnow()
        prev = self.context.system_base_state
        self.context.system_base_state = state

        if state not in {FaceBaseState.CHARGING, FaceBaseState.LOW_BATTERY}:
            self.context.fallback_base_state = state

        # TODO(ros): 충전 여부/배터리 잔량은 배터리 토픽 동기화가 가장 안전하다.
        # state 기반 입력만 있어도 표정이 어긋나지 않게 전원 관련 래치를 함께 동기화한다.
        if state == FaceBaseState.CHARGING:
            self.context.is_charging = True
            self.context.low_battery_latched = False
        elif state == FaceBaseState.LOW_BATTERY:
            self.context.is_charging = False
            self.context.low_battery_latched = True
        elif state not in {FaceBaseState.ERROR, FaceBaseState.EMERGENCY_STOP}:
            # 일반 상태로 복귀하면 power override를 해제한다.
            self.context.is_charging = False
            self.context.low_battery_latched = False

        self.context.last_update_time = now
        if prev != state:
            self._logger.debug("Face system base state changed: %s -> %s", prev.value, state.value)

    def force_base_state(self, state: FaceBaseState, *, now: datetime | None = None) -> None:
        self.set_system_base_state(state, now=now)

    def set_transient_base_state(self, state: FaceBaseState, duration_sec: float, *, now: datetime | None = None) -> None:
        now = now or datetime.utcnow()
        duration_sec = max(0.0, duration_sec)
        self.context.transient_base_state = state
        self.context.transient_until = now + timedelta(seconds=duration_sec)
        self.context.last_update_time = now
        self._logger.debug("Transient base state applied: %s (%.2fs)", state.value, duration_sec)

    def clear_transient_base_state(self, *, now: datetime | None = None) -> None:
        now = now or datetime.utcnow()
        if self.context.transient_base_state is not None:
            self._logger.debug("Transient base state cleared: %s", self.context.transient_base_state.value)
        self.context.transient_base_state = None
        self.context.transient_until = None
        self.context.last_update_time = now

    def set_temp_expression(self, expression: TempExpression, duration_sec: float, *, now: datetime | None = None) -> None:
        now = now or datetime.utcnow()
        self.context.temp_expression = expression
        self.context.temp_until = now + timedelta(seconds=max(0.0, duration_sec))
        self.context.last_update_time = now
        self._logger.debug("Temp expression applied: %s (%.2fs)", expression.value, duration_sec)

    def clear_temp_expression(self, *, now: datetime | None = None) -> None:
        now = now or datetime.utcnow()
        if self.context.temp_expression != TempExpression.NONE:
            self._logger.debug("Temp expression cleared: %s", self.context.temp_expression.value)
        self.context.temp_expression = TempExpression.NONE
        self.context.temp_until = None
        self.context.last_update_time = now

    def set_tts_active(self, active: bool, *, now: datetime | None = None) -> None:
        now = now or datetime.utcnow()
        if self.context.tts_active != active:
            self._logger.debug("TTS active changed: %s -> %s", self.context.tts_active, active)
        self.context.tts_active = active
        self.context.last_update_time = now

    def set_speaking_enabled(self, enabled: bool, *, now: datetime | None = None) -> None:
        now = now or datetime.utcnow()
        if self.context.speaking_enabled != enabled:
            self._logger.debug("Speaking enabled changed: %s -> %s", self.context.speaking_enabled, enabled)
        self.context.speaking_enabled = enabled
        self.context.last_update_time = now

    def set_blink_enabled(self, enabled: bool, *, now: datetime | None = None) -> None:
        now = now or datetime.utcnow()
        self.context.blink_enabled = enabled
        self.context.last_update_time = now

    def set_charging(self, charging: bool, *, now: datetime | None = None) -> None:
        now = now or datetime.utcnow()
        self.context.is_charging = charging
        if charging:
            self.context.system_base_state = FaceBaseState.CHARGING
            self.context.low_battery_latched = False
        else:
            # 충전 해제 시에는 직전 정상 상태로 복귀한다.
            if self.context.system_base_state == FaceBaseState.CHARGING:
                self.context.system_base_state = self.context.fallback_base_state
        self.context.last_update_time = now

    def update_battery(self, percent: float, *, charging: bool, now: datetime | None = None) -> None:
        now = now or datetime.utcnow()
        self.context.battery_percent = float(percent)
        self.context.is_charging = bool(charging)

        if self.context.is_charging:
            self.context.low_battery_latched = False
        elif self.context.battery_percent <= self.LOW_BATTERY_ENTER_THRESHOLD:
            self.context.low_battery_latched = True
        elif self.context.battery_percent >= self.LOW_BATTERY_EXIT_THRESHOLD:
            self.context.low_battery_latched = False

        self.context.last_update_time = now

    def _clear_expired_transient(self, *, now: datetime) -> None:
        if self.context.transient_until is not None and now >= self.context.transient_until:
            self.clear_transient_base_state(now=now)

    def _clear_expired_temp(self, *, now: datetime) -> None:
        if self.context.temp_until is not None and now >= self.context.temp_until:
            self.clear_temp_expression(now=now)

    def _resolve_display_state(self) -> FaceBaseState:
        system = self.context.system_base_state

        if system == FaceBaseState.EMERGENCY_STOP:
            return FaceBaseState.EMERGENCY_STOP
        if system == FaceBaseState.ERROR:
            return FaceBaseState.ERROR

        if self.context.is_charging:
            return FaceBaseState.CHARGING
        if self.context.low_battery_latched:
            return FaceBaseState.LOW_BATTERY

        if self.context.transient_base_state is not None:
            return self.context.transient_base_state

        if system in {FaceBaseState.CHARGING, FaceBaseState.LOW_BATTERY}:
            return self.context.fallback_base_state
        return system

    def resolve(self, *, now: datetime | None = None) -> FaceContext:
        now = now or datetime.utcnow()
        self._clear_expired_transient(now=now)
        self._clear_expired_temp(now=now)
        self.context.display_state = self._resolve_display_state()
        self.context.last_update_time = now
        return self.context
