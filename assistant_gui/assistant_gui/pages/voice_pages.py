from __future__ import annotations

import importlib
import os
import re
import shutil
import subprocess
import tempfile
import threading
import time
from pathlib import Path

from PySide6.QtCore import QThread, Signal, QTimer
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QTextEdit,
    QPushButton,
    QButtonGroup,
    QGroupBox,
    QComboBox,
    QCheckBox,
)

try:
    from assistant_gui.styles import themed_text_panel_style
except ModuleNotFoundError:
    from styles import themed_text_panel_style


class SpeechRecognitionWorker(QThread):
    """마이크 입력을 1회 녹음해 STT 결과를 반환하는 워커 스레드."""

    status_changed = Signal(str)
    recognized = Signal(str)
    failed = Signal(str)

    def __init__(self, *, language: str = "ko-KR", record_seconds: int = 6, parent=None):
        super().__init__(parent)
        self.language = language
        self.record_seconds = max(2, int(record_seconds))

    def run(self) -> None:
        try:
            sr = importlib.import_module("speech_recognition")
        except Exception:
            self.failed.emit("speech_recognition 패키지가 없어 음성 인식을 실행할 수 없습니다.")
            return
        recognizer = sr.Recognizer()

        mic_error = ""
        if hasattr(sr, "Microphone"):
            try:
                with sr.Microphone(sample_rate=16000) as source:
                    recognizer.dynamic_energy_threshold = True
                    recognizer.pause_threshold = 0.6
                    recognizer.non_speaking_duration = 0.3
                    recognizer.adjust_for_ambient_noise(source, duration=0.3)
                    self.status_changed.emit("마이크 대기 중... (실시간 구간 감지)")
                    audio_data = recognizer.listen(
                        source,
                        timeout=max(2, min(8, self.record_seconds)),
                        phrase_time_limit=self.record_seconds,
                    )

                self.status_changed.emit("음성 인식 처리 중...")
                text = recognizer.recognize_google(audio_data, language=self.language)
                self.recognized.emit(text)
                return
            except Exception as exc:
                mic_error = str(exc)

        if shutil.which("arecord") is None:
            msg = "arecord가 없어 마이크 녹음을 시작할 수 없습니다."
            if mic_error:
                msg = f"{msg} (microphone fallback 실패: {mic_error})"
            self.failed.emit(msg)
            return

        temp_path = ""
        try:
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                temp_path = tmp.name

            self.status_changed.emit(f"마이크 녹음 중... (최대 {self.record_seconds}초)")
            record_cmd = [
                "arecord",
                "-q",
                "-d",
                str(self.record_seconds),
                "-f",
                "S16_LE",
                "-r",
                "16000",
                "-c",
                "1",
                temp_path,
            ]
            record_timeout = max(8, self.record_seconds + 4)
            record_result = subprocess.run(record_cmd, capture_output=True, text=True, timeout=record_timeout)
            if record_result.returncode != 0:
                msg = (record_result.stderr or record_result.stdout or "녹음 실패").strip()
                self.failed.emit(f"마이크 녹음 실패: {msg}")
                return

            self.status_changed.emit("음성 인식 처리 중...")
            with sr.AudioFile(temp_path) as source:
                audio_data = recognizer.record(source)
            text = recognizer.recognize_google(audio_data, language=self.language)
            self.recognized.emit(text)
        except subprocess.TimeoutExpired:
            self.failed.emit("녹음 시간이 초과되었습니다.")
        except Exception as exc:
            self.failed.emit(f"음성 인식 실패: {exc}")
        finally:
            if temp_path and os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except OSError:
                    pass


