from __future__ import annotations

import logging
from datetime import datetime

from PySide6.QtCore import QObject, QTimer, Signal

from .face_animation_manager import FaceAnimationManager, FaceOverlayState
from .face_asset_repository import FaceAssetRepository
from .face_models import FaceBaseState, FaceContext, TempExpression
from .face_renderer import FaceRenderDebugInfo, FaceRenderer
from .face_state_manager import FaceStateManager


class FaceController(QObject):
    """ROS/GUI 이벤트를 얼굴 상태로 변환하고 렌더 결과를 배포 기능."""

    face_updated = Signal(object, object)  # (QPixmap, FaceRenderDebugInfo)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._logger = logging.getLogger(__name__)
        self.state_manager = FaceStateManager(logger=self._logger)
        self.anim_manager = FaceAnimationManager()
        self.asset_repo = FaceAssetRepository()
        self.renderer = FaceRenderer(self.asset_repo)

        self._timer: QTimer | None = None
        self._timer_interval_ms = 100

        self._last_overlay = FaceOverlayState()
        self._last_debug_info = FaceRenderDebugInfo(
            display_state="idle",
            temp_expression="none",
            blink_state="open",
            mouth_state="mouth_0",
            speaking_active=False,
            base_asset_name="<none>",
            temp_asset_name="<none>",
            blink_asset_name="<none>",
            mouth_asset_name="<none>",
            base_asset_exists=False,
            temp_asset_exists=True,
            blink_asset_exists=True,
            mouth_asset_exists=False,
            base_fallback_used=False,
            warnings="",
        )

    @property
    def context(self) -> FaceContext:
        return self.state_manager.context

    @property
    def last_debug_info(self) -> FaceRenderDebugInfo:
        return self._last_debug_info

    @property
    def last_overlay(self) -> FaceOverlayState:
        return self._last_overlay

    @property
    def timer_running(self) -> bool:
        return self._timer is not None and self._timer.isActive()

    def start_timer(self, interval_ms: int = 100) -> None:
        """공유 컨트롤러에서도 중복 타이머가 생기지 않도록 단일 타이머만 운용 기능."""
        self._timer_interval_ms = max(16, int(interval_ms))
        if self._timer is None:
            self._timer = QTimer(self)
            self._timer.timeout.connect(self.tick)
        if not self._timer.isActive():
            self._timer.start(self._timer_interval_ms)
        self.tick()

    def stop_timer(self) -> None:
        if self._timer is not None and self._timer.isActive():
            self._timer.stop()

    def tick(self) -> None:
        now = datetime.utcnow()
        ctx = self.state_manager.resolve(now=now)
        overlay = self.anim_manager.update(
            now=now,
            blink_enabled=ctx.blink_enabled,
            speaking_active=ctx.tts_active and ctx.speaking_enabled,
        )
        self._last_overlay = overlay
        # 고해상도로 렌더링 후 뷰에서 화면 크기에 맞춰 스케일 기능.
        pixmap, debug = self.renderer.render(context=ctx, overlay=overlay, size=512)
        self._last_debug_info = debug
        self.face_updated.emit(pixmap, debug)

    def force_base(self, state: FaceBaseState) -> None:
        self.state_manager.set_system_base_state(state)

    def trigger_temp(self, expression: TempExpression, duration_sec: float) -> None:
        self.state_manager.set_temp_expression(expression, duration_sec)

    def clear_temp(self) -> None:
        self.state_manager.clear_temp_expression()

    def trigger_blink_once(self) -> None:
        self.anim_manager.trigger_blink_once()

    def set_tts_active(self, active: bool) -> None:
        self.state_manager.set_tts_active(active)

    def set_blink_enabled(self, enabled: bool) -> None:
        self.state_manager.set_blink_enabled(enabled)

    def set_speaking_enabled(self, enabled: bool) -> None:
        self.state_manager.set_speaking_enabled(enabled)

    def on_robot_state_changed(self, state_name: str) -> None:
        # TODO(ros): /assistant/state msg를 받아 여기로 전달
        if state_name == "LISTENING":
            self.on_listening_started()
            return

        self.state_manager.clear_transient_base_state()

        mapping = {
            "IDLE": FaceBaseState.IDLE,
            "SLEEPING": FaceBaseState.IDLE,
            "EXECUTING": FaceBaseState.NAVIGATING,
            "PROCESSING": FaceBaseState.THINKING,
            "RESPONDING": FaceBaseState.WAITING_CONFIRMATION,
            "ACTING": FaceBaseState.NAVIGATING,
            "WAITING_CONFIRMATION": FaceBaseState.WAITING_CONFIRMATION,
            "CHARGING": FaceBaseState.CHARGING,
            "LOW_BATTERY": FaceBaseState.LOW_BATTERY,
            "LOW_BATTERY_RESTRICTED": FaceBaseState.LOW_BATTERY,
            "ERROR": FaceBaseState.ERROR,
            "EMERGENCY_STOP": FaceBaseState.EMERGENCY_STOP,
        }
        mapped = mapping.get(state_name, FaceBaseState.IDLE)
        self.state_manager.set_system_base_state(mapped)

    def on_tts_started(self) -> None:
        self.state_manager.set_tts_active(True)

    def on_tts_finished(self) -> None:
        self.state_manager.set_tts_active(False)

    def on_wakeword_detected(self) -> None:
        # wakeword는 짧은 transient + surprised temp만 적용하고 base source는 훼손하지 않는다.
        self.state_manager.set_transient_base_state(FaceBaseState.LISTENING, 0.9)
        self.state_manager.set_temp_expression(TempExpression.SURPRISED, 0.9)

    def on_listening_started(self) -> None:
        self.state_manager.set_transient_base_state(FaceBaseState.LISTENING, 8.0)

    def on_listening_finished(self) -> None:
        self.state_manager.clear_transient_base_state()

    def on_processing_started(self, duration_sec: float = 1.4) -> None:
        self.state_manager.set_transient_base_state(FaceBaseState.THINKING, duration_sec)

    def on_processing_finished(self) -> None:
        if self.state_manager.context.transient_base_state == FaceBaseState.THINKING:
            self.state_manager.clear_transient_base_state()

    def on_person_recognized(self, name: str) -> None:
        self._logger.debug("Person recognized: %s", name)
        self.state_manager.set_temp_expression(TempExpression.GREETING, 1.5)

    def on_error(self, message: str) -> None:
        self._logger.debug("Face error event: %s", message)
        self.state_manager.set_system_base_state(FaceBaseState.ERROR)
        self.state_manager.set_temp_expression(TempExpression.APOLOGETIC, 2.0)

    def on_charging_started(self) -> None:
        self.state_manager.set_charging(True)

    def on_charging_finished(self) -> None:
        self.state_manager.set_charging(False)
        # 테스트/실운영 모두에서 즉시 상태 반영되도록 한 번 resolve를 유도 기능.
        self.state_manager.resolve()

    def on_battery_low(self, percent: float) -> None:
        self.state_manager.update_battery(percent=percent, charging=self.state_manager.context.is_charging)

    def on_battery_changed(self, percent: float, *, charging: bool) -> None:
        self.state_manager.update_battery(percent=percent, charging=charging)
