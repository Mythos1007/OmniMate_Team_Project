from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QTabWidget,
    QGroupBox,
    QFormLayout,
    QComboBox,
    QHBoxLayout,
    QCheckBox,
    QSpinBox,
    QScrollArea,
    QFrame,
    QTextEdit,
    QLineEdit,
    QPushButton,
    QMessageBox,
    QMainWindow,
    QSlider,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
)

try:
    from assistant_gui.face.face_controller import FaceController
    from assistant_gui.face.face_test_panel import FaceTestPanel
    from assistant_gui.config.app_constants import EDGE_TTS_VOICES
except ModuleNotFoundError:
    from face.face_controller import FaceController
    from face.face_test_panel import FaceTestPanel
    from config.app_constants import EDGE_TTS_VOICES


class SettingsPage(QWidget):
    def __init__(
        self,
        main_window: QMainWindow | None = None,
        shared_face_controller: FaceController | None = None,
        *,
        use_shared_controller: bool = False,
    ):
        super().__init__()
        self.main_window = main_window
        self.shared_face_controller = shared_face_controller
        self.setObjectName("settings_root")
        self._tts_template_editors: dict[str, QTextEdit] = {}
        self._syncing_tts_templates = False
        self._size_preset_mapping = {
            "초소형 (1280 x 420)": (1280, 420),
            "와이드 낮음 (1600 x 420)": (1600, 420),
            "와이드 컴팩트 (1600 x 480)": (1600, 480),
            "소형 (1024 x 576)": (1024, 576),
            "기본 (1600 x 560)": (1600, 560),
            "HD (1600 x 900)": (1600, 900),
            "FHD (1920 x 1080)": (1920, 1080),
        }

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 8, 20, 20)
        layout.setAlignment(Qt.AlignTop)
        title = QLabel("설정")
        title.setProperty("class", "TitleText")
        layout.addWidget(title)
        subtitle = QLabel("화면/동작 관련 설정을 즉시 적용할 수 있습니다.")
        subtitle.setProperty("class", "SubText")
        layout.addWidget(subtitle)

        tabs = QTabWidget()

        general_tab = QWidget()
        general_layout = QVBoxLayout(general_tab)

        display_group = QGroupBox("GUI 화면 설정")
        display_form = QFormLayout(display_group)

        self.size_preset_combo = QComboBox()
        self.size_preset_combo.addItems(list(self._size_preset_mapping.keys()))
        self.size_preset_combo.currentTextChanged.connect(self._on_size_preset_changed)
        self._selected_resolution = self._size_preset_mapping["기본 (1600 x 560)"]

        resolution_row = QHBoxLayout()
        resolution_row.addWidget(self.size_preset_combo)

        self.fullscreen_check = QCheckBox("전체 화면")
        self.fullscreen_check.toggled.connect(self._toggle_fullscreen)

        display_form.addRow("해상도", resolution_row)
        display_form.addRow("화면 모드", self.fullscreen_check)
        general_layout.addWidget(display_group)

        runtime_group = QGroupBox("동작 설정")
        runtime_form = QFormLayout(runtime_group)

        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["라이트", "다크"])
        self.theme_combo.currentTextChanged.connect(self._apply_theme)

        self.status_poll_spin = QSpinBox()
        self.status_poll_spin.setRange(500, 10000)
        self.status_poll_spin.setSingleStep(500)
        self.status_poll_spin.setValue(3000)
        self.status_poll_spin.valueChanged.connect(self._apply_status_poll_interval)

        self.face_fps_spin = QSpinBox()
        self.face_fps_spin.setRange(5, 60)
        self.face_fps_spin.setValue(10)
        self.face_fps_spin.valueChanged.connect(self._apply_face_fps)

        self.voice_backend_combo = QComboBox()
        self.voice_backend_combo.addItems(["자동", "Edge TTS", "Speech Dispatcher", "eSpeak NG"])
        self.voice_backend_combo.currentTextChanged.connect(self._apply_default_voice_backend)

        self.edge_voice_combo = QComboBox()
        self.edge_voice_combo.addItems(EDGE_TTS_VOICES)
        self.edge_voice_combo.currentTextChanged.connect(self._apply_default_edge_voice)
        self.edge_voice_combo.setObjectName("edge_voice_combo")
        self.voice_engine_setting_label = QLabel("보이스 엔진 설정")

        self.wakeword_reply_only_check = QCheckBox("호출어 응답 전용 테스트")
        self.wakeword_reply_only_check.toggled.connect(self._apply_wakeword_reply_only)

        self.pc_local_voice_check = QCheckBox("노트북 로컬 호출어 사용")
        self.pc_local_voice_check.toggled.connect(self._apply_pc_local_voice_enabled)

        self.robot_voice_input_check = QCheckBox("로봇 음성 입력 사용")
        self.robot_voice_input_check.toggled.connect(self._apply_robot_voice_input_enabled)
        self.robot_voice_input_status_label = QLabel("로봇 음성 입력 런타임 토글 상태")
        self.robot_voice_input_status_label.setWordWrap(True)
        self.robot_voice_input_status_label.setProperty("class", "SubText")

        self.person_greeting_check = QCheckBox("사람 인식 인사 로직 사용")
        self.person_greeting_check.toggled.connect(self._apply_person_greeting_enabled)
        self.person_greeting_status_label = QLabel("사람 인식 인사 로직 런타임 토글 상태")
        self.person_greeting_status_label.setWordWrap(True)
        self.person_greeting_status_label.setProperty("class", "SubText")

        self.robot_volume_slider = QSlider(Qt.Horizontal)
        self.robot_volume_slider.setRange(0, 100)
        self.robot_volume_slider.setSingleStep(5)
        self.robot_volume_slider.setPageStep(10)
        self.robot_volume_slider.valueChanged.connect(self._on_robot_volume_slider_changed)
        self.robot_volume_value_label = QLabel("35%")
        self.robot_volume_value_label.setMinimumWidth(48)
        self.robot_volume_apply_btn = QPushButton("로봇 볼륨 적용")
        self.robot_volume_apply_btn.clicked.connect(self._apply_robot_speaker_volume)
        self.robot_volume_status_label = QLabel("저장된 값만 바뀝니다. 적용 버튼을 누르면 로봇에 전송합니다.")
        self.robot_volume_status_label.setWordWrap(True)
        self.robot_volume_status_label.setProperty("class", "SubText")

        volume_row = QHBoxLayout()
        volume_row.addWidget(self.robot_volume_slider, stretch=1)
        volume_row.addWidget(self.robot_volume_value_label)
        volume_row.addWidget(self.robot_volume_apply_btn)

        runtime_form.addRow("테마", self.theme_combo)
        runtime_form.addRow("상태 갱신 주기(ms)", self.status_poll_spin)
        runtime_form.addRow("얼굴 애니메이션 FPS", self.face_fps_spin)
        runtime_form.addRow("기본 음성 엔진", self.voice_backend_combo)
        runtime_form.addRow(self.voice_engine_setting_label, self.edge_voice_combo)
        runtime_form.addRow("노트북 로컬 호출어", self.pc_local_voice_check)
        runtime_form.addRow("로봇 음성 입력", self.robot_voice_input_check)
        runtime_form.addRow("로봇 음성 입력 상태", self.robot_voice_input_status_label)
        runtime_form.addRow("사람 인식 인사", self.person_greeting_check)
        runtime_form.addRow("사람 인식 상태", self.person_greeting_status_label)
        runtime_form.addRow("로봇 스피커 볼륨", volume_row)
        runtime_form.addRow("볼륨 적용 상태", self.robot_volume_status_label)
        runtime_form.addRow("음성 테스트 모드", self.wakeword_reply_only_check)
        runtime_form.addRow("테스트 탭 컨트롤러", QLabel("공유" if use_shared_controller else "독립"))
        general_layout.addWidget(runtime_group)

        info_group = QGroupBox("안내")
        info_layout = QVBoxLayout(info_group)
        info_layout.addWidget(QLabel("- 해상도는 프리셋을 선택하면 즉시 적용됩니다."))
        info_layout.addWidget(QLabel("- 창 테두리를 드래그해서 수동 리사이즈도 가능합니다."))
        info_layout.addWidget(QLabel("- 테마는 즉시 반영되고 재실행 후에도 유지됩니다."))
        info_layout.addWidget(QLabel("- 얼굴 FPS를 높이면 부드럽지만 CPU 사용량이 늘 수 있습니다."))
        info_layout.addWidget(QLabel("- 기본 음성 엔진은 호출어 응답 TTS에 우선 적용됩니다."))
        info_layout.addWidget(QLabel("- Edge TTS를 사용하려면 edge-tts 실행 파일이 필요합니다."))
        info_layout.addWidget(QLabel("- 호출어 응답 전용 테스트를 켜면 '옴니야'에만 응답하고 명령은 받지 않습니다."))
        info_layout.addWidget(QLabel("- 테스트 탭은 운영 상태와 분리 또는 공유 모드로 동작합니다."))
        general_layout.addWidget(info_group)

        general_layout.addStretch()

        tts_tab = QWidget()
        tts_layout = QVBoxLayout(tts_tab)

        tts_desc = QLabel("상황별 TTS 문구를 수정하고 바로 미리듣기할 수 있습니다. {장소}, {명령}, {시간}, {날짜} 플레이스홀더를 지원합니다.")
        tts_desc.setWordWrap(True)
        tts_desc.setProperty("class", "SubText")
        tts_layout.addWidget(tts_desc)

        tts_scroll = QScrollArea()
        tts_scroll.setWidgetResizable(True)
        tts_scroll.setFrameShape(QFrame.NoFrame)
        tts_scroll_body = QWidget()
        tts_scroll_body.setObjectName("tts_scroll_body")
        tts_scroll_layout = QVBoxLayout(tts_scroll_body)
        tts_scroll_layout.setContentsMargins(4, 4, 4, 4)
        tts_scroll_layout.setSpacing(10)

        scenarios = self.main_window.get_tts_scenario_items() if self.main_window is not None else []
        for key, label in scenarios:
            group = QGroupBox()
            group_layout = QVBoxLayout(group)
            group_layout.setContentsMargins(10, 10, 10, 10)
            group_layout.setSpacing(8)

            row = QHBoxLayout()
            name_lbl = QLabel(label)
            name_lbl.setStyleSheet("font-weight: bold;")
            listen_btn = QPushButton("듣기")
            listen_btn.clicked.connect(lambda checked=False, k=key: self._listen_tts_scenario(k))
            row.addWidget(name_lbl)
            row.addStretch()
            row.addWidget(listen_btn)
            group_layout.addLayout(row)

            editor = QTextEdit()
            editor.setFixedHeight(72)
            editor.textChanged.connect(lambda k=key, e=editor: self._on_tts_template_changed(k, e))
            group_layout.addWidget(editor)
            self._tts_template_editors[key] = editor
            tts_scroll_layout.addWidget(group)

        tts_scroll_layout.addStretch()
        tts_scroll.setWidget(tts_scroll_body)
        tts_layout.addWidget(tts_scroll, stretch=1)

        test_group = QGroupBox("상황별 출력 테스트")
        test_layout = QVBoxLayout(test_group)

        test_row = QHBoxLayout()
        test_row.addWidget(QLabel("상황"))
        self.tts_test_scenario_combo = QComboBox()
        for key, label in scenarios:
            self.tts_test_scenario_combo.addItem(label, key)
        self.tts_test_scenario_combo.currentIndexChanged.connect(self._update_tts_test_preview)
        test_row.addWidget(self.tts_test_scenario_combo, stretch=1)

        test_row.addWidget(QLabel("장소 값"))
        self.tts_test_place_input = QLineEdit()
        self.tts_test_place_input.setPlaceholderText("예: 회의실")
        self.tts_test_place_input.textChanged.connect(self._update_tts_test_preview)
        test_row.addWidget(self.tts_test_place_input, stretch=1)
        test_layout.addLayout(test_row)

        self.tts_test_preview = QLineEdit()
        self.tts_test_preview.setReadOnly(True)
        self.tts_test_preview.setPlaceholderText("미리보기")
        test_layout.addWidget(self.tts_test_preview)

        test_btn_row = QHBoxLayout()
        self.tts_test_target_combo = QComboBox()
        self.tts_test_target_combo.addItems(["PC", "로봇"])
        test_btn_row.addWidget(self.tts_test_target_combo)

        test_speak_btn = QPushButton("테스트 출력")
        test_speak_btn.setProperty("class", "PrimaryBtn")
        test_speak_btn.clicked.connect(self._run_tts_scenario_test)
        test_btn_row.addWidget(test_speak_btn)

        reset_tts_btn = QPushButton("기본값으로 초기화")
        reset_tts_btn.clicked.connect(self._reset_tts_templates)
        test_btn_row.addWidget(reset_tts_btn)
        test_btn_row.addStretch()
        test_layout.addLayout(test_btn_row)
        tts_layout.addWidget(test_group)

        place_tab = QWidget()
        place_layout = QVBoxLayout(place_tab)

        place_desc = QLabel("장소 이름과 좌표를 여기서 수정하면 홈 화면 빠른 목적지와 이름 기반 안내에 함께 반영됩니다.")
        place_desc.setWordWrap(True)
        place_desc.setProperty("class", "SubText")
        place_layout.addWidget(place_desc)

        self.place_table = QTableWidget(0, 7)
        self.place_table.setHorizontalHeaderLabels(["장소 이름", "frame", "x", "y", "yaw", "aliases", "OCR"])
        self.place_table.verticalHeader().setVisible(False)
        self.place_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.place_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.place_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.place_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.place_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.place_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.Stretch)
        self.place_table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeToContents)
        place_layout.addWidget(self.place_table, stretch=1)

        place_btn_row = QHBoxLayout()
        add_place_btn = QPushButton("행 추가")
        add_place_btn.clicked.connect(self._add_place_row)
        place_btn_row.addWidget(add_place_btn)

        remove_place_btn = QPushButton("선택 행 삭제")
        remove_place_btn.clicked.connect(self._remove_selected_place_rows)
        place_btn_row.addWidget(remove_place_btn)

        reload_place_btn = QPushButton("다시 불러오기")
        reload_place_btn.clicked.connect(self._reload_place_table)
        place_btn_row.addWidget(reload_place_btn)

        save_place_btn = QPushButton("장소 저장")
        save_place_btn.setProperty("class", "PrimaryBtn")
        save_place_btn.clicked.connect(self._save_place_table)
        place_btn_row.addWidget(save_place_btn)
        place_btn_row.addStretch()
        place_layout.addLayout(place_btn_row)

        self._sync_ui_from_runtime()
        self._sync_tts_templates_from_runtime()
        self._reload_place_table()
        self._update_tts_test_preview()
        self._apply_local_theme_style()

        if shared_face_controller is not None and use_shared_controller:
            self.face_tab = FaceTestPanel(controller=shared_face_controller, use_shared_controller=True)
        else:
            self.face_tab = FaceTestPanel()

        current_theme = getattr(self.main_window, "_theme_mode", "light") if self.main_window is not None else "light"
        self.face_tab.apply_theme_style(current_theme)

        face_tab_scroll = QScrollArea()
        face_tab_scroll.setWidgetResizable(True)
        face_tab_scroll.setFrameShape(QFrame.NoFrame)
        face_tab_scroll.setWidget(self.face_tab)

        tabs.addTab(general_tab, "일반")
        tabs.addTab(tts_tab, "상황별 TTS")
        tabs.addTab(place_tab, "장소 설정")
        tabs.addTab(face_tab_scroll, "로봇 얼굴")
        layout.addWidget(tabs)

    def _sync_ui_from_runtime(self) -> None:
        if self.main_window is None:
            return
        current_w = max(800, self.main_window.width())
        current_h = max(360, self.main_window.height())

        preset_by_size = {size: label for label, size in self._size_preset_mapping.items()}
        preset = preset_by_size.get((current_w, current_h), "기본 (1600 x 560)")
        self.size_preset_combo.blockSignals(True)
        self.size_preset_combo.setCurrentText(preset)
        self.size_preset_combo.blockSignals(False)
        self._on_size_preset_changed(preset)

        self.fullscreen_check.blockSignals(True)
        self.fullscreen_check.setChecked(self.main_window.isFullScreen())
        self.fullscreen_check.blockSignals(False)

        poll_timer = getattr(self.main_window, "_status_poll_timer", None)
        if poll_timer is not None:
            self.status_poll_spin.blockSignals(True)
            self.status_poll_spin.setValue(max(500, poll_timer.interval()))
            self.status_poll_spin.blockSignals(False)

        if self.shared_face_controller is not None:
            ms = max(16, int(getattr(self.shared_face_controller, "_timer_interval_ms", 100)))
            fps = max(5, min(60, round(1000 / ms)))
            self.face_fps_spin.blockSignals(True)
            self.face_fps_spin.setValue(fps)
            self.face_fps_spin.blockSignals(False)

        current_theme = getattr(self.main_window, "_theme_mode", "light")
        self.theme_combo.blockSignals(True)
        self.theme_combo.setCurrentText("다크" if current_theme == "dark" else "라이트")
        self.theme_combo.blockSignals(False)

        backend_to_label = {
            "auto": "자동",
            "edge_tts": "Edge TTS",
            "speech_dispatcher": "Speech Dispatcher",
            "espeak_ng": "eSpeak NG",
        }
        current_backend = str(getattr(self.main_window, "_default_voice_backend", "auto"))
        self.voice_backend_combo.blockSignals(True)
        self.voice_backend_combo.setCurrentText(backend_to_label.get(current_backend, "자동"))
        self.voice_backend_combo.blockSignals(False)

        current_edge_voice = str(getattr(self.main_window, "_default_edge_voice", "ko-KR-SunHiNeural"))
        self.edge_voice_combo.blockSignals(True)
        if current_edge_voice in EDGE_TTS_VOICES:
            self.edge_voice_combo.setCurrentText(current_edge_voice)
        else:
            self.edge_voice_combo.setCurrentText("ko-KR-SunHiNeural")
        self.edge_voice_combo.blockSignals(False)
        self._refresh_voice_engine_setting_ui()

        self.wakeword_reply_only_check.blockSignals(True)
        self.wakeword_reply_only_check.setChecked(bool(getattr(self.main_window, "_wakeword_reply_only", False)))
        self.wakeword_reply_only_check.blockSignals(False)

        self.pc_local_voice_check.blockSignals(True)
        self.pc_local_voice_check.setChecked(bool(getattr(self.main_window, "_face_voice_loop_enabled", True)))
        self.pc_local_voice_check.blockSignals(False)

        self.robot_voice_input_check.blockSignals(True)
        self.robot_voice_input_check.setChecked(bool(getattr(self.main_window, "_robot_voice_input_enabled", True)))
        self.robot_voice_input_check.blockSignals(False)

        self.person_greeting_check.blockSignals(True)
        self.person_greeting_check.setChecked(bool(getattr(self.main_window, "_person_greeting_enabled", False)))
        self.person_greeting_check.blockSignals(False)

        current_robot_volume = int(getattr(self.main_window, "_robot_speaker_volume", 70))
        self.robot_volume_slider.blockSignals(True)
        self.robot_volume_slider.setValue(max(0, min(100, current_robot_volume)))
        self.robot_volume_slider.blockSignals(False)
        self._on_robot_volume_slider_changed(self.robot_volume_slider.value())

    def _sync_tts_templates_from_runtime(self) -> None:
        if self.main_window is None:
            return
        self._syncing_tts_templates = True
        try:
            for key, editor in self._tts_template_editors.items():
                editor.blockSignals(True)
                editor.setPlainText(self.main_window.get_tts_template(key))
                editor.blockSignals(False)
        finally:
            self._syncing_tts_templates = False

    def _build_tts_context(self, *, place_override: str | None = None) -> dict[str, str]:
        if self.main_window is None:
            return {}
        context = self.main_window.build_tts_runtime_context(command_text="")
        if place_override is not None and place_override.strip():
            context["장소"] = place_override.strip()
            context["location"] = place_override.strip()
        return context

    def _on_tts_template_changed(self, key: str, editor: QTextEdit) -> None:
        if self.main_window is None or self._syncing_tts_templates:
            return
        self.main_window.set_tts_template(key, editor.toPlainText())
        self._update_tts_test_preview()

    def _listen_tts_scenario(self, key: str) -> None:
        if self.main_window is None:
            return
        text = self.main_window.render_tts_scenario(key, self._build_tts_context())
        ok, msg = self.main_window.speak_text(text, target="pc")
        if not ok:
            QMessageBox.warning(self, "TTS 실행 실패", f"상황별 TTS 실행에 실패했습니다.\n{msg}")

    def _current_test_scenario_key(self) -> str:
        key = self.tts_test_scenario_combo.currentData()
        if not key:
            key = "unknown"
        return str(key)

    def _update_tts_test_preview(self) -> None:
        if self.main_window is None:
            return
        scenario_key = self._current_test_scenario_key()
        place = self.tts_test_place_input.text().strip()
        preview = self.main_window.render_tts_scenario(
            scenario_key,
            self._build_tts_context(place_override=place),
        )
        self.tts_test_preview.setText(preview)

    def _run_tts_scenario_test(self) -> None:
        if self.main_window is None:
            return
        self._update_tts_test_preview()
        text = self.tts_test_preview.text().strip()
        if not text:
            return
        target = "robot" if self.tts_test_target_combo.currentText() == "로봇" else "pc"
        ok, msg = self.main_window.speak_text(text, target=target)
        if ok:
            return

        if target == "robot":
            fallback_ok, fallback_msg = self.main_window.speak_text(text, target="pc")
            if fallback_ok:
                QMessageBox.information(
                    self,
                    "로봇 출력 실패",
                    f"로봇 출력에 실패해 PC로 대신 출력했습니다.\n사유: {msg}",
                )
                return
            QMessageBox.warning(
                self,
                "TTS 실행 실패",
                f"로봇/PC 출력 모두 실패했습니다.\n로봇: {msg}\nPC: {fallback_msg}",
            )
            return

        QMessageBox.warning(self, "TTS 실행 실패", f"상황별 TTS 실행에 실패했습니다.\n{msg}")

    def _reset_tts_templates(self) -> None:
        if self.main_window is None:
            return
        self.main_window.reset_tts_templates()
        self._sync_tts_templates_from_runtime()
        self._update_tts_test_preview()

    def _set_place_cell(self, row: int, column: int, value: object) -> None:
        item = QTableWidgetItem(str(value))
        if column == 6:
            item.setText("true" if bool(value) else "false")
        self.place_table.setItem(row, column, item)

    def _add_place_row(self, place: dict[str, object] | None = None) -> None:
        row = self.place_table.rowCount()
        self.place_table.insertRow(row)
        place_data = place or {}
        aliases = place_data.get("aliases", [])
        if isinstance(aliases, list):
            aliases_text = ", ".join(str(alias) for alias in aliases if str(alias).strip())
        else:
            aliases_text = str(aliases or "")
        values = [
            place_data.get("name", ""),
            place_data.get("frame_id", "map"),
            place_data.get("x", 0.0),
            place_data.get("y", 0.0),
            place_data.get("yaw", 0.0),
            aliases_text,
            place_data.get("ocr_enabled", False),
        ]
        for column, value in enumerate(values):
            self._set_place_cell(row, column, value)

    def _remove_selected_place_rows(self) -> None:
        rows = sorted({index.row() for index in self.place_table.selectedIndexes()}, reverse=True)
        for row in rows:
            self.place_table.removeRow(row)

    def _reload_place_table(self) -> None:
        self.place_table.setRowCount(0)
        if self.main_window is None or not hasattr(self.main_window, "get_named_place_items"):
            return
        for place in self.main_window.get_named_place_items():
            self._add_place_row(place)

    def _collect_place_rows(self) -> list[dict[str, object]]:
        items: list[dict[str, object]] = []
        for row in range(self.place_table.rowCount()):
            name_item = self.place_table.item(row, 0)
            frame_item = self.place_table.item(row, 1)
            x_item = self.place_table.item(row, 2)
            y_item = self.place_table.item(row, 3)
            yaw_item = self.place_table.item(row, 4)
            aliases_item = self.place_table.item(row, 5)
            ocr_item = self.place_table.item(row, 6)

            name = name_item.text().strip() if name_item is not None else ""
            if not name:
                continue

            try:
                x_value = float(x_item.text().strip()) if x_item is not None else 0.0
                y_value = float(y_item.text().strip()) if y_item is not None else 0.0
                yaw_value = float(yaw_item.text().strip()) if yaw_item is not None else 0.0
            except ValueError as exc:
                raise ValueError(f"{row + 1}번째 행 좌표 값이 올바르지 않습니다: {exc}") from exc

            aliases_text = aliases_item.text().strip() if aliases_item is not None else ""
            aliases = [alias.strip() for alias in aliases_text.split(",") if alias.strip()]
            ocr_text = ocr_item.text().strip().lower() if ocr_item is not None else "false"
            items.append(
                {
                    "name": name,
                    "frame_id": frame_item.text().strip() if frame_item is not None and frame_item.text().strip() else "map",
                    "x": x_value,
                    "y": y_value,
                    "yaw": yaw_value,
                    "aliases": aliases,
                    "ocr_enabled": ocr_text in {"1", "true", "yes", "on", "y"},
                }
            )
        return items

    def _save_place_table(self) -> None:
        if self.main_window is None or not hasattr(self.main_window, "save_named_place_items"):
            return
        try:
            items = self._collect_place_rows()
        except ValueError as exc:
            QMessageBox.warning(self, "장소 저장 실패", str(exc))
            return

        ok, message = self.main_window.save_named_place_items(items)
        if not ok:
            QMessageBox.warning(self, "장소 저장 실패", message)
            return
        QMessageBox.information(self, "장소 저장", message)
        self._reload_place_table()

    def _on_size_preset_changed(self, text: str) -> None:
        size = self._size_preset_mapping.get(text)
        if size is None:
            return
        self._selected_resolution = size

        if self.main_window is not None and not self.main_window.isFullScreen():
            self.main_window.apply_window_size(self._selected_resolution[0], self._selected_resolution[1])

    def _toggle_fullscreen(self, checked: bool) -> None:
        if self.main_window is None:
            return
        self.main_window.apply_fullscreen(checked, self._selected_resolution[0], self._selected_resolution[1])

    def _apply_status_poll_interval(self, value: int) -> None:
        if self.main_window is None:
            return
        self.main_window.apply_status_poll_interval(int(value))

    def _apply_face_fps(self, fps: int) -> None:
        if self.shared_face_controller is None or self.main_window is None:
            return
        self.main_window.apply_face_fps(int(fps))

    def _apply_default_voice_backend(self, label: str) -> None:
        if self.main_window is None:
            return
        self.main_window.apply_default_voice_backend(label)
        self._refresh_voice_engine_setting_ui()

    def _apply_default_edge_voice(self, _text: str | None = None) -> None:
        if self.main_window is None:
            return
        self.main_window.apply_default_edge_voice(self.edge_voice_combo.currentText())

    def _refresh_voice_engine_setting_ui(self) -> None:
        backend_label = self.voice_backend_combo.currentText().strip()
        is_edge = backend_label == "Edge TTS"

        if is_edge:
            self.voice_engine_setting_label.setText("보이스 엔진 설정 (음성 선택)")
            self.edge_voice_combo.setEnabled(True)
            self.edge_voice_combo.setToolTip("Edge TTS에서 사용할 음성을 선택합니다.")
            if self.edge_voice_combo.count() == 0:
                self.edge_voice_combo.addItems(EDGE_TTS_VOICES)
            return

        if backend_label == "자동":
            self.voice_engine_setting_label.setText("보이스 엔진 설정 (자동)")
            self.edge_voice_combo.setToolTip("기본 음성 엔진이 자동일 때는 별도 음성 선택이 비활성화됩니다.")
        else:
            self.voice_engine_setting_label.setText(f"보이스 엔진 설정 ({backend_label})")
            self.edge_voice_combo.setToolTip(f"{backend_label} 엔진은 현재 이 화면에서 별도 음성 선택을 사용하지 않습니다.")
        self.edge_voice_combo.setEnabled(False)

    def _apply_wakeword_reply_only(self, checked: bool) -> None:
        if self.main_window is None:
            return
        self.main_window.apply_wakeword_reply_only(bool(checked))

    def _apply_pc_local_voice_enabled(self, checked: bool) -> None:
        if self.main_window is None:
            return
        self.main_window.apply_pc_local_voice_enabled(bool(checked))

    def _apply_robot_voice_input_enabled(self, checked: bool) -> None:
        if self.main_window is None:
            return
        ok, message = self.main_window.apply_robot_voice_input_enabled(bool(checked), publish=True)
        self.robot_voice_input_status_label.setText(message)
        if ok:
            return
        QMessageBox.warning(self, "로봇 음성 입력 적용 실패", message)

    def _apply_person_greeting_enabled(self, checked: bool) -> None:
        if self.main_window is None:
            return
        ok, message = self.main_window.apply_person_greeting_enabled(bool(checked), publish=True)
        self.person_greeting_status_label.setText(message)
        if ok:
            return
        QMessageBox.warning(self, "사람 인식 인사 적용 실패", message)

    def _on_robot_volume_slider_changed(self, value: int) -> None:
        self.robot_volume_value_label.setText(f"{int(value)}%")

    def _apply_robot_speaker_volume(self) -> None:
        if self.main_window is None:
            return
        ok, message = self.main_window.apply_robot_speaker_volume(self.robot_volume_slider.value(), publish=True)
        self.robot_volume_status_label.setText(message)
        if ok:
            return
        QMessageBox.warning(self, "로봇 볼륨 적용 실패", message)

    def _apply_theme(self, label: str) -> None:
        if self.main_window is None:
            return
        theme = "dark" if label == "다크" else "light"
        self.main_window.apply_theme(theme)
        self._apply_local_theme_style()

    def _apply_local_theme_style(self) -> None:
        theme = getattr(self.main_window, "_theme_mode", "light") if self.main_window is not None else "light"
        if theme == "dark":
            self.setStyleSheet(
                "QWidget#settings_root { background-color: #374151; }"
                "QWidget#tts_scroll_body { background-color: #4B5563; }"
                "QTabWidget { background-color: #4B5563; }"
                "QTabWidget::tab-bar { left: 0px; }"
                "QTabWidget::pane { background-color: #4B5563; border: 1px solid #6B7280; border-top-left-radius: 0px; border-top-right-radius: 0px; border-bottom-left-radius: 10px; border-bottom-right-radius: 10px; top: -1px; }"
                "QTabBar { background-color: #4B5563; }"
                "QTabBar::tab { color: #FFFFFF; background-color: #4B5563; border: 1px solid #6B7280; border-bottom: none; border-top-left-radius: 8px; border-top-right-radius: 8px; padding: 6px 12px; margin-right: 2px; }"
                "QTabBar::tab:selected { background-color: #4B5563; color: #FFFFFF; }"
                "QTabBar::tab:!selected { background-color: #374151; color: #D1D5DB; }"
                "QScrollArea { background-color: #4B5563; border: none; }"
                "QGroupBox { color: #FFFFFF; background-color: #60697D; border: 1px solid #6B7280; border-radius: 10px; margin-top: 10px; padding: 10px; }"
                "QGroupBox::title { color: #FFFFFF; subcontrol-origin: margin; left: 8px; padding: 0 4px; }"
                "QLabel { color: #FFFFFF; }"
                "QCheckBox { color: #FFFFFF; }"
                "QComboBox, QSpinBox, QLineEdit, QTextEdit { color: #FFFFFF; background-color: #374151; border: 1px solid #6B7280; border-radius: 6px; padding: 4px 6px; }"
                "QComboBox QAbstractItemView { color: #FFFFFF; background-color: #374151; selection-background-color: #6B7280; selection-color: #FFFFFF; border: 1px solid #6B7280; }"
                "QComboBox::drop-down { border: none; background-color: #2D3748; }"
                "QPushButton { color: #FFFFFF; background-color: #6B7280; border: 1px solid #9CA3AF; }"
                "QPushButton:hover { background-color: #9CA3AF; color: #111827; }"
            )
            if hasattr(self, "face_tab") and self.face_tab is not None and hasattr(self.face_tab, "apply_theme_style"):
                self.face_tab.apply_theme_style("dark")
            return

        self.setStyleSheet(
            "QWidget#settings_root { background-color: #F3F4F6; }"
            "QWidget#tts_scroll_body { background-color: #F3F4F6; }"
            "QTabWidget { background-color: #F3F4F6; }"
            "QTabWidget::tab-bar { left: 0px; }"
            "QTabWidget::pane { background-color: #F3F4F6; border: 1px solid #D1D5DB; border-top-left-radius: 0px; border-top-right-radius: 0px; border-bottom-left-radius: 10px; border-bottom-right-radius: 10px; top: -1px; }"
            "QTabBar { background-color: #F3F4F6; }"
            "QTabBar::tab { color: #111827; background-color: #F3F4F6; border: 1px solid #D1D5DB; border-bottom: none; border-top-left-radius: 8px; border-top-right-radius: 8px; padding: 6px 12px; margin-right: 2px; }"
            "QTabBar::tab:selected { background-color: #F3F4F6; color: #111827; }"
            "QTabBar::tab:!selected { background-color: #E5E7EB; color: #111827; }"
            "QScrollArea { background-color: #F3F4F6; border: none; }"
            "QGroupBox { color: #111827; background-color: #F8F9FB; border: 1px solid #D1D5DB; border-radius: 10px; margin-top: 12px; padding: 10px; }"
            "QGroupBox::title { color: #111827; subcontrol-origin: margin; left: 8px; top: 0px; padding: 0 4px; }"
            "QLabel { color: #111827; }"
            "QCheckBox { color: #111827; }"
            "QComboBox, QSpinBox, QLineEdit, QTextEdit { color: #111827; background-color: #FFFFFF; border: 1px solid #D1D5DB; border-radius: 6px; padding: 4px 6px; }"
            "QComboBox QAbstractItemView { color: #111827; background-color: #FFFFFF; selection-background-color: #3B82F6; selection-color: #FFFFFF; border: 1px solid #D1D5DB; }"
            "QComboBox::drop-down { border: none; background-color: #FFFFFF; }"
            "QPushButton { color: #111827; background-color: #E5E7EB; border: 1px solid #D1D5DB; }"
            "QPushButton:hover { background-color: #D1D5DB; color: #111827; }"
        )
        if hasattr(self, "face_tab") and self.face_tab is not None and hasattr(self.face_tab, "apply_theme_style"):
            self.face_tab.apply_theme_style("light")