class VoiceTestPage(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self._worker = None
        self._wakeword_test_stage = "wakeword"
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 20, 40, 20)

        title = QLabel("🎤 음성 인식 테스트 창")
        title.setProperty("class", "TitleText")
        layout.addWidget(title)

        info_lbl = QLabel("전 화면 공통 호출어 인식은 백그라운드에서 상시 동작합니다. 이 페이지 버튼은 수동 단발 테스트용입니다.")
        info_lbl.setWordWrap(True)
        info_lbl.setProperty("class", "SubText")
        layout.addWidget(info_lbl)

        status_row = QHBoxLayout()
        self.network_state_lbl = QLabel("📶 네트워크 확인 중...")
        self.network_state_lbl.setProperty("class", "SubText")
        self.mic_state_lbl = QLabel("🎙️ 마이크 확인 중...")
        self.mic_state_lbl.setProperty("class", "SubText")
        status_row.addWidget(self.network_state_lbl)
        status_row.addWidget(self.mic_state_lbl)
        status_row.addStretch()
        layout.addLayout(status_row)

        self.log_area = QTextEdit()
        self.log_area.setReadOnly(True)
        self.log_area.setText("시스템: 마이크 대기 중...\n")
        self._apply_log_area_style()
        layout.addWidget(self.log_area, stretch=1)

        simulation_row = QHBoxLayout()
        simulation_row.setSpacing(8)
        self.wakeword_mode_check = QCheckBox("호출어 대화 테스트")
        self.wakeword_mode_check.setChecked(True)
        self.wakeword_mode_check.toggled.connect(self._on_wakeword_mode_toggled)
        self.wakeword_stage_lbl = QLabel("현재 단계: 호출어 대기")
        self.wakeword_stage_lbl.setProperty("class", "SubText")
        simulation_label = QLabel("인식된 음성으로 명령 시뮬레이션 출력")
        simulation_label.setProperty("class", "SubText")
        self.simulation_toggle_btn = QPushButton("ON")
        self.simulation_toggle_btn.setCheckable(True)
        self.simulation_toggle_btn.setChecked(True)
        self.simulation_toggle_btn.setFixedWidth(78)
        self.simulation_toggle_btn.setStyleSheet(
            "QPushButton { background-color: #E5E7EB; color: #374151; border-radius: 14px; padding: 6px 10px; }"
            "QPushButton:checked { background-color: #10B981; color: #FFFFFF; }"
        )
        self.simulation_toggle_btn.toggled.connect(self._on_simulation_toggled)
        simulation_row.addWidget(self.wakeword_mode_check)
        simulation_row.addWidget(self.wakeword_stage_lbl)
        simulation_row.addWidget(self.simulation_toggle_btn)
        simulation_row.addWidget(simulation_label)
        simulation_row.addStretch()
        layout.addLayout(simulation_row)

        btn_layout = QHBoxLayout()
        self.live_test_btn = QPushButton("🎤 수동 재시작")
        self.live_test_btn.setProperty("class", "PrimaryBtn")
        self.live_test_btn.clicked.connect(self._run_live_recognition)

        clear_btn = QPushButton("로그 지우기")
        clear_btn.clicked.connect(self.log_area.clear)

        tts_test_btn = QPushButton("🔊 TTS 테스트")
        tts_test_btn.setProperty("class", "PrimaryBtn")
        tts_test_btn.clicked.connect(lambda: self.main_window.switch_page(11, manual=True))

        btn_layout.addWidget(self.live_test_btn)
        btn_layout.addWidget(clear_btn)
        btn_layout.addWidget(tts_test_btn)
        layout.addLayout(btn_layout)

        self._sync_capability_labels()
        self._update_wakeword_stage_ui()

    def _apply_log_area_style(self) -> None:
        theme = getattr(self.main_window, "_theme_mode", "light") if self.main_window is not None else "light"
        self.log_area.setStyleSheet(themed_text_panel_style(theme, font_size=16))

    def showEvent(self, event):
        super().showEvent(event)
        self._apply_log_area_style()

    def _sync_capability_labels(self) -> None:
        network_ok = self.main_window.is_network_available()
        mic_ok = self.main_window.is_microphone_available()
        self.network_state_lbl.setText("📶 네트워크 연결됨" if network_ok else "📶 네트워크 없음")
        self.mic_state_lbl.setText("🎙️ 마이크 인식됨" if mic_ok else "🎙️ 마이크 없음")

    def _run_live_recognition(self) -> None:
        self._sync_capability_labels()
        if not self.main_window.is_microphone_available():
            self.log_area.append("시스템: 마이크가 없어 테스트를 시작할 수 없습니다.")
            return
        if not self.main_window.is_network_available():
            self.log_area.append("시스템: 네트워크가 없어 온라인 STT를 실행할 수 없습니다.")
            return

        if self._worker is not None:
            return

        record_seconds = 10 if self._use_wakeword_mode() and self._wakeword_test_stage == "wakeword" else 6
        if self._use_wakeword_mode():
            label = "호출어" if self._wakeword_test_stage == "wakeword" else "명령"
            self.log_area.append(f"시스템: {label} 인식을 시작합니다.")
        else:
            self.log_area.append("시스템: 마이크 인식 테스트를 시작합니다.")

        self._worker = SpeechRecognitionWorker(language="ko-KR", record_seconds=record_seconds, parent=self)
        self._worker.status_changed.connect(lambda msg: self.log_area.append(f"시스템: {msg}"))
        self._worker.recognized.connect(self._on_recognized)
        self._worker.failed.connect(self._on_failed)
        self._worker.finished.connect(self._on_worker_finished)
        self._worker.start()

    def _on_recognized(self, text: str) -> None:
        self.log_area.append(f"User: {text}")
        self.log_area.append("시스템: 음성 인식이 완료되었습니다.")
        if self._use_wakeword_mode() and self.main_window is not None:
            self._handle_wakeword_test_recognized(text)
            return
        if self.simulation_toggle_btn.isChecked():
            self.log_area.append(f"시스템: {self._build_simulation_response(text)}")

    def _handle_wakeword_test_recognized(self, text: str) -> None:
        if self._wakeword_test_stage == "wakeword":
            if not self.main_window._is_wakeword_detected(text):
                self.log_area.append("시스템: 호출어가 아닙니다. 다시 불러주세요.")
                self._wakeword_test_stage = "wakeword"
                self._update_wakeword_stage_ui()
                return

            inline_command = self.main_window._extract_command_after_wakeword(text)
            if inline_command:
                self.log_area.append("시스템: 호출어 뒤의 명령은 무시하고, 다음 턴에서 명령만 듣습니다.")

            wakeword_prompt = self.main_window.render_tts_scenario("wakeword_prompt")
            self.log_area.append(f"시스템: {wakeword_prompt}")
            ok, message = self.main_window.speak_text(wakeword_prompt, target="pc")
            if not ok:
                self.log_area.append(f"시스템: 호출어 응답 TTS 실패 - {message}")

            self._wakeword_test_stage = "command"
            self._update_wakeword_stage_ui()
            QTimer.singleShot(self._estimate_tts_delay_ms(wakeword_prompt if ok else ""), self._begin_command_followup)
            return

        response = self._build_simulation_response(text)
        self.log_area.append(f"시스템: {response}")
        ok, message = self.main_window.speak_text(response, target="pc")
        if not ok:
            self.log_area.append(f"시스템: 명령 응답 TTS 실패 - {message}")
        self._wakeword_test_stage = "wakeword"
        self._update_wakeword_stage_ui()

    def _on_simulation_toggled(self, checked: bool) -> None:
        self.simulation_toggle_btn.setText("ON" if checked else "OFF")
        if checked:
            self.log_area.append("시스템: 명령 시뮬레이션 출력이 활성화되었습니다.")
        else:
            self.log_area.append("시스템: 명령 시뮬레이션 출력이 비활성화되었습니다.")

    def _on_wakeword_mode_toggled(self, checked: bool) -> None:
        self._wakeword_test_stage = "wakeword"
        self._update_wakeword_stage_ui()
        if checked:
            self.log_area.append("시스템: 호출어 대화 테스트 모드가 활성화되었습니다.")
        else:
            self.log_area.append("시스템: 일반 음성 인식 테스트 모드로 전환되었습니다.")

    def _build_simulation_response(self, text: str) -> str:
        if self.main_window is not None and hasattr(self.main_window, "build_situation_response_text"):
            return self.main_window.build_situation_response_text(text)

        normalized = text.replace(" ", "")
        if normalized in {"옴니", "옴니야"}:
            return "호출어를 인식했습니다. 뒤에 명령을 말씀해주세요."
        if "일정" in normalized:
            return "일정 조회 요청으로 인식했습니다. status_brief 미션을 등록합니다."
        if "알람맞춰줘" in normalized or "알람설정" in normalized or "알람추가" in normalized:
            return "알람 설정 요청으로 인식했습니다. status_brief 미션을 등록합니다."
        if "알람" in normalized:
            return "알람 조회 요청으로 인식했습니다. status_brief 미션을 등록합니다."
        if "복약" in normalized or "약확인" in normalized or "약체크" in normalized:
            return "복약 조회 요청으로 인식했습니다. status_brief 미션을 등록합니다."
        if "취소" in normalized or "중지" in normalized or "멈춰" in normalized:
            return "취소 요청으로 인식했습니다. status_brief 미션을 등록합니다."
        if "날씨" in normalized:
            return "날씨 안내 요청으로 인식했습니다. weather_tts 미션을 등록합니다."
        if "어디가" in normalized or "어디로가" in normalized:
            return "상태 질의 요청으로 인식했습니다. 현재 목적지 안내를 시도합니다."
        if "우편" in normalized or "배달" in normalized or "배송" in normalized or "전달" in normalized:
            return "배달/배송 요청으로 인식했습니다. delivery 미션을 등록합니다."
        if "가줘" in normalized or "로가" in normalized or "안내해줘" in normalized:
            return "이동 요청으로 인식했습니다. call 미션을 등록합니다."
        return "요청을 이해하지 못했습니다. 첫 번째 유효 명령을 다시 말씀해주세요."

    def _on_failed(self, message: str) -> None:
        self.log_area.append(f"시스템: {message}")
        if self._use_wakeword_mode() and self._wakeword_test_stage == "command":
            self.log_area.append("시스템: 명령 대기 상태를 유지합니다. 수동 테스트를 다시 실행할 수 있습니다.")
            return

    def _on_worker_finished(self) -> None:
        self._worker = None

    def _begin_command_followup(self) -> None:
        if not self._use_wakeword_mode():
            return
        if self._wakeword_test_stage != "command":
            return
        if self._worker is not None:
            return
        self.log_area.append("시스템: 이제 명령을 말씀해주세요.")
        self._run_live_recognition()

    def _update_wakeword_stage_ui(self) -> None:
        if not self._use_wakeword_mode():
            self.wakeword_stage_lbl.setText("현재 단계: 일반 인식 상시 대기")
            self.live_test_btn.setText("🎤 수동 재시작")
            return

        if self._wakeword_test_stage == "wakeword":
            self.wakeword_stage_lbl.setText("현재 단계: 호출어 상시 대기")
            self.live_test_btn.setText("🎤 수동 재시작")
        else:
            self.wakeword_stage_lbl.setText("현재 단계: 명령 상시 대기")
            self.live_test_btn.setText("🎤 수동 재시작")

    def _use_wakeword_mode(self) -> bool:
        return bool(self.wakeword_mode_check.isChecked())

    @staticmethod
    def _estimate_tts_delay_ms(text: str) -> int:
        if not text:
            return 300
        return max(1200, min(5500, 650 + (len(text) * 85)))


