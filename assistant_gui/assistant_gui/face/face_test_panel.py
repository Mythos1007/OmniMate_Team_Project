from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from .face_controller import FaceController
from .face_models import FaceBaseState, TempExpression
from .face_page import FacePage


_BASE_LABELS = {
    "대기": FaceBaseState.IDLE,
    "듣는 중": FaceBaseState.LISTENING,
    "생각 중": FaceBaseState.THINKING,
    "이동 중": FaceBaseState.NAVIGATING,
    "확인 대기": FaceBaseState.WAITING_CONFIRMATION,
    "충전 중": FaceBaseState.CHARGING,
    "저배터리": FaceBaseState.LOW_BATTERY,
    "에러": FaceBaseState.ERROR,
    "비상정지": FaceBaseState.EMERGENCY_STOP,
}

_TEMP_LABELS = {
    "happy": TempExpression.HAPPY,
    "greeting": TempExpression.GREETING,
    "apologetic": TempExpression.APOLOGETIC,
    "surprised": TempExpression.SURPRISED,
}


class FaceTestPanel(QWidget):
    """설정 탭에서 사용하는 로봇 얼굴 개발/디버그 패널."""

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        controller: FaceController | None = None,
        use_shared_controller: bool = False,
    ) -> None:
        super().__init__(parent)
        self.controller = controller or FaceController(self)
        self._use_shared_controller = use_shared_controller and controller is not None

        # 설정 탭 테마(라이트/다크)를 그대로 따라가도록 패널 전용 스타일을 분리 기능.
        self.setObjectName("face_test_panel")
        self.apply_theme_style("light")

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        # 미리보기
        preview_group = QGroupBox("미리보기 영역")
        preview_layout = QVBoxLayout(preview_group)
        # shared controller일 때는 패널이 별도 타이머를 추가로 만들지 않는다.
        self.face_page = FacePage(controller=self.controller, autonomous=not self._use_shared_controller)
        preview_layout.addWidget(self.face_page)
        root.addWidget(preview_group)

        controls_row = QHBoxLayout()

        # 기본 표정
        base_group = QGroupBox("기본 표정 테스트")
        base_layout = QVBoxLayout(base_group)
        self.base_combo = QComboBox()
        for label in _BASE_LABELS:
            self.base_combo.addItem(label)
        self.base_combo.currentTextChanged.connect(self._on_base_changed)
        base_layout.addWidget(self.base_combo)
        controls_row.addWidget(base_group)

        # 임시 표정
        temp_group = QGroupBox("임시 표정 테스트")
        temp_layout = QFormLayout(temp_group)
        self.temp_combo = QComboBox()
        for label in _TEMP_LABELS:
            self.temp_combo.addItem(label)
        self.temp_duration = QSpinBox()
        self.temp_duration.setRange(1, 10)
        self.temp_duration.setValue(2)
        temp_btn = QPushButton("임시 표정 적용")
        temp_btn.clicked.connect(self._on_temp_apply)
        clear_temp_btn = QPushButton("temporary clear")
        clear_temp_btn.clicked.connect(self.controller.clear_temp)

        quick_row = QHBoxLayout()
        for text, expr in _TEMP_LABELS.items():
            btn = QPushButton(text)
            btn.clicked.connect(lambda _=False, e=expr: self.controller.trigger_temp(e, 1.2))
            quick_row.addWidget(btn)

        temp_layout.addRow("표정", self.temp_combo)
        temp_layout.addRow("지속(초)", self.temp_duration)
        temp_layout.addRow(temp_btn)
        temp_layout.addRow(clear_temp_btn)
        temp_layout.addRow(quick_row)
        controls_row.addWidget(temp_group)

        # 오버레이
        overlay_group = QGroupBox("오버레이 테스트")
        overlay_layout = QVBoxLayout(overlay_group)
        self.blink_enable = QCheckBox("Blink 활성")
        self.blink_enable.setChecked(True)
        self.blink_enable.toggled.connect(self.controller.set_blink_enabled)

        self.tts_active_toggle = QCheckBox("TTS active")
        self.tts_active_toggle.toggled.connect(self.controller.set_tts_active)

        self.speaking_enabled_toggle = QCheckBox("입 애니메이션 허용")
        self.speaking_enabled_toggle.setChecked(True)
        self.speaking_enabled_toggle.toggled.connect(self.controller.set_speaking_enabled)

        blink_once = QPushButton("Blink 강제 실행")
        blink_once.clicked.connect(self.controller.trigger_blink_once)

        overlay_layout.addWidget(self.blink_enable)
        overlay_layout.addWidget(self.tts_active_toggle)
        overlay_layout.addWidget(self.speaking_enabled_toggle)
        overlay_layout.addWidget(blink_once)
        controls_row.addWidget(overlay_group)

        root.addLayout(controls_row)

        # 상황별 시뮬레이션
        scenario_group = QGroupBox("상황별 시뮬레이션")
        scenario_grid = QGridLayout(scenario_group)
        actions = [
            ("사람 인식 인사", lambda: self.controller.on_person_recognized("guest")),
            ("listening transient 시작", self.controller.on_listening_started),
            ("listening transient 종료", self.controller.on_listening_finished),
            ("wakeword", self.controller.on_wakeword_detected),
            ("TTS 시작", self.controller.on_tts_started),
            ("TTS 종료", self.controller.on_tts_finished),
            ("배터리 부족", lambda: self.controller.on_battery_changed(10.0, charging=False)),
            ("배터리 회복", lambda: self.controller.on_battery_changed(35.0, charging=False)),
            ("충전 시작", self.controller.on_charging_started),
            ("충전 종료", self.controller.on_charging_finished),
            ("에러 발생", lambda: self.controller.on_error("manual")),
            ("에러 해제", lambda: self.controller.force_base(FaceBaseState.IDLE)),
        ]
        for idx, (text, cb) in enumerate(actions):
            btn = QPushButton(text)
            btn.clicked.connect(cb)
            scenario_grid.addWidget(btn, idx // 4, idx % 4)
        root.addWidget(scenario_group)

        # 디버그 정보
        debug_group = QGroupBox("디버그 정보")
        debug_layout = QFormLayout(debug_group)
        self.lbl_system_base = QLabel("-")
        self.lbl_display = QLabel("-")
        self.lbl_transient = QLabel("-")
        self.lbl_temp = QLabel("-")
        self.lbl_tts = QLabel("-")
        self.lbl_speaking_enabled = QLabel("-")
        self.lbl_blink_enabled = QLabel("-")
        self.lbl_blink_state = QLabel("-")
        self.lbl_mouth_state = QLabel("-")
        self.lbl_battery = QLabel("-")
        self.lbl_temp_left = QLabel("-")
        self.lbl_transient_left = QLabel("-")
        self.lbl_asset = QLabel("-")
        self.lbl_asset_exists = QLabel("-")
        self.lbl_asset_warn = QLabel("-")

        debug_layout.addRow("system base", self.lbl_system_base)
        debug_layout.addRow("display state", self.lbl_display)
        debug_layout.addRow("transient base", self.lbl_transient)
        debug_layout.addRow("temp expression", self.lbl_temp)
        debug_layout.addRow("tts_active", self.lbl_tts)
        debug_layout.addRow("speaking_enabled", self.lbl_speaking_enabled)
        debug_layout.addRow("blink_enabled", self.lbl_blink_enabled)
        debug_layout.addRow("blink_state", self.lbl_blink_state)
        debug_layout.addRow("mouth_state", self.lbl_mouth_state)
        debug_layout.addRow("battery", self.lbl_battery)
        debug_layout.addRow("temp 남은시간", self.lbl_temp_left)
        debug_layout.addRow("transient 남은시간", self.lbl_transient_left)
        debug_layout.addRow("asset", self.lbl_asset)
        debug_layout.addRow("asset exists", self.lbl_asset_exists)
        debug_layout.addRow("asset warnings", self.lbl_asset_warn)
        root.addWidget(debug_group)

        self._debug_timer = QTimer(self)
        self._debug_timer.timeout.connect(self._refresh_debug)
        self._debug_timer.start(200)
        self._refresh_debug()

    def apply_theme_style(self, theme: str) -> None:
        if theme == "dark":
            self.setStyleSheet(
                "#face_test_panel { background-color: #1F2937; }"
                "#face_test_panel QGroupBox { color: #F9FAFB; border: 1px solid #4B5563; border-radius: 8px; margin-top: 10px; background-color: #374151; }"
                "#face_test_panel QGroupBox::title { color: #F9FAFB; subcontrol-origin: margin; left: 8px; padding: 0 4px; }"
                "#face_test_panel QLabel { color: #F3F4F6; }"
                "#face_test_panel QCheckBox { color: #F3F4F6; }"
                "#face_test_panel QPushButton { color: #FFFFFF; background-color: #4B5563; border: 1px solid #6B7280; border-radius: 6px; padding: 6px 12px; }"
                "#face_test_panel QPushButton:hover { background-color: #6B7280; }"
                "#face_test_panel QPushButton:pressed { background-color: #374151; }"
                "#face_test_panel QComboBox, #face_test_panel QSpinBox, #face_test_panel QLineEdit { color: #FFFFFF; background-color: #374151; border: 1px solid #6B7280; border-radius: 6px; padding: 4px 6px; }"
                "#face_test_panel QComboBox QAbstractItemView { color: #FFFFFF; background-color: #374151; selection-background-color: #6B7280; selection-color: #FFFFFF; border: 1px solid #6B7280; }"
                "#face_test_panel QComboBox::drop-down { border: none; background-color: #2D3748; }"
                "#face_test_panel QComboBox::down-arrow { image: none; }"
                "#face_test_panel QSpinBox::up-button, #face_test_panel QSpinBox::down-button { border: 1px solid #6B7280; background-color: #4B5563; width: 16px; }"
                "#face_test_panel QSpinBox::up-button:hover, #face_test_panel QSpinBox::down-button:hover { background-color: #6B7280; }"
                "#face_test_panel QSpinBox::up-button:pressed, #face_test_panel QSpinBox::down-button:pressed { background-color: #2D3748; }"
                "#face_test_panel QSpinBox::up-button:disabled, #face_test_panel QSpinBox::down-button:disabled { background-color: #1F2937; border-color: #4B5563; }"
            )
            return

        self.setStyleSheet(
            "#face_test_panel { background-color: #F3F4F6; }"
            "#face_test_panel QGroupBox { color: #111827; border: 1px solid #9CA3AF; border-radius: 8px; margin-top: 10px; background-color: #E5E7EB; }"
            "#face_test_panel QGroupBox::title { color: #111827; subcontrol-origin: margin; left: 8px; padding: 0 4px; }"
            "#face_test_panel QLabel { color: #111827; }"
            "#face_test_panel QCheckBox { color: #111827; }"
            "#face_test_panel QPushButton { color: #111827; background-color: #D1D5DB; border: 1px solid #9CA3AF; border-radius: 6px; padding: 6px 12px; }"
            "#face_test_panel QPushButton:hover { background-color: #9CA3AF; }"
            "#face_test_panel QPushButton:pressed { background-color: #6B7280; color: #FFFFFF; }"
            "#face_test_panel QComboBox, #face_test_panel QSpinBox, #face_test_panel QLineEdit { color: #111827; background-color: #FFFFFF; border: 1px solid #9CA3AF; border-radius: 6px; padding: 4px 6px; }"
            "#face_test_panel QComboBox QAbstractItemView { color: #111827; background-color: #FFFFFF; selection-background-color: #3B82F6; selection-color: #FFFFFF; border: 1px solid #9CA3AF; }"
            "#face_test_panel QComboBox::drop-down { border: none; background-color: #F3F4F6; }"
            "#face_test_panel QComboBox::down-arrow { image: none; }"
            "#face_test_panel QSpinBox::up-button, #face_test_panel QSpinBox::down-button { border: 1px solid #9CA3AF; background-color: #D1D5DB; width: 16px; }"
            "#face_test_panel QSpinBox::up-button:hover, #face_test_panel QSpinBox::down-button:hover { background-color: #9CA3AF; }"
            "#face_test_panel QSpinBox::up-button:pressed, #face_test_panel QSpinBox::down-button:pressed { background-color: #6B7280; }"
            "#face_test_panel QSpinBox::up-button:disabled, #face_test_panel QSpinBox::down-button:disabled { background-color: #E5E7EB; border-color: #D1D5DB; }"
        )

    def _on_base_changed(self, label: str) -> None:
        self.controller.force_base(_BASE_LABELS[label])

    def _on_temp_apply(self) -> None:
        expression = _TEMP_LABELS[self.temp_combo.currentText()]
        self.controller.trigger_temp(expression, float(self.temp_duration.value()))

    def _refresh_debug(self) -> None:
        ctx = self.controller.context
        now = datetime.utcnow()

        temp_remain = 0.0
        if ctx.temp_until is not None:
            temp_remain = max(0.0, (ctx.temp_until - now).total_seconds())

        transient_remain = 0.0
        if ctx.transient_until is not None:
            transient_remain = max(0.0, (ctx.transient_until - now).total_seconds())

        self.lbl_system_base.setText(ctx.system_base_state.value)
        self.lbl_display.setText(ctx.display_state.value)
        self.lbl_transient.setText(ctx.transient_base_state.value if ctx.transient_base_state else "none")
        self.lbl_temp.setText(ctx.temp_expression.value)
        self.lbl_tts.setText(str(ctx.tts_active))
        self.lbl_speaking_enabled.setText(str(ctx.speaking_enabled))
        self.lbl_blink_enabled.setText(str(ctx.blink_enabled))
        self.lbl_blink_state.setText(self.controller.last_overlay.blink_state.value)
        self.lbl_mouth_state.setText(self.controller.last_overlay.mouth_state.value)
        self.lbl_battery.setText(
            f"{ctx.battery_percent:.1f}% / charging={ctx.is_charging} / low={ctx.low_battery_latched}"
        )
        self.lbl_temp_left.setText(f"{temp_remain:.2f}s")
        self.lbl_transient_left.setText(f"{transient_remain:.2f}s")

        info = self.controller.last_debug_info
        self.lbl_asset.setText(
            f"base={info.base_asset_name}, temp={info.temp_asset_name}, "
            f"blink={info.blink_asset_name}, mouth={info.mouth_asset_name}"
        )
        self.lbl_asset_exists.setText(
            f"base={info.base_asset_exists}, temp={info.temp_asset_exists}, "
            f"blink={info.blink_asset_exists}, mouth={info.mouth_asset_exists}"
        )
        self.lbl_asset_warn.setText(info.warnings or "-")