class TtsTestPage(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self._output_mode = "pc"

        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 20, 40, 20)
        layout.setSpacing(12)

        title = QLabel("🔊 TTS 테스트 창")
        title.setProperty("class", "TitleText")
        layout.addWidget(title)

        self.input_area = QTextEdit()
        self.input_area.setPlaceholderText("여기에 TTS로 출력할 문장을 입력하세요.")
        layout.addWidget(self.input_area, stretch=1)

        toggle_layout = QHBoxLayout()
        toggle_label = QLabel("출력 대상")
        toggle_label.setProperty("class", "SubText")

        self.pc_btn = QPushButton("💻 PC")
        self.robot_btn = QPushButton("🤖 로봇")
        self.pc_btn.setCheckable(True)
        self.robot_btn.setCheckable(True)

        self.mode_group = QButtonGroup(self)
        self.mode_group.setExclusive(True)
        self.mode_group.addButton(self.pc_btn)
        self.mode_group.addButton(self.robot_btn)

        self.pc_btn.clicked.connect(lambda: self._set_mode("pc"))
        self.robot_btn.clicked.connect(lambda: self._set_mode("robot"))

        toggle_layout.addWidget(toggle_label)
        toggle_layout.addWidget(self.pc_btn)
        toggle_layout.addWidget(self.robot_btn)
        toggle_layout.addStretch()
        layout.addLayout(toggle_layout)

        combo_style = (
            "QComboBox {"
            " color: #FFFFFF; background-color: #1F2937; border: 1px solid #374151;"
            " border-radius: 6px; padding: 4px 8px; }"
            "QComboBox QAbstractItemView { color: #FFFFFF; background-color: #111827;"
            " selection-background-color: #2563EB; selection-color: #FFFFFF; border: 1px solid #374151; }"
            "QComboBox::drop-down { border: none; background-color: #1F2937; }"
        )

        compare_group = QGroupBox("백엔드 비교 테스트")
        compare_layout = QVBoxLayout(compare_group)
        compare_layout.setSpacing(10)

        self._sentence_presets = {
            "짧은 문장": "안녕하세요. 테스트 중입니다.",
            "긴 문장": "안녕하세요. 이 문장은 여러 TTS 백엔드의 자연스러움과 속도, 발음 품질을 비교하기 위한 긴 테스트 문장입니다.",
            "숫자 포함": "오늘은 2026년 4월 1일이고 배터리는 82퍼센트입니다.",
            "영어 혼합": "오늘 meeting은 오후 3시에 Room A에서 시작합니다.",
            "대화체": "지금 바로 회의실 앞으로 안내해드릴게요. 천천히 저를 따라오세요.",
        }

        preset_layout = QHBoxLayout()
        preset_label = QLabel("기본 문장")
        preset_label.setProperty("class", "SubText")
        self.sentence_preset_combo = QComboBox()
        self.sentence_preset_combo.addItems(list(self._sentence_presets.keys()))
        self.sentence_preset_combo.setStyleSheet(combo_style)
        self.sentence_preset_combo.setFixedWidth(160)
        apply_preset_btn = QPushButton("문장 넣기")
        apply_preset_btn.clicked.connect(self._apply_sentence_preset)
        preset_layout.addWidget(preset_label)
        preset_layout.addWidget(self.sentence_preset_combo)
        preset_layout.addWidget(apply_preset_btn)
        preset_layout.addStretch()
        compare_layout.addLayout(preset_layout)

        profile_layout = QHBoxLayout()
        profile_label = QLabel("공통 프로필")
        profile_label.setProperty("class", "SubText")
        self.gender_combo = QComboBox()
        self.gender_combo.addItems(["여성", "남성"])
        self.gender_combo.setCurrentText("여성")
        self.gender_combo.setFixedWidth(90)
        self.gender_combo.setStyleSheet(combo_style)

        self.language_combo = QComboBox()
        self.language_combo.addItems(["한국어(ko-KR)", "영어(en-US)", "일본어(ja-JP)"])
        self.language_combo.setCurrentText("한국어(ko-KR)")
        self.language_combo.setFixedWidth(140)
        self.language_combo.setStyleSheet(combo_style)

        self.quality_combo = QComboBox()
        self.quality_combo.addItems(["고음질", "균형형", "저지연"])
        self.quality_combo.setCurrentText("고음질")
        self.quality_combo.setFixedWidth(90)
        self.quality_combo.setStyleSheet(combo_style)

        self.playback_command_combo = QComboBox()
        self.playback_command_combo.addItems(["gst-play-1.0", "ffplay", "aplay"])
        self.playback_command_combo.setCurrentText("gst-play-1.0")
        self.playback_command_combo.setFixedWidth(140)
        self.playback_command_combo.setStyleSheet(combo_style)

        profile_layout.addWidget(profile_label)
        profile_layout.addWidget(self.gender_combo)
        profile_layout.addWidget(self.language_combo)
        profile_layout.addWidget(self.quality_combo)
        profile_layout.addWidget(QLabel("재생기"))
        profile_layout.addWidget(self.playback_command_combo)
        profile_layout.addStretch()
        compare_layout.addLayout(profile_layout)

        backend_layout = QHBoxLayout()
        backend_label = QLabel("백엔드 선택")
        backend_label.setProperty("class", "SubText")
        self.edge_checkbox = QCheckBox("Edge TTS")
        self.speech_checkbox = QCheckBox("Speech Dispatcher")
        self.elevenlabs_checkbox = QCheckBox("ElevenLabs")
        self.cartesia_checkbox = QCheckBox("Cartesia")
        self.edge_checkbox.setChecked(True)
        self.speech_checkbox.setChecked(True)
        self.elevenlabs_checkbox.toggled.connect(self._refresh_backend_settings_visibility)
        self.cartesia_checkbox.toggled.connect(self._refresh_backend_settings_visibility)
        backend_layout.addWidget(backend_label)
        backend_layout.addWidget(self.edge_checkbox)
        backend_layout.addWidget(self.speech_checkbox)
        backend_layout.addWidget(self.elevenlabs_checkbox)
        backend_layout.addWidget(self.cartesia_checkbox)
        backend_layout.addStretch()
        compare_layout.addLayout(backend_layout)

        self.elevenlabs_settings_group = QGroupBox("ElevenLabs 설정")
        elevenlabs_layout = QHBoxLayout(self.elevenlabs_settings_group)
        elevenlabs_layout.addWidget(QLabel("Voice"))
        self.elevenlabs_voice_combo = QComboBox()
        self.elevenlabs_voice_combo.addItems([
            "여성 밝은 (Jessica)",
            "여성 차분 (Sarah)",
            "남성 기본 (Adam)",
            "환경변수 (ELEVENLABS_VOICE_ID)",
        ])
        self.elevenlabs_voice_combo.setCurrentIndex(0)
        self.elevenlabs_voice_combo.setStyleSheet(combo_style)
        self.elevenlabs_voice_combo.setFixedWidth(220)
        elevenlabs_layout.addWidget(self.elevenlabs_voice_combo)
        elevenlabs_layout.addWidget(QLabel("Model"))
        self.elevenlabs_model_combo = QComboBox()
        self.elevenlabs_model_combo.addItems(["자동", "eleven_multilingual_v2", "eleven_flash_v2_5", "eleven_turbo_v2_5"])
        self.elevenlabs_model_combo.setStyleSheet(combo_style)
        self.elevenlabs_model_combo.setFixedWidth(190)
        elevenlabs_layout.addWidget(self.elevenlabs_model_combo)
        elevenlabs_layout.addStretch()
        compare_layout.addWidget(self.elevenlabs_settings_group)

        self.cartesia_settings_group = QGroupBox("Cartesia 설정")
        cartesia_layout = QHBoxLayout(self.cartesia_settings_group)
        cartesia_layout.addWidget(QLabel("Voice"))
        self.cartesia_voice_combo = QComboBox()
        self.cartesia_voice_combo.addItems([
            "여성 기본 (Haley)",
            "여성 밝은 (Mindy)",
            "남성 기본 (Donny)",
            "환경변수 (CARTESIA_VOICE_ID)",
        ])
        self.cartesia_voice_combo.setCurrentIndex(0)
        self.cartesia_voice_combo.setStyleSheet(combo_style)
        self.cartesia_voice_combo.setFixedWidth(220)
        cartesia_layout.addWidget(self.cartesia_voice_combo)
        cartesia_layout.addWidget(QLabel("Model"))
        self.cartesia_model_combo = QComboBox()
        self.cartesia_model_combo.addItems(["자동", "sonic-3", "sonic-2"])
        self.cartesia_model_combo.setStyleSheet(combo_style)
        self.cartesia_model_combo.setFixedWidth(190)
        cartesia_layout.addWidget(self.cartesia_model_combo)
        cartesia_layout.addStretch()
        compare_layout.addWidget(self.cartesia_settings_group)

        compare_btn_layout = QHBoxLayout()
        compare_btn = QPushButton("선택한 모델 모두 테스트")
        compare_btn.setProperty("class", "PrimaryBtn")
        compare_btn.clicked.connect(self._on_compare_backends)
        compare_btn_layout.addWidget(compare_btn)
        compare_btn_layout.addStretch()
        compare_layout.addLayout(compare_btn_layout)

        layout.addWidget(compare_group)

        self.status_log = QTextEdit()
        self.status_log.setReadOnly(True)
        self.status_log.setFixedHeight(180)
        layout.addWidget(self.status_log)

        btn_layout = QHBoxLayout()
        speak_btn = QPushButton("말하기")
        speak_btn.setProperty("class", "PrimaryBtn")
        speak_btn.clicked.connect(self._on_speak)

        clear_btn = QPushButton("입력/로그 지우기")
        clear_btn.clicked.connect(self._on_clear)

        back_btn = QPushButton("◀ 음성 테스트로")
        back_btn.clicked.connect(lambda: self.main_window.switch_page(9, manual=True))

        btn_layout.addWidget(speak_btn)
        btn_layout.addWidget(clear_btn)
        btn_layout.addWidget(back_btn)
        layout.addLayout(btn_layout)

        self._apply_text_area_style()
        self._set_mode("pc")
        self._refresh_backend_settings_visibility()
        self._log("시스템: TTS 테스트 준비 완료")
        self._log("시스템: 백엔드 비교 테스트는 현재 GUI 실행 장치 기준으로 순차 실행됩니다.")

    def _apply_text_area_style(self) -> None:
        theme = getattr(self.main_window, "_theme_mode", "light") if self.main_window is not None else "light"
        shared_style = themed_text_panel_style(theme, font_size=16)
        self.input_area.setStyleSheet(shared_style)
        self.status_log.setStyleSheet(shared_style)

    def showEvent(self, event):
        super().showEvent(event)
        self._apply_text_area_style()

    def _set_mode(self, mode):
        self._output_mode = mode
        self.pc_btn.blockSignals(True)
        self.robot_btn.blockSignals(True)
        self.pc_btn.setChecked(mode == "pc")
        self.robot_btn.setChecked(mode == "robot")
        self.pc_btn.blockSignals(False)
        self.robot_btn.blockSignals(False)

        self.pc_btn.setProperty("class", "PrimaryBtn" if mode == "pc" else "")
        self.robot_btn.setProperty("class", "PrimaryBtn" if mode == "robot" else "")
        self.pc_btn.style().unpolish(self.pc_btn)
        self.pc_btn.style().polish(self.pc_btn)
        self.robot_btn.style().unpolish(self.robot_btn)
        self.robot_btn.style().polish(self.robot_btn)

        target = "PC" if mode == "pc" else "로봇"
        self._log(f"시스템: 출력 대상을 {target}로 설정")

    def _on_clear(self):
        self.input_area.clear()
        self.status_log.clear()
        self._log("시스템: 입력/로그 초기화 완료")

    def _on_speak(self):
        text = self.input_area.toPlainText().strip()
        if not text:
            self._log("에러: 출력할 문장을 입력해주세요.")
            return

        if self._output_mode == "pc":
            if self.main_window is not None and hasattr(self.main_window, "speak_text"):
                ok, msg = self.main_window.speak_text(text, target="pc")
            else:
                ok = self._speak_on_pc(text)
                msg = "ok" if ok else "PC TTS 실행에 실패했습니다. (spd-say/espeak-ng 확인 필요)"
            if ok:
                self._log(f"PC 출력: {text}")
            else:
                self._log(f"에러: {msg}")
        else:
            ok, msg = self._publish_to_robot(text)
            if ok:
                self._log(f"로봇 출력 요청: {text}")
            else:
                self._log(f"에러: 로봇 출력 실패 - {msg}")

    def _apply_sentence_preset(self):
        sentence = self._sentence_presets.get(self.sentence_preset_combo.currentText(), "")
        if sentence:
            self.input_area.setPlainText(sentence)
            self._log(f"시스템: 기본 문장 적용 - {self.sentence_preset_combo.currentText()}")

    def _refresh_backend_settings_visibility(self):
        self.elevenlabs_settings_group.setVisible(self.elevenlabs_checkbox.isChecked())
        self.cartesia_settings_group.setVisible(self.cartesia_checkbox.isChecked())

    def _resolve_elevenlabs_voice_id(self):
        selected = self.elevenlabs_voice_combo.currentText()
        if selected.startswith("여성 밝은"):
            return "cgSgspJ2msm6clMCkdW9"
        if selected.startswith("여성 차분"):
            return "EXAVITQu4vr4xnSDxMaL"
        if selected.startswith("기본 남성"):
            return "pNInz6obpgDQGcFmaJgB"
        return os.getenv("ELEVENLABS_VOICE_ID", "").strip()

    def _resolve_cartesia_voice_id(self):
        selected = self.cartesia_voice_combo.currentText()
        if selected.startswith("여성 기본"):
            return "cec7cae1-ac8b-4a59-9eac-ec48366f37ae"
        if selected.startswith("여성 밝은"):
            return "d6905573-8e91-4e32-b103-fd4d1205cd87"
        if selected.startswith("남성 기본"):
            return "d709a7e8-9495-4247-aef0-01b3207d11bf"
        return os.getenv("CARTESIA_VOICE_ID", "").strip()

    def _resolve_smoke_profile(self, backend, gender, language_label, quality):
        lang_locale = "ko-KR"
        if "en-US" in language_label:
            lang_locale = "en-US"
        elif "ja-JP" in language_label:
            lang_locale = "ja-JP"

        if backend == "edge_tts":
            edge_voice_map = {
                "ko-KR": {"여성": "ko-KR-SunHiNeural", "남성": "ko-KR-InJoonNeural"},
                "en-US": {"여성": "en-US-AriaNeural", "남성": "en-US-GuyNeural"},
                "ja-JP": {"여성": "ja-JP-NanamiNeural", "남성": "ja-JP-KeitaNeural"},
            }
            voice_name = edge_voice_map.get(lang_locale, edge_voice_map["ko-KR"]).get(gender, "ko-KR-SunHiNeural")
            language = lang_locale.split("-")[0]
            return {
                "backend": backend,
                "display": "Edge TTS",
                "voice": voice_name,
                "model": quality,
                "language": language,
            }

        if backend == "speech_dispatcher":
            voice_name = "female1" if gender == "여성" else "male1"
            return {
                "backend": backend,
                "display": "Speech Dispatcher",
                "voice": voice_name,
                "model": quality,
                "language": "",
            }

        if backend == "elevenlabs":
            model_name = self.elevenlabs_model_combo.currentText().strip()
            if model_name == "자동":
                quality_models = {
                    "고음질": "eleven_multilingual_v2",
                    "균형형": "eleven_turbo_v2_5",
                    "저지연": "eleven_flash_v2_5",
                }
                model_name = quality_models.get(quality, "eleven_multilingual_v2")
            return {
                "backend": backend,
                "display": "ElevenLabs",
                "voice": self._resolve_elevenlabs_voice_id(),
                "model": model_name,
                "language": lang_locale.split("-")[0],
            }

        if backend == "cartesia":
            model_name = self.cartesia_model_combo.currentText().strip()
            if model_name == "자동":
                quality_models = {
                    "고음질": "sonic-3",
                    "균형형": "sonic-3",
                    "저지연": "sonic-2",
                }
                model_name = quality_models.get(quality, "sonic-3")
            return {
                "backend": backend,
                "display": "Cartesia",
                "voice": self._resolve_cartesia_voice_id(),
                "model": model_name,
                "language": lang_locale.split("-")[0],
            }

        return {
            "backend": "mock",
            "display": "Mock",
            "voice": "default",
            "model": quality,
            "language": "",
        }

    def _selected_backend_specs(self):
        gender = self.gender_combo.currentText().strip()
        language_label = self.language_combo.currentText().strip()
        quality = self.quality_combo.currentText().strip()
        specs = []
        if self.edge_checkbox.isChecked():
            specs.append(self._resolve_smoke_profile("edge_tts", gender, language_label, quality))
        if self.speech_checkbox.isChecked():
            specs.append(self._resolve_smoke_profile("speech_dispatcher", gender, language_label, quality))
        if self.elevenlabs_checkbox.isChecked():
            specs.append(self._resolve_smoke_profile("elevenlabs", gender, language_label, quality))
        if self.cartesia_checkbox.isChecked():
            specs.append(self._resolve_smoke_profile("cartesia", gender, language_label, quality))
        return specs

    def _on_compare_backends(self):
        text = self.input_area.toPlainText().strip()
        if not text:
            self._log("에러: 테스트 문장을 입력해주세요.")
            return

        specs = self._selected_backend_specs()
        if not specs:
            self._log("에러: 비교할 백엔드를 하나 이상 선택해주세요.")
            return

        for spec in specs:
            if spec["backend"] in {"elevenlabs", "cartesia"} and not spec["voice"]:
                env = "ELEVENLABS_VOICE_ID" if spec["backend"] == "elevenlabs" else "CARTESIA_VOICE_ID"
                self._log(f"에러: {spec['display']} voice_id가 없습니다. 환경변수 {env}를 설정해주세요.")
                return

        self._log(f"시스템: {len(specs)}개 백엔드 비교 테스트 시작")
        for spec in specs:
            started_at = time.monotonic()
            ok, msg = self._run_local_tts_smoke(text, spec)
            elapsed_ms = int((time.monotonic() - started_at) * 1000)
            status = "성공" if ok else "실패"
            self._log(
                f"[{spec['display']}] {status} | {elapsed_ms}ms | "
                f"voice={spec['voice'] or '-'} | model={spec['model'] or '-'} | {msg}"
            )

    def _speak_on_pc(self, text):
        cmd = None
        if shutil.which("spd-say"):
            cmd = ["spd-say", text]
        elif shutil.which("espeak-ng"):
            cmd = ["espeak-ng", "-v", "ko", text]

        if not cmd:
            return False

        try:
            subprocess.Popen(cmd)
            return True
        except Exception:
            return False

    def _publish_to_robot(self, text):
        if self.main_window is not None and hasattr(self.main_window, "publish_tts_to_robot"):
            return self.main_window.publish_tts_to_robot(text)

        if not shutil.which("ros2"):
            return False, "ros2 CLI를 찾을 수 없습니다."

        safe_text = text.replace("\\", "\\\\").replace('"', '\\"')
        msg_arg = f'{{data: "{safe_text}"}}'
        cmd = [
            "ros2", "topic", "pub", "--once",
            "-w", "1", "--max-wait-time-secs", "1",
            "/assistant/speak", "std_msgs/msg/String", msg_arg,
        ]

        ros_env = os.environ.copy()
        ros_env.setdefault("ROS_DOMAIN_ID", "142")
        ros_env.setdefault("ROS_LOCALHOST_ONLY", "0")
        ros_env.setdefault("RMW_IMPLEMENTATION", "rmw_fastrtps_cpp")
        ros_env.setdefault("ROS_AUTOMATIC_DISCOVERY_RANGE", "SUBNET")
        robot_peer_ip = (
            ros_env.get("ASSISTANT_ROBOT_IP", "").strip()
            or ros_env.get("ASSISTANT_TURTLEBOT_IP", "").strip()
            or "192.168.96.23"
        )
        if robot_peer_ip:
            ros_env["ROS_STATIC_PEERS"] = robot_peer_ip

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=6, env=ros_env)
            if result.returncode != 0:
                err = (result.stderr.strip() or result.stdout.strip() or "ros2 topic pub 실패")
                if "Timed out waiting for subscribers" in err:
                    err = "구독자 없음: 로봇 tts_node 미실행 또는 ROS_DOMAIN_ID/RMW 불일치"
                return False, err
            return True, "ok"
        except Exception as exc:
            return False, str(exc)

    def _run_local_tts_smoke(self, text, spec):
        if not shutil.which("ros2"):
            return False, "ros2 CLI를 찾을 수 없습니다."

        playback_command = self.playback_command_combo.currentText().strip() or "gst-play-1.0"
        cmd = [
            "ros2", "run", "assistant_audio", "tts_smoke_test",
            "--backend", spec["backend"],
            "--text", text,
            "--voice-name", spec["voice"],
            "--language", spec["language"],
            "--fallback-voice-name", "female1",
            "--playback-command", playback_command,
        ]

        if spec["backend"] == "elevenlabs":
            cmd.extend(["--elevenlabs-voice-id", spec["voice"], "--elevenlabs-model-id", spec["model"]])
        if spec["backend"] == "cartesia":
            cmd.extend(["--cartesia-voice-id", spec["voice"], "--cartesia-model-id", spec["model"]])

        ros_env = os.environ.copy()
        ros_env.setdefault("ROS_DOMAIN_ID", "142")
        ros_env.setdefault("ROS_LOCALHOST_ONLY", "0")
        ros_env.setdefault("RMW_IMPLEMENTATION", "rmw_fastrtps_cpp")

        try:
            setup_script = self._find_workspace_setup_script()
            if setup_script:
                cmd_str = subprocess.list2cmdline(cmd)
                sourced_cmd = f"source '{setup_script}' && {cmd_str}"
                result = subprocess.run(
                    ["bash", "-lc", sourced_cmd],
                    capture_output=True,
                    text=True,
                    timeout=25,
                    env=ros_env,
                )
            else:
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=20, env=ros_env)

            if result.returncode != 0:
                err = result.stderr.strip() or result.stdout.strip() or "tts_smoke_test 실패"
                if "Package 'assistant_audio' not found" in err:
                    return False, "assistant_audio 패키지를 찾지 못했습니다. colcon build 후 install/setup.bash가 필요합니다."
                return False, err
            return True, result.stdout.strip() or "ok"
        except Exception as exc:
            return False, str(exc)

    @staticmethod
    def _find_workspace_setup_script() -> str | None:
        here = Path(__file__).resolve()
        for parent in here.parents:
            candidate = parent / "install" / "setup.bash"
            if candidate.exists():
                return str(candidate)
        return None

    def _log(self, text):
        self.status_log.append(text)
