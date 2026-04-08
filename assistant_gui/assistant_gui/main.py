"""OmniMate GUI 애플리케이션 메인 진입점.

역할:
- UI 초기화 및 페이지 라우팅
- 음성/날씨/배터리 엔진 연결
- ROS 브리지 상태 반영
"""

import re
import sys
import os
import json
import importlib
import math
import shutil
import subprocess
import tempfile
import socket
from pathlib import Path
import threading
import time
from datetime import datetime

import yaml

CURRENT_DIR = Path(__file__).resolve().parent
PACKAGE_PARENT = CURRENT_DIR.parent
ROBOT_PACKAGE_PARENT = PACKAGE_PARENT.parent / "assistant_robot"
ROBOT_NAMED_PLACE_CONFIG = ROBOT_PACKAGE_PARENT / "assistant_robot" / "config" / "named_places.yaml"
for candidate in (PACKAGE_PARENT, CURRENT_DIR, ROBOT_PACKAGE_PARENT):
    candidate_str = str(candidate)
    if candidate_str not in sys.path:
        sys.path.insert(0, candidate_str)

from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                               QHBoxLayout, QLabel, QPushButton, QStackedWidget,
                               QFrame)
from PySide6.QtCore import Qt, QTimer, QSettings
try:
    from assistant_gui.engines.weather_engine import WeatherEngine
    from assistant_gui.engines.schedule_manager import ScheduleManager
    from assistant_gui.engines.alarm_manager import AlarmManager
    from assistant_gui.engines.ocr_engine import OcrEngine
    from assistant_gui.engines.battery_engine import BatteryEngine
    from assistant_gui.engines.pose_engine import PoseEngine
    from assistant_gui.integrations.ros_state_bridge import RosStateBridge
    from assistant_gui.face.face_controller import FaceController
    from assistant_gui.face.face_page import FacePage as UnifiedFacePage
    from assistant_gui.styles import GLOBAL_STYLE, THEME_STYLES
    from assistant_gui.tts_template import render_tts_template
    from assistant_gui.pages.schedule_pages import (
        SchedulePage,
        ScheduleAddPage,
        AlarmPage,
        AlarmAddPage,
    )
    from assistant_gui.pages.voice_pages import SpeechRecognitionWorker, VoiceTestPage, TtsTestPage
    from assistant_gui.pages.weather_page import WeatherForecastPage
    from assistant_gui.pages.utility_pages import MedicationPage, MailPage, GesturePage
    from assistant_gui.pages.home_page import HomePage
    from assistant_gui.pages.settings_page import SettingsPage
    from assistant_gui.config.app_constants import TTS_SCENARIO_DEFAULTS
    from assistant_gui.engines.wakeword_runtime import (
        GUI_WAKEWORD_VARIANTS,
        GlobalWakewordController,
        extract_command_after_wakeword,
        is_wakeword_detected,
    )
    from assistant_gui.engines.voice_response_builder import build_contextual_voice_response
except ModuleNotFoundError:
    # Keep direct script execution support (python main.py)
    from engines.weather_engine import WeatherEngine
    from engines.schedule_manager import ScheduleManager
    from engines.alarm_manager import AlarmManager
    from engines.ocr_engine import OcrEngine
    from engines.battery_engine import BatteryEngine
    from engines.pose_engine import PoseEngine
    from integrations.ros_state_bridge import RosStateBridge
    from face.face_controller import FaceController
    from face.face_page import FacePage as UnifiedFacePage
    from styles import GLOBAL_STYLE, THEME_STYLES
    from tts_template import render_tts_template
    from pages.schedule_pages import (
        SchedulePage,
        ScheduleAddPage,
        AlarmPage,
        AlarmAddPage,
    )
    from pages.voice_pages import SpeechRecognitionWorker, VoiceTestPage, TtsTestPage
    from pages.weather_page import WeatherForecastPage
    from pages.utility_pages import MedicationPage, MailPage, GesturePage
    from pages.home_page import HomePage
    from pages.settings_page import SettingsPage
    from config.app_constants import TTS_SCENARIO_DEFAULTS
    from engines.wakeword_runtime import (
        GUI_WAKEWORD_VARIANTS,
        GlobalWakewordController,
        extract_command_after_wakeword,
        is_wakeword_detected,
    )
    from engines.voice_response_builder import build_contextual_voice_response


class OmniMateMain(QMainWindow):
    def __init__(self):
        super().__init__()
        self._settings = QSettings("OmniMate", "AssistantGUI")
        self._theme_mode = str(self._settings.value("ui/theme", "light"))
        self._voice_only_face_mode = os.getenv("ASSISTANT_VOICE_ONLY_FACE_MODE", "1").strip() in {"1", "true", "TRUE"}
        self._manual_navigation_active = False
        self._manual_navigation_until = 0.0
        default_face_voice_loop = os.getenv("ASSISTANT_FACE_VOICE_LOOP", "1").strip() in {"1", "true", "TRUE"}
        self._face_voice_loop_enabled = str(
            self._settings.value("voice/pc_local_voice_enabled", "true" if default_face_voice_loop else "false")
        ).strip().lower() in {"1", "true", "yes", "on"}
        self._robot_voice_input_enabled = str(
            self._settings.value("voice/robot_voice_input_enabled", "false")
        ).strip().lower() in {"1", "true", "yes", "on"}
        self._person_greeting_enabled = str(
            self._settings.value("behavior/person_greeting_enabled", "false")
        ).strip().lower() in {"1", "true", "yes", "on"}
        self._person_greeting_suspend_reasons: set[str] = set()
        self._face_voice_wake_listen_sec = float(os.getenv("ASSISTANT_FACE_WAKE_LISTEN_SEC", "8"))
        self._face_voice_command_listen_sec = float(os.getenv("ASSISTANT_FACE_COMMAND_LISTEN_SEC", "4"))
        self._face_voice_wake_restart_delay_ms = int(os.getenv("ASSISTANT_FACE_WAKE_RESTART_DELAY_MS", "180"))
        self._face_voice_command_restart_delay_ms = int(os.getenv("ASSISTANT_FACE_COMMAND_RESTART_DELAY_MS", "100"))
        self._face_voice_command_timeout_sec = float(os.getenv("ASSISTANT_FACE_COMMAND_TIMEOUT_SEC", "10"))
        self._face_voice_max_silence_retries = int(os.getenv("ASSISTANT_FACE_COMMAND_SILENCE_RETRIES", "2"))
        self._default_voice_backend = str(self._settings.value("voice/default_backend", "auto"))
        self._default_edge_voice = str(self._settings.value("voice/edge_voice", "ko-KR-SunHiNeural"))
        self._wakeword_reply_only = str(self._settings.value("voice/wakeword_reply_only", "false")).lower() in {"1", "true", "yes"}
        self._robot_speaker_volume = int(self._settings.value("voice/robot_speaker_volume", 35))
        self._tts_defaults: dict[str, str] = {key: default for key, _label, default in TTS_SCENARIO_DEFAULTS}
        self._tts_labels: dict[str, str] = {key: label for key, label, _default in TTS_SCENARIO_DEFAULTS}
        self._tts_templates: dict[str, str] = {}
        self._load_tts_templates()
        schedule_path = str(Path(__file__).resolve().parent / "schedules.json")
        self.schedule_mgr = ScheduleManager(filename=schedule_path)
        alarm_path = str(Path(__file__).resolve().parent / "alarms.json")
        self.alarm_mgr = AlarmManager(filename=alarm_path)
        OcrEngine.start_reader_warmup()

        self.weather_engine = WeatherEngine()
        self.weather_engine.start()

        self.battery_engine = BatteryEngine()
        self.battery_engine.battery_changed.connect(self._on_battery_changed)
        self.battery_engine.start()

        self.pose_engine = PoseEngine()
        self.pose_engine.pose_changed.connect(self._on_pose_changed)
        self.pose_engine.start()

        self.setWindowTitle("OmniMate - AI Robot Dashboard")
        self.setMinimumSize(900, 360)
        self.resize(1600, 560)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        self.main_layout = QVBoxLayout(central_widget)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        # ------------------------------------------
        # 글로벌 헤더 (표정 화면에서는 숨겨짐)
        # ------------------------------------------
        self.hdr_frame = QFrame()
        self.hdr_frame.setObjectName("hdr_frame")
        self.hdr_frame.setFixedHeight(60)
        hdr_layout = QHBoxLayout(self.hdr_frame)
        hdr_layout.setContentsMargins(20, 0, 20, 0)

        hdr_home_Btn = QPushButton("🏠 Home")
        hdr_home_Btn.setStyleSheet("border: none; font-size: 18px; font-weight: bold;")
        hdr_home_Btn.clicked.connect(lambda: self.switch_page(1, manual=True)) # 1이 메인 홈

        # 다시 대기(표정) 모드로 돌아가기 위한 테스트 버튼
        hdr_sleep_Btn = QPushButton("💤 취침모드")
        hdr_sleep_Btn.setStyleSheet("border: none; font-size: 14px; color: #6B7280;")
        hdr_sleep_Btn.clicked.connect(lambda: self.switch_page(0, manual=True))

        self.hdr_voiceState_Lbl = QLabel("🎤️ 호출어 대기 중...")
        self.hdr_voiceState_Lbl.setObjectName("hdr_voiceState_Lbl")
        self.hdr_voiceState_Lbl.setAlignment(Qt.AlignCenter)

        hdr_status_layout = QHBoxLayout()
        self.hdr_network_lbl = QLabel("📶 확인 중...")
        self.hdr_network_lbl.setProperty("class", "SubText")
        self.hdr_mic_lbl = QLabel("🎙️ 확인 중...")
        self.hdr_mic_lbl.setProperty("class", "SubText")
        self.hdr_battery_lbl = QLabel("🔋 --")
        self.hdr_battery_lbl.setProperty("class", "SubText")
        hdr_status_layout.addWidget(self.hdr_network_lbl)
        hdr_status_layout.addWidget(self.hdr_mic_lbl)
        hdr_status_layout.addWidget(self.hdr_battery_lbl)

        hdr_layout.addWidget(hdr_home_Btn)
        hdr_layout.addWidget(hdr_sleep_Btn)
        hdr_layout.addWidget(self.hdr_voiceState_Lbl, stretch=1)
        hdr_layout.addLayout(hdr_status_layout)
        self.main_layout.addWidget(self.hdr_frame)

        # ------------------------------------------
        # 페이지 전환기 (QStackedWidget)
        # ------------------------------------------
        self.stacked_widget = QStackedWidget()
        self.main_layout.addWidget(self.stacked_widget)

        # 얼굴 시스템은 단일 컨트롤러를 공유해 메인/설정 탭의 로직 일관성을 유지 기능.
        # TODO(integration): 운영 중에는 설정 탭을 별도 테스트 컨트롤러로 분리할지 정책 확정.
        self.shared_face_controller = FaceController(self)
        self.shared_face_controller.start_timer(100)

        # 페이지 추가 (인덱스 순서 주의)

        self.face_page = UnifiedFacePage(controller=self.shared_face_controller, autonomous=False)
        self.face_page.clicked.connect(lambda: self.switch_page(1, manual=True))
        self.stacked_widget.addWidget(self.face_page)                                 # 0. 로봇 표정 (루트)
        self.home_page = HomePage(self, self.weather_engine)
        self.stacked_widget.addWidget(self.home_page)                                 # 1. 홈 대시보드
        self.schedule_page = SchedulePage(self)
        self.schedule_add_page = ScheduleAddPage(self)
        self.alarm_page = AlarmPage(self)
        self.alarm_add_page = AlarmAddPage(self)
        self.medication_page = MedicationPage(self)
        self.stacked_widget.addWidget(self.schedule_page)                             # 2. 일정
        self.stacked_widget.addWidget(self.schedule_add_page)                         # 3. 일정 추가
        self.stacked_widget.addWidget(self.alarm_page)                                # 4. 알람
        self.stacked_widget.addWidget(self.alarm_add_page)                            # 5. 알람 추가
        self.stacked_widget.addWidget(self.medication_page)                           # 6. 복약 확인
        self.stacked_widget.addWidget(MailPage(self))                                 # 7. 우편 (카메라)
        use_shared_face_test = os.getenv("ASSISTANT_FACE_TEST_USE_SHARED", "0").strip() in {"1", "true", "TRUE"}
        self.stacked_widget.addWidget(
            SettingsPage(
                main_window=self,
                shared_face_controller=self.shared_face_controller,
                use_shared_controller=use_shared_face_test,
            )
        )                                                                              # 8. 설정
        self.stacked_widget.addWidget(VoiceTestPage(self))                            # 9. 음성 테스트
        self.stacked_widget.addWidget(WeatherForecastPage(self.weather_engine, self)) # 10. 날씨 정보
        self.stacked_widget.addWidget(TtsTestPage(self))                              # 11. TTS 테스트
        self.gesture_page = GesturePage(self)
        self.stacked_widget.addWidget(self.gesture_page)                              # 12. 수취 확인/복귀 제스처
        self._global_wakeword_controller = GlobalWakewordController(self)
        # 처음 시작은 로봇 표정 화면으로
        self.switch_page(0)

        # ROS 브리지 선택적 활성화 기능. (기본: 비활성)
        # 네이티브 환경별 rclpy 종료 충돌을 피하기 위한 안전 모드.
        self._ros_bridge = None
        if os.getenv('ASSISTANT_ENABLE_ROS_BRIDGE', '0').strip() in {'1', 'true', 'TRUE'}:
            self._start_ros_bridge()

        self._status_poll_timer = QTimer(self)
        self._status_poll_timer.timeout.connect(self._refresh_runtime_capability_status)
        self._status_poll_timer.start(3000)
        self._refresh_runtime_capability_status()

        self._restore_ui_preferences()
        QTimer.singleShot(1800, self._sync_remote_audio_preferences)
        QTimer.singleShot(1200, self._sync_face_voice_loop)

    def _restore_ui_preferences(self) -> None:
        theme = str(self._settings.value("ui/theme", "light"))
        self.apply_theme(theme)

        poll_ms = int(self._settings.value("runtime/status_poll_ms", 3000))
        self.apply_status_poll_interval(poll_ms)

        face_fps = int(self._settings.value("runtime/face_fps", 10))
        self.apply_face_fps(face_fps)

        voice_backend = str(self._settings.value("voice/default_backend", self._default_voice_backend))
        edge_voice = str(self._settings.value("voice/edge_voice", self._default_edge_voice))
        wakeword_reply_only = str(self._settings.value("voice/wakeword_reply_only", "true" if self._wakeword_reply_only else "false"))
        robot_speaker_volume = int(self._settings.value("voice/robot_speaker_volume", self._robot_speaker_volume))
        pc_local_voice_enabled = str(self._settings.value("voice/pc_local_voice_enabled", "true" if self._face_voice_loop_enabled else "false"))
        robot_voice_input_enabled = str(self._settings.value("voice/robot_voice_input_enabled", "true" if self._robot_voice_input_enabled else "false"))
        self.apply_default_voice_backend(voice_backend)
        self.apply_default_edge_voice(edge_voice)
        self.apply_wakeword_reply_only(wakeword_reply_only)
        if not self.is_microphone_available():
            pc_local_voice_enabled = "false"
        self.apply_pc_local_voice_enabled(pc_local_voice_enabled)
        self.apply_robot_voice_input_enabled(robot_voice_input_enabled, publish=False)
        self.apply_person_greeting_enabled(
            str(self._settings.value("behavior/person_greeting_enabled", "true" if self._person_greeting_enabled else "false")),
            publish=False,
        )
        self.apply_robot_speaker_volume(robot_speaker_volume, publish=False)

        width = int(self._settings.value("window/width", 1600))
        height = int(self._settings.value("window/height", 560))
        self.resize(width, height)
        self._pref_fullscreen = str(self._settings.value("window/fullscreen", "false")).lower() in {"1", "true", "yes"}

    def apply_theme(self, theme: str) -> None:
        theme = "dark" if theme == "dark" else "light"
        self._theme_mode = theme
        app = QApplication.instance()
        if app is not None:
            app.setStyleSheet(THEME_STYLES[theme])
        self._refresh_page_theme_overrides()
        self._settings.setValue("ui/theme", theme)

    def _refresh_page_theme_overrides(self) -> None:
        # Pages with local styles must be refreshed explicitly after global theme swap.
        try:
            if hasattr(self, "schedule_page"):
                if hasattr(self.schedule_page, "_apply_list_theme_style"):
                    self.schedule_page._apply_list_theme_style()
                if hasattr(self.schedule_page, "_apply_calendar_theme_style"):
                    self.schedule_page._apply_calendar_theme_style()
                if hasattr(self.schedule_page, "update_calendar_markers"):
                    self.schedule_page.update_calendar_markers()
            if hasattr(self, "alarm_page") and hasattr(self.alarm_page, "_apply_theme_style"):
                self.alarm_page._apply_theme_style()
                if hasattr(self.alarm_page, "update_list"):
                    self.alarm_page.update_list()
            if hasattr(self, "alarm_add_page") and hasattr(self.alarm_add_page, "_apply_theme_style"):
                self.alarm_add_page._apply_theme_style()
            if hasattr(self, "medication_page") and hasattr(self.medication_page, "_apply_theme_style"):
                self.medication_page._apply_theme_style()
                if hasattr(self.medication_page, "update_list"):
                    self.medication_page.update_list()
        except Exception:
            # Theme refresh should never block runtime behavior.
            pass

    def _on_battery_changed(self, percent: int, is_charging: bool) -> None:
        """배터리 상태 변경 시 헤더 업데이트."""
        charging_icon = "⚡" if is_charging else "🔋"
        self.hdr_battery_lbl.setText(f"{charging_icon} {percent}%")
        if hasattr(self, "shared_face_controller"):
            try:
                self.shared_face_controller.on_battery_changed(float(percent), charging=is_charging)
            except Exception:
                pass

    def _on_pose_changed(self, x_m: float, y_m: float, source: str) -> None:
        if hasattr(self, "home_page"):
            try:
                self.home_page.update_robot_pose(x_m, y_m, source)
            except Exception:
                pass

    def apply_window_size(self, width: int, height: int) -> None:
        width = max(800, min(3840, int(width)))
        height = max(360, min(2160, int(height)))
        self.resize(width, height)
        self._settings.setValue("window/width", width)
        self._settings.setValue("window/height", height)

    def apply_fullscreen(self, enabled: bool, width: int | None = None, height: int | None = None) -> None:
        if enabled:
            self.showFullScreen()
            self._settings.setValue("window/fullscreen", True)
        else:
            self.showNormal()
            self._settings.setValue("window/fullscreen", False)
            if width is not None and height is not None:
                self.apply_window_size(width, height)

    def apply_status_poll_interval(self, ms: int) -> None:
        ms = max(500, min(10000, int(ms)))
        self._status_poll_timer.setInterval(ms)
        self._settings.setValue("runtime/status_poll_ms", ms)

    def apply_face_fps(self, fps: int) -> None:
        fps = max(5, min(60, int(fps)))
        interval_ms = max(16, int(1000 / fps))
        self.shared_face_controller.start_timer(interval_ms)
        self._settings.setValue("runtime/face_fps", fps)

    def apply_default_voice_backend(self, backend: str) -> None:
        mapping = {
            "자동": "auto",
            "Edge TTS": "edge_tts",
            "Speech Dispatcher": "speech_dispatcher",
            "eSpeak NG": "espeak_ng",
            "auto": "auto",
            "edge_tts": "edge_tts",
            "speech_dispatcher": "speech_dispatcher",
            "espeak_ng": "espeak_ng",
        }
        normalized = mapping.get(str(backend).strip(), "auto")
        self._default_voice_backend = normalized
        self._settings.setValue("voice/default_backend", normalized)

    def apply_default_edge_voice(self, voice_name: str) -> None:
        voice = str(voice_name).strip() or "ko-KR-SunHiNeural"
        self._default_edge_voice = voice
        self._settings.setValue("voice/edge_voice", voice)

    def apply_wakeword_reply_only(self, enabled) -> None:
        if isinstance(enabled, str):
            self._wakeword_reply_only = enabled.strip().lower() in {"1", "true", "yes", "on"}
        else:
            self._wakeword_reply_only = bool(enabled)
        self._settings.setValue("voice/wakeword_reply_only", self._wakeword_reply_only)

    def apply_pc_local_voice_enabled(self, enabled) -> None:
        if isinstance(enabled, str):
            self._face_voice_loop_enabled = enabled.strip().lower() in {"1", "true", "yes", "on"}
        else:
            self._face_voice_loop_enabled = bool(enabled)
        self._settings.setValue("voice/pc_local_voice_enabled", self._face_voice_loop_enabled)
        if hasattr(self, "_global_wakeword_controller"):
            self._sync_face_voice_loop()

    def apply_robot_voice_input_enabled(
        self,
        enabled,
        *,
        publish: bool = False,
    ) -> tuple[bool, str]:
        if isinstance(enabled, str):
            self._robot_voice_input_enabled = enabled.strip().lower() in {"1", "true", "yes", "on"}
        else:
            self._robot_voice_input_enabled = bool(enabled)
        self._settings.setValue("voice/robot_voice_input_enabled", self._robot_voice_input_enabled)
        if not publish:
            label = "활성" if self._robot_voice_input_enabled else "비활성"
            return True, f"로봇 음성 입력 기본값을 {label}으로 저장했습니다."
        return self.publish_robot_voice_input_enabled(self._robot_voice_input_enabled)

    def apply_robot_speaker_volume(self, value: int, *, publish: bool = False) -> tuple[bool, str]:
        volume = max(0, min(100, int(value)))
        self._robot_speaker_volume = volume
        self._settings.setValue("voice/robot_speaker_volume", volume)
        if not publish:
            return True, f"로봇 스피커 볼륨 기본값을 {volume}%로 저장했습니다."
        return self.publish_robot_speaker_volume(volume)

    def apply_person_greeting_enabled(
        self,
        enabled,
        *,
        publish: bool = False,
    ) -> tuple[bool, str]:
        if isinstance(enabled, str):
            self._person_greeting_enabled = enabled.strip().lower() in {"1", "true", "yes", "on"}
        else:
            self._person_greeting_enabled = bool(enabled)
        self._settings.setValue("behavior/person_greeting_enabled", self._person_greeting_enabled)
        if not publish:
            label = "활성" if self._person_greeting_enabled else "비활성"
            return True, f"사람 인사 로직 기본값을 {label}으로 저장했습니다."
        return self.publish_person_greeting_enabled(self._person_greeting_enabled)

    def _load_tts_templates(self) -> None:
        loaded: dict[str, str] = {}
        for key, _label, default in TTS_SCENARIO_DEFAULTS:
            value = str(self._settings.value(f"voice/templates/{key}", default)).strip()
            loaded[key] = value or default
        self._tts_templates = loaded

    def get_tts_scenario_items(self) -> list[tuple[str, str]]:
        return [(key, self._tts_labels.get(key, key)) for key, _label, _default in TTS_SCENARIO_DEFAULTS]

    def get_tts_template(self, scenario_key: str) -> str:
        key = str(scenario_key).strip()
        if key in self._tts_templates:
            return self._tts_templates[key]
        return self._tts_defaults.get(key, "")

    def set_tts_template(self, scenario_key: str, text: str) -> None:
        key = str(scenario_key).strip()
        if key not in self._tts_defaults:
            return
        value = str(text or "").strip() or self._tts_defaults[key]
        self._tts_templates[key] = value
        self._settings.setValue(f"voice/templates/{key}", value)

    def reset_tts_templates(self) -> None:
        self._tts_templates = dict(self._tts_defaults)
        for key in self._tts_defaults:
            self._settings.setValue(f"voice/templates/{key}", self._tts_templates[key])

    def _guess_current_place(self) -> str:
        main_text = ""
        sub_text = ""
        if hasattr(self, "home_page"):
            try:
                main_text = self.home_page.st_main.text().strip()
                sub_text = self.home_page.st_sub.text().strip()
            except Exception:
                main_text = ""
                sub_text = ""

        # 예: "회의실 배송 중"
        match = re.match(r"^(.+?)\s+배송\s+중$", main_text)
        if match:
            return match.group(1).strip()

        # 예: "현재 회의실(으)로 이동하고 있습니다."
        match = re.search(r"현재\s+(.+?)\(으\)로\s+이동", sub_text)
        if match:
            return match.group(1).strip()

        # 예: "회의실에 우편 배달을 완료했습니다."
        match = re.search(r"(.+?)에\s+우편\s+배달", sub_text)
        if match:
            return match.group(1).strip()

        return "목적지"

    def build_tts_runtime_context(self, command_text: str = "") -> dict[str, str]:
        now = datetime.now()
        location = self._guess_current_place()
        command = str(command_text or "").strip()
        return {
            "장소": location,
            "명령": command,
            "시간": now.strftime("%H:%M"),
            "날짜": now.strftime("%Y-%m-%d"),
            "location": location,
            "command": command,
        }

    def render_tts_scenario(self, scenario_key: str, context: dict[str, str] | None = None) -> str:
        key = str(scenario_key).strip()
        template = self.get_tts_template(key)
        merged_context = self.build_tts_runtime_context()
        if context:
            merged_context.update({str(k): str(v) for k, v in context.items()})
        text = render_tts_template(template, merged_context)
        return text or template

    @staticmethod
    def classify_tts_scenario(text: str) -> str:
        normalized = str(text or "").replace(" ", "")
        if normalized in {"옴니", "옴니야"}:
            return "wakeword_prompt"
        if "일정" in normalized:
            return "schedule_query"
        if "알람맞춰줘" in normalized or "알람설정" in normalized or "알람추가" in normalized:
            return "alarm_set"
        if "알람" in normalized:
            return "alarm_query"
        if "복약" in normalized or "약확인" in normalized or "약체크" in normalized:
            return "medication_query"
        if "취소" in normalized or "중지" in normalized or "멈춰" in normalized:
            return "cancel"
        if "날씨" in normalized:
            return "weather"
        if "어디가" in normalized or "어디로가" in normalized:
            return "where_status"
        if "우편" in normalized or "배달" in normalized or "배송" in normalized or "전달" in normalized:
            return "delivery_request"
        if "가줘" in normalized or "로가" in normalized or "안내해줘" in normalized:
            return "navigation_request"
        return "unknown"

    def build_situation_response_text(self, command_text: str) -> str:
        return build_contextual_voice_response(self, command_text)

    def _get_runtime_data_service(self):
        try:
            runtime_module = importlib.import_module("assistant_robot.services.runtime_data_service")
            runtime_service_class = getattr(runtime_module, "RuntimeDataService")
        except Exception:
            return None
        medication_path = ""
        if hasattr(self, "medication_page") and hasattr(self.medication_page, "med_mgr"):
            medication_path = str(getattr(self.medication_page.med_mgr, "filename", ""))
        return runtime_service_class(
            schedule_path=str(getattr(self.schedule_mgr, "filename", "")),
            alarm_path=str(getattr(self.alarm_mgr, "filename", "")),
            medication_path=medication_path,
        )

    @staticmethod
    def _is_schedule_add_command(text: str) -> bool:
        return bool(re.search(r"(일정|스케줄|약속).*(추가|등록)", str(text or "")))

    @staticmethod
    def _is_alarm_add_command(text: str) -> bool:
        return bool(re.search(r"알람\s*(맞춰\s*줘|설정\s*해\s*줘|추가\s*해\s*줘|등록\s*해\s*줘)", str(text or "")))

    @staticmethod
    def _is_medication_add_command(text: str) -> bool:
        return bool(re.search(r"(복약|약).*(추가|등록)", str(text or "")))

    def _is_always_local_voice_command(self, command_text: str) -> bool:
        scenario = self.classify_tts_scenario(command_text)
        if scenario in {
            "wakeword_prompt",
            "schedule_query",
            "alarm_set",
            "alarm_query",
            "medication_query",
            "weather",
        }:
            return True
        return (
            self._is_schedule_add_command(command_text)
            or self._is_alarm_add_command(command_text)
            or self._is_medication_add_command(command_text)
        )

    def _can_fallback_to_local_voice_command(self, command_text: str) -> bool:
        scenario = self.classify_tts_scenario(command_text)
        return scenario in {"cancel", "where_status"} or self._is_always_local_voice_command(command_text)

    def _refresh_local_data_views(self) -> None:
        try:
            if hasattr(self, "schedule_mgr"):
                self.schedule_mgr.load_data()
            if hasattr(self, "schedule_page") and hasattr(self.schedule_page, "update_schedule_list"):
                self.schedule_page.update_schedule_list()
            if hasattr(self, "alarm_mgr"):
                self.alarm_mgr.load_data()
            if hasattr(self, "alarm_page") and hasattr(self.alarm_page, "update_list"):
                self.alarm_page.update_list()
            if hasattr(self, "medication_page") and hasattr(self.medication_page, "med_mgr"):
                self.medication_page.med_mgr.load_data()
            if hasattr(self, "medication_page") and hasattr(self.medication_page, "update_list"):
                self.medication_page.update_list()
            if hasattr(self, "medication_page") and hasattr(self.medication_page, "update_status_logic"):
                self.medication_page.update_status_logic()
        except Exception:
            pass

    def build_local_voice_response(self, command_text: str) -> str:
        runtime_data = self._get_runtime_data_service()
        text = str(command_text or "").strip()
        if runtime_data is not None:
            if self._is_schedule_add_command(text):
                response = runtime_data.add_schedule_from_text(text)
                self._refresh_local_data_views()
                return response
            if self._is_alarm_add_command(text):
                response = runtime_data.add_alarm_from_text(text)
                self._refresh_local_data_views()
                return response
            if self._is_medication_add_command(text):
                response = runtime_data.add_medication_from_text(text)
                self._refresh_local_data_views()
                return response
        return self.build_situation_response_text(text)

    def dispatch_voice_command(self, command_text: str) -> tuple[bool, str, bool]:
        text = str(command_text or "").strip()
        if not text:
            return False, "빈 명령입니다.", False

        if self._is_always_local_voice_command(text):
            return True, self.build_local_voice_response(text), True

        submitted, message = self.submit_command_text(text)
        if not submitted and self._can_fallback_to_local_voice_command(text):
            return True, self.build_local_voice_response(text), True
        return submitted, message, False

    def speak_text(self, text: str, *, target: str = "pc") -> tuple[bool, str]:
        if target == "robot":
            return self.publish_tts_to_robot(text)
        ok = self._speak_quick(text)
        if ok:
            return True, "ok"
        selected = str(getattr(self, "_default_voice_backend", "auto"))
        return False, (
            "PC TTS 실행에 실패했습니다. "
            f"(기본 음성 엔진: {selected}, edge-tts/spd-say/espeak-ng 설치/상태 확인 필요)"
        )

    def submit_command_text(self, command_text: str) -> tuple[bool, str]:
        text = str(command_text or "").strip()
        if not text:
            return False, "빈 명령입니다."
        return self._publish_string_topic("/assistant/command_text", text)

    def send_nav_to_coordinate(self, x_m: float, y_m: float) -> tuple[bool, str]:
        """지도 클릭 좌표 기반 로봇 이동 명령 발행 기능."""
        msg_data = f"navigate:x={x_m:.3f},y={y_m:.3f}"
        return self.submit_command_text(msg_data)

    def send_nav_to_named_place(self, place_name: str) -> tuple[bool, str]:
        name = str(place_name or "").strip()
        if not name:
            return False, "장소 이름이 비어 있습니다."
        return self.submit_command_text(f"{name}으로 안내해줘")

    def _load_named_place_document(self) -> dict:
        config_path = ROBOT_NAMED_PLACE_CONFIG
        if not config_path.exists():
            return {"medication_targets": [], "named_places": {}}
        loaded = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        return loaded if isinstance(loaded, dict) else {"medication_targets": [], "named_places": {}}

    @staticmethod
    def _yaw_from_metadata(metadata: dict) -> float:
        if "yaw" in metadata:
            try:
                return float(metadata.get("yaw", 0.0))
            except (TypeError, ValueError):
                return 0.0
        try:
            orientation_z = float(metadata.get("orientation_z", 0.0))
            orientation_w = float(metadata.get("orientation_w", 1.0))
            return math.atan2(2.0 * orientation_w * orientation_z, 1.0 - 2.0 * orientation_z * orientation_z)
        except (TypeError, ValueError):
            return 0.0

    def get_named_place_items(self) -> list[dict[str, object]]:
        document = self._load_named_place_document()
        raw_places = document.get("named_places", {})
        if not isinstance(raw_places, dict):
            return []

        items: list[dict[str, object]] = []
        for name, metadata in raw_places.items():
            if not isinstance(metadata, dict):
                continue
            aliases = metadata.get("aliases", [])
            if not isinstance(aliases, list):
                aliases = []
            items.append(
                {
                    "name": str(name).strip(),
                    "source": str(metadata.get("source", "waypoints")).strip() or "waypoints",
                    "frame_id": str(metadata.get("frame_id", "map")).strip() or "map",
                    "x": float(metadata.get("x", 0.0)),
                    "y": float(metadata.get("y", 0.0)),
                    "yaw": self._yaw_from_metadata(metadata),
                    "aliases": [str(alias).strip() for alias in aliases if str(alias).strip()],
                    "ocr_enabled": bool(metadata.get("ocr_enabled", False)),
                }
            )
        return items

    def get_named_place_lookup(self) -> dict[str, dict[str, object]]:
        return {str(item.get("name", "")): item for item in self.get_named_place_items() if str(item.get("name", "")).strip()}

    def get_quick_destination_names(self, *, limit: int = 4) -> list[str]:
        preferred = [item["name"] for item in self.get_named_place_items() if item.get("name") and item.get("name") != "home"]
        if not preferred:
            preferred = [item["name"] for item in self.get_named_place_items() if item.get("name")]
        return [str(name) for name in preferred[: max(1, int(limit))]]

    def save_named_place_items(self, items: list[dict[str, object]]) -> tuple[bool, str]:
        existing_lookup = self.get_named_place_lookup()
        named_places: dict[str, dict[str, object]] = {}
        for item in items:
            name = str(item.get("name", "")).strip()
            if not name:
                continue

            aliases_value = item.get("aliases", [])
            if isinstance(aliases_value, str):
                aliases = [alias.strip() for alias in aliases_value.split(",") if alias.strip()]
            elif isinstance(aliases_value, list):
                aliases = [str(alias).strip() for alias in aliases_value if str(alias).strip()]
            else:
                aliases = []
            if name not in aliases:
                aliases.insert(0, name)

            try:
                x_value = float(item.get("x", 0.0))
                y_value = float(item.get("y", 0.0))
                yaw_value = float(item.get("yaw", 0.0))
            except (TypeError, ValueError):
                return False, f"장소 '{name}'의 좌표 또는 yaw 값이 올바르지 않습니다."

            named_places[name] = {
                "source": str(item.get("source", existing_lookup.get(name, {}).get("source", "waypoints"))).strip() or "waypoints",
                "frame_id": str(item.get("frame_id", "map")).strip() or "map",
                "x": round(x_value, 3),
                "y": round(y_value, 3),
                "yaw": round(yaw_value, 3),
                "aliases": aliases,
                "ocr_enabled": bool(item.get("ocr_enabled", False)),
            }

        document = self._load_named_place_document()
        medication_targets = document.get("medication_targets", [])
        if not isinstance(medication_targets, list):
            medication_targets = []

        config_path = ROBOT_NAMED_PLACE_CONFIG
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(
            yaml.safe_dump(
                {
                    "medication_targets": medication_targets,
                    "named_places": named_places,
                },
                allow_unicode=True,
                sort_keys=False,
            ),
            encoding="utf-8",
        )

        if hasattr(self, "home_page") and self.home_page is not None and hasattr(self.home_page, "refresh_quick_destinations"):
            self.home_page.refresh_quick_destinations()
        return True, f"장소 {len(named_places)}개를 저장했습니다."

    def publish_tts_to_robot(self, text: str) -> tuple[bool, str]:
        if not shutil.which("ros2"):
            return False, "ros2 CLI를 찾을 수 없습니다."

        safe_text = text.replace("\\", "\\\\").replace('"', '\\"')
        msg_arg = f'{{data: "{safe_text}"}}'
        cmd = [
            "ros2", "topic", "pub", "--once",
            "-w", "1", "--max-wait-time-secs", "1",
            "/assistant/speak", "std_msgs/msg/String", msg_arg,
        ]

        ros_env = self._build_ros_cli_env()

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=6, env=ros_env)
            if result.returncode != 0:
                err = (result.stderr.strip() or result.stdout.strip() or "ros2 topic pub 실패")
                if "Timed out waiting for subscribers" in err:
                    err = "구독자 없음: 로봇 tts_node 미실행 또는 ROS_DOMAIN_ID/RMW 불일치"
                elif "Connection refused" in err or "연결이 거부" in err:
                    err = "로봇 연결이 거부되었습니다. 로봇측 ROS2 노드/네트워크/도메인(ROS_DOMAIN_ID=142) 설정을 확인하세요."
                return False, err
            return True, "ok"
        except Exception as exc:
            message = str(exc)
            if "Connection refused" in message or "연결이 거부" in message:
                return False, "로봇 연결이 거부되었습니다. 로봇측 ROS2 노드/네트워크/도메인(ROS_DOMAIN_ID=142) 설정을 확인하세요."
            return False, message

    def _publish_string_topic(self, topic_name: str, text: str) -> tuple[bool, str]:
        if not shutil.which("ros2"):
            return False, "ros2 CLI를 찾을 수 없습니다."

        payload = json.dumps({"data": text}, ensure_ascii=False)
        cmd = [
            "ros2", "topic", "pub", "--once",
            "-w", "1", "--max-wait-time-secs", "1",
            topic_name, "std_msgs/msg/String", payload,
        ]

        ros_env = self._build_ros_cli_env()

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=6, env=ros_env)
            if result.returncode != 0:
                err = result.stderr.strip() or result.stdout.strip() or "ros2 topic pub 실패"
                if "Timed out waiting for subscribers" in err:
                    err = (
                        "명령 구독자 없음: ROS 노드가 아직 안 떠 있거나 "
                        "orchestrator_node/intent_parser_node 미실행, 또는 ROS_DOMAIN_ID/RMW 설정이 다릅니다."
                    )
                elif "Connection refused" in err or "연결이 거부" in err:
                    err = "ROS 연결이 거부되었습니다. 로봇측 ROS2 노드/네트워크/도메인 설정을 확인하세요."
                return False, err
            return True, "ok"
        except Exception as exc:
            message = str(exc)
            if "Connection refused" in message or "연결이 거부" in message:
                return False, "ROS 연결이 거부되었습니다. 로봇측 ROS2 노드/네트워크/도메인 설정을 확인하세요."
            return False, message

    def publish_robot_speaker_volume(self, volume: int) -> tuple[bool, str]:
        return self._publish_int_topic('/assistant/audio/set_volume', volume)

    def publish_robot_voice_input_enabled(self, enabled: bool) -> tuple[bool, str]:
        ok, message = self._publish_bool_topic('/assistant/audio/robot/input_enabled', enabled)
        if not ok:
            return ok, message
        state_label = '활성' if enabled else '비활성'
        return True, f'로봇 음성 입력을 {state_label}했습니다.'

    def publish_person_greeting_enabled(self, enabled: bool) -> tuple[bool, str]:
        ok, message = self._publish_bool_topic('/assistant/person_greeting/enabled', enabled)
        if not ok:
            return ok, message
        state_label = '활성' if enabled else '비활성'
        return True, f'사람 인사 로직을 {state_label}했습니다.'

    def suspend_person_greeting(self, reason: str) -> tuple[bool, str]:
        token = str(reason).strip() or 'runtime'
        already_suspended = bool(self._person_greeting_suspend_reasons)
        self._person_greeting_suspend_reasons.add(token)
        if already_suspended:
            return True, '사람 인식 인사 로직이 이미 작업 중 임시 중지 상태입니다.'
        return self.publish_person_greeting_enabled(False)

    def resume_person_greeting(self, reason: str) -> tuple[bool, str]:
        token = str(reason).strip() or 'runtime'
        self._person_greeting_suspend_reasons.discard(token)
        if self._person_greeting_suspend_reasons:
            return True, '다른 작업이 아직 실행 중이라 사람 인식 인사를 계속 중지합니다.'
        return self.publish_person_greeting_enabled(bool(self._person_greeting_enabled))

    def _publish_int_topic(self, topic_name: str, value: int) -> tuple[bool, str]:
        if not shutil.which("ros2"):
            return False, "ros2 CLI를 찾을 수 없습니다."

        payload = json.dumps({"data": int(value)}, ensure_ascii=False)
        cmd = [
            "ros2", "topic", "pub", "--once",
            "-w", "1", "--max-wait-time-secs", "1",
            topic_name, "std_msgs/msg/Int32", payload,
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=6, env=self._build_ros_cli_env())
            if result.returncode != 0:
                err = result.stderr.strip() or result.stdout.strip() or "ros2 topic pub 실패"
                if "Timed out waiting for subscribers" in err:
                    err = "로봇 오디오 구독자 없음: tts_node 미실행 또는 ROS_DOMAIN_ID/RMW 설정 불일치"
                elif "Connection refused" in err or "연결이 거부" in err:
                    err = "로봇 연결이 거부되었습니다. 로봇측 ROS2 오디오 노드/네트워크/도메인 설정을 확인하세요."
                return False, err
            return True, f"로봇 스피커 볼륨을 {int(value)}%로 적용했습니다."
        except Exception as exc:
            message = str(exc)
            if "Connection refused" in message or "연결이 거부" in message:
                return False, "로봇 연결이 거부되었습니다. 로봇측 ROS2 오디오 노드/네트워크/도메인 설정을 확인하세요."
            return False, message

    def _publish_bool_topic(self, topic_name: str, value: bool) -> tuple[bool, str]:
        if not shutil.which("ros2"):
            return False, "ros2 CLI를 찾을 수 없습니다."

        payload = json.dumps({"data": bool(value)}, ensure_ascii=False)
        cmd = [
            "ros2", "topic", "pub", "--once",
            "-w", "1", "--max-wait-time-secs", "1",
            topic_name, "std_msgs/msg/Bool", payload,
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=6, env=self._build_ros_cli_env())
            if result.returncode != 0:
                err = result.stderr.strip() or result.stdout.strip() or "ros2 topic pub 실패"
                if "Timed out waiting for subscribers" in err:
                    err = "로봇 오디오 제어 구독자 없음: 로봇 오디오 노드 미실행 또는 ROS 설정 불일치"
                elif "Connection refused" in err or "연결이 거부" in err:
                    err = "로봇 연결이 거부되었습니다. 로봇측 ROS2 오디오 노드/네트워크/도메인 설정을 확인하세요."
                return False, err
            return True, "ok"
        except Exception as exc:
            message = str(exc)
            if "Connection refused" in message or "연결이 거부" in message:
                return False, "로봇 연결이 거부되었습니다. 로봇측 ROS2 오디오 노드/네트워크/도메인 설정을 확인하세요."
            return False, message

    def _sync_remote_audio_preferences(self) -> None:
        try:
            if not self._query_remote_bool_topic('/assistant/audio/robot/input_available'):
                self.apply_robot_voice_input_enabled(False, publish=False)
            self.publish_robot_voice_input_enabled(bool(self._robot_voice_input_enabled))
            self.publish_person_greeting_enabled(bool(self._person_greeting_enabled))
        except Exception:
            pass

    def _query_remote_bool_topic(self, topic_name: str) -> bool:
        if not shutil.which("ros2"):
            return False

        cmd = [
            "ros2", "topic", "echo", "--once",
            topic_name, "std_msgs/msg/Bool",
        ]
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=4,
                env=self._build_ros_cli_env(),
            )
            if result.returncode != 0:
                return False
            output = (result.stdout or "").lower()
            return "data: true" in output
        except Exception:
            return False

    @staticmethod
    def _build_ros_cli_env() -> dict[str, str]:
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
        return ros_env

    def switch_page(self, index, *, manual: bool = False):
        """페이지 전환 및 헤더 표시 여부 결정"""
        if manual:
            # 사람이 직접 화면을 조작한 경우에만 표정 화면 고정을 해제 기능.
            self._manual_navigation_active = index != 0
            if self._manual_navigation_active:
                self._manual_navigation_until = time.monotonic() + 20.0
            else:
                self._manual_navigation_until = 0.0

        # 수동 이동 직후 자동 화면 덮어쓰기 방지 보호 기능.
        if (not manual and index == 0 and self._manual_navigation_active and
                time.monotonic() < self._manual_navigation_until):
            return

        # 음성 전용 모드에서는 수동 조작 전까지 표정 화면(0)만 유지 기능.
        if self._voice_only_face_mode and not manual and not self._manual_navigation_active and index != 0:
            index = 0

        # 표정 화면으로 돌아오면 다시 음성 전용 고정 상태를 복구 기능.
        if index == 0:
            self._manual_navigation_active = False
            self._manual_navigation_until = 0.0

        if index == 3 and hasattr(self, "schedule_page") and hasattr(self, "schedule_add_page"):
            selected_date = self.schedule_page.cal.selectedDate()
            self.schedule_add_page.date_input.setDate(selected_date)

        self.stacked_widget.setCurrentIndex(index)

        # 인덱스 0(로봇 표정)일 때는 글로벌 헤더를 숨깁니다.
        if index == 0:
            self.hdr_frame.hide()
        else:
            self.hdr_frame.show()

        self._sync_face_voice_loop()

    def _sync_face_voice_loop(self) -> None:
        self._global_wakeword_controller.sync()

    def _start_face_voice_worker(self, *, delay_ms: int = 0) -> None:
        if not self._face_voice_loop_active:
            return
        if self._face_voice_worker is not None:
            return

        def _kickoff() -> None:
            if not self._face_voice_loop_active or self._face_voice_worker is not None:
                return
            if time.monotonic() < self._face_voice_pause_until:
                QTimer.singleShot(250, lambda: self._start_face_voice_worker(delay_ms=0))
                return
            if not self.is_microphone_available() or not self.is_network_available():
                QTimer.singleShot(2500, lambda: self._start_face_voice_worker(delay_ms=0))
                return

            record_seconds = 20 if self._face_voice_stage == "wakeword" else 6

            worker = SpeechRecognitionWorker(language="ko-KR", record_seconds=record_seconds, parent=self)
            self._face_voice_worker = worker
            worker.recognized.connect(self._on_face_voice_recognized)
            worker.failed.connect(self._on_face_voice_failed)
            worker.finished.connect(self._on_face_voice_finished)
            worker.start()

        if delay_ms > 0:
            QTimer.singleShot(delay_ms, _kickoff)
        else:
            _kickoff()

    def _on_face_voice_recognized(self, text: str) -> None:
        wakeword_hit = self._is_wakeword_detected(text)

        if self._face_voice_stage == "wakeword":
            if wakeword_hit:
                inline_command = self._extract_command_after_wakeword(text)
                if hasattr(self, "shared_face_controller"):
                    try:
                        self.shared_face_controller.on_wakeword_detected()
                        if inline_command:
                            self.shared_face_controller.on_listening_finished()
                        else:
                            self.shared_face_controller.on_listening_started()
                    except Exception:
                        pass

                if inline_command:
                    self._handle_voice_command(inline_command)
                    return

                self.hdr_voiceState_Lbl.setText("🎧 호출어 인식, 명령 대기 중...")
                self.hdr_voiceState_Lbl.setStyleSheet("font-size: 16px; font-weight: bold; color: #3B82F6;")
                wakeword_prompt = self.render_tts_scenario("wakeword_prompt")
                if self._speak_quick(wakeword_prompt):
                    if self._wakeword_reply_only:
                        self._face_voice_stage = "wakeword"
                        self._face_voice_command_started_at = 0.0
                        self._face_voice_silence_retries = 0
                        self.hdr_voiceState_Lbl.setText("🎤️ 호출어 대기 중...")
                        self.hdr_voiceState_Lbl.setStyleSheet("font-size: 16px; font-weight: bold; color: #10B981;")
                        return
                    self._face_voice_stage = "command"
                    self._face_voice_command_started_at = time.monotonic()
                    self._face_voice_silence_retries = 0
                else:
                    self._face_voice_stage = "wakeword"
                    self._face_voice_command_started_at = 0.0
                    self._face_voice_silence_retries = 0
                    self.hdr_voiceState_Lbl.setText("⚠️ 음성 출력 실패 (TTS 확인 필요)")
                    self.hdr_voiceState_Lbl.setStyleSheet("font-size: 16px; font-weight: bold; color: #EF4444;")
            return

        if wakeword_hit:
            inline_command = self._extract_command_after_wakeword(text)
            if inline_command:
                if self._wakeword_reply_only:
                    self._speak_quick(self.render_tts_scenario("wakeword_only_mode"))
                    self._face_voice_stage = "wakeword"
                    self._face_voice_command_started_at = 0.0
                    self._face_voice_silence_retries = 0
                    return
                self._handle_voice_command(inline_command)
                return
            wakeword_prompt = self.render_tts_scenario("wakeword_prompt")
            if self._speak_quick(wakeword_prompt):
                if self._wakeword_reply_only:
                    self._face_voice_stage = "wakeword"
                    self._face_voice_command_started_at = 0.0
                    self._face_voice_silence_retries = 0
                    return
                self._face_voice_command_started_at = time.monotonic()
                self._face_voice_silence_retries = 0
            else:
                self._face_voice_stage = "wakeword"
                self._face_voice_command_started_at = 0.0
                self._face_voice_silence_retries = 0
            return

        self._handle_voice_command(text)

    def _handle_voice_command(self, command_text: str) -> None:
        response = self.build_situation_response_text(command_text)
        if hasattr(self, "shared_face_controller"):
            try:
                self.shared_face_controller.on_listening_finished()
            except Exception:
                pass
        self.hdr_voiceState_Lbl.setText("💬 음성 명령 처리 완료")
        self.hdr_voiceState_Lbl.setStyleSheet("font-size: 16px; font-weight: bold; color: #10B981;")
        self._speak_quick(response)
        self._face_voice_stage = "wakeword"
        self._face_voice_command_started_at = 0.0
        self._face_voice_silence_retries = 0

    @staticmethod
    def _extract_command_after_wakeword(text: str) -> str:
        return extract_command_after_wakeword(text)

    def _on_face_voice_failed(self, message: str) -> None:
        if self._face_voice_stage != "command":
            return

        self._face_voice_silence_retries += 1
        elapsed = 0.0
        if self._face_voice_command_started_at > 0.0:
            elapsed = time.monotonic() - self._face_voice_command_started_at

        timeout_hit = elapsed >= self._face_voice_command_timeout_sec
        retry_hit = self._face_voice_silence_retries >= self._face_voice_max_silence_retries
        if timeout_hit or retry_hit or ("초과" in message):
            self._face_voice_stage = "wakeword"
            self._face_voice_command_started_at = 0.0
            self._face_voice_silence_retries = 0
            if hasattr(self, "shared_face_controller"):
                try:
                    self.shared_face_controller.on_listening_finished()
                except Exception:
                    pass
            self.hdr_voiceState_Lbl.setText("🎤️ 호출어 대기 중...")
            self.hdr_voiceState_Lbl.setStyleSheet("font-size: 16px; font-weight: bold; color: #10B981;")

    def _on_face_voice_finished(self) -> None:
        self._face_voice_worker = None
        if self._face_voice_loop_active:
            next_delay = 250 if self._face_voice_stage == "command" else 600
            self._start_face_voice_worker(delay_ms=next_delay)

    def _speak_quick(self, text: str) -> bool:
        if hasattr(self, "shared_face_controller"):
            try:
                self.shared_face_controller.on_tts_started()
            except Exception:
                pass

        selected = str(getattr(self, "_default_voice_backend", "auto")).strip()
        backend = self._resolve_quick_tts_backend()
        fallback_order = ["edge_tts", "speech_dispatcher", "espeak_ng"]
        if selected in {"edge_tts", "speech_dispatcher", "espeak_ng"}:
            # 사용자 지정 엔진 단독 사용 기능.
            candidates = [selected]
        else:
            # auto 모드 한정 순차 폴백 기능.
            candidates: list[str] = []
            if backend in fallback_order:
                candidates.append(backend)
            candidates.extend([item for item in fallback_order if item not in candidates])

        started = False
        for candidate in candidates:
            if candidate == "edge_tts":
                started = self._speak_quick_edge_tts(text)
            elif candidate == "speech_dispatcher":
                started = self._speak_quick_spd(text)
            elif candidate == "espeak_ng":
                started = self._speak_quick_espeak(text)
            if started:
                break

        if not started:
            if hasattr(self, "shared_face_controller"):
                try:
                    self.shared_face_controller.on_tts_finished()
                except Exception:
                    pass
            return False

        # 실제 재생 완료 콜백이 없어 텍스트 길이 기반으로 speaking 상태를 자동 해제 기능.
        est_ms = max(1200, min(5500, 650 + (len(text) * 85)))
        self._face_voice_pause_until = time.monotonic() + (est_ms / 1000.0) + 0.4
        QTimer.singleShot(est_ms, self._finish_quick_tts)
        return True

    def _finish_quick_tts(self) -> None:
        if hasattr(self, "shared_face_controller"):
            try:
                self.shared_face_controller.on_tts_finished()
            except Exception:
                pass

    @staticmethod
    def _is_wakeword_detected(text: str) -> bool:
        return is_wakeword_detected(text)

    def _resolve_quick_tts_backend(self) -> str:
        selected = str(getattr(self, "_default_voice_backend", "auto"))
        if selected == "edge_tts" and self._find_edge_tts_executable() is not None:
            return "edge_tts"
        if selected == "speech_dispatcher" and shutil.which("spd-say"):
            return "speech_dispatcher"
        if selected == "espeak_ng" and shutil.which("espeak-ng"):
            return "espeak_ng"

        # auto 또는 선택 엔진 미설치 시 폴백 순서
        if self._find_edge_tts_executable() is not None:
            return "edge_tts"
        if shutil.which("spd-say"):
            return "speech_dispatcher"
        if shutil.which("espeak-ng"):
            return "espeak_ng"
        return "none"

    @staticmethod
    def _find_edge_tts_executable() -> str | None:
        edge_cli = shutil.which("edge-tts")
        if edge_cli:
            return edge_cli
        user_local = os.path.expanduser("~/.local/bin/edge-tts")
        if os.path.isfile(user_local) and os.access(user_local, os.X_OK):
            return user_local
        return None

    @staticmethod
    def _speak_quick_spd(text: str) -> bool:
        if not shutil.which("spd-say"):
            return False
        try:
            # spd-say가 무음으로 끝나는 환경을 줄이기 위해 dispatcher 데몬을 보장 기능.
            if shutil.which("speech-dispatcher"):
                probe = subprocess.run(["pgrep", "-f", "speech-dispatcher"], capture_output=True, text=True, timeout=1)
                if probe.returncode != 0:
                    subprocess.Popen(
                        ["speech-dispatcher", "--spawn"],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                    time.sleep(0.25)
            result = subprocess.run(["spd-say", text], capture_output=True, text=True, timeout=6)
            stderr_text = (result.stderr or "").strip().lower()
            if result.returncode != 0:
                return False
            if "can't connect to unix socket" in stderr_text or "connection refused" in stderr_text:
                return False
            return True
        except Exception:
            return False

    @staticmethod
    def _speak_quick_espeak(text: str) -> bool:
        if not shutil.which("espeak-ng"):
            return False
        try:
            subprocess.Popen(["espeak-ng", "-v", "ko", text])
            return True
        except Exception:
            return False

    def _speak_quick_edge_tts(self, text: str) -> bool:
        edge_cli = self._find_edge_tts_executable()
        if not edge_cli:
            return False

        player = None
        if shutil.which("gst-play-1.0"):
            player = "gst-play-1.0"
        elif shutil.which("ffplay"):
            player = "ffplay"
        if player is None:
            return False

        voice = str(getattr(self, "_default_edge_voice", "ko-KR-SunHiNeural")).strip() or "ko-KR-SunHiNeural"

        def _run() -> None:
            temp_path = ""
            try:
                with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
                    temp_path = tmp.name

                gen_cmd = [
                    edge_cli,
                    "--voice", voice,
                    "--text", text,
                    "--write-media", temp_path,
                ]
                result = subprocess.run(gen_cmd, capture_output=True, text=True, timeout=25)
                if result.returncode != 0:
                    return

                if player == "gst-play-1.0":
                    subprocess.run(["gst-play-1.0", "-q", temp_path], capture_output=True, text=True, timeout=30)
                else:
                    subprocess.run(["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", temp_path], capture_output=True, text=True, timeout=30)
            except Exception:
                return
            finally:
                if temp_path and os.path.exists(temp_path):
                    try:
                        os.remove(temp_path)
                    except OSError:
                        pass

        threading.Thread(target=_run, daemon=True).start()
        return True

    # ─── ROS2 상태 수신 ─────────────────────────────────────────────────────

    def _start_ros_bridge(self) -> None:
        """ROS2 상태 브리지 시작 및 Qt 시그널 연결 기능."""
        self._ros_bridge = RosStateBridge(parent=self)
        self._ros_bridge.state_changed.connect(self._on_ros_state_changed)
        self._ros_bridge.status_changed.connect(self._on_ros_status_changed)
        self._ros_bridge.start()

    def _on_ros_state_changed(self, state: str) -> None:
        """ROS2 AssistantState 변경 수신 시 GUI 업데이트."""
        # TODO(ros): state 토픽에 listening 시작/종료 구간 정보가 분리되면
        # on_listening_started/on_listening_finished 이벤트 연결 기능.
        _state_labels = {
            'SLEEPING':       ('💤 절전 모드', '#9CA3AF'),
            'IDLE':           ('🎤️ 호출어 대기 중...', '#10B981'),
            'LISTENING':      ('🎤️ 듣고 있어요...', '#3B82F6'),
            'PROCESSING':     ('🤔 이해 중...', '#F59E0B'),
            'RESPONDING':     ('💬 응답 중...', '#8B5CF6'),
            'ACTING':         ('🤖 동작 중...', '#EF4444'),
            'EXECUTING':      ('🤖 동작 중...', '#EF4444'),
            'WAITING_CONFIRMATION': ('🖐️ 확인 대기 중...', '#F59E0B'),
            'CHARGING':       ('⚡ 충전 중...', '#06B6D4'),
            'LOW_BATTERY_RESTRICTED': ('🔋 저전력 제한', '#F59E0B'),
            'ERROR':          ('⚠️ 오류 발생', '#EF4444'),
            'EMERGENCY_STOP': ('🛑 비상 정지', '#EF4444'),
        }
        label_text, color = _state_labels.get(state, ('🎤️ 호출어 대기 중...', '#10B981'))
        self.hdr_voiceState_Lbl.setText(label_text)
        self.hdr_voiceState_Lbl.setStyleSheet(
            f'font-size: 16px; font-weight: bold; color: {color};'
        )

        # 메인 얼굴/설정 탭 동일 FaceController 상태머신 공유 기능.
        self.shared_face_controller.on_robot_state_changed(state)

        # SLEEPING 상태 기반 FacePage 자동 전환 기능.
        if state == 'SLEEPING':
            self.switch_page(0)

    def _on_ros_status_changed(self, status: str) -> None:
        """status_text 로그 수신 (필요 시 팁소 또는 상태 표시에 사용할 수 있다)."""
        if hasattr(self, 'shared_face_controller'):
            status_upper = status.strip().upper()
            try:
                if status_upper.startswith('STATE:LISTENING'):
                    self.shared_face_controller.on_processing_finished()
                    self.shared_face_controller.on_tts_finished()
                    self.shared_face_controller.on_listening_started()
                elif status_upper.startswith('STATE:PROCESSING'):
                    self.shared_face_controller.on_listening_finished()
                    self.shared_face_controller.on_processing_started()
                elif status_upper.startswith('STATE:RESPONDING'):
                    self.shared_face_controller.on_processing_finished()
                    self.shared_face_controller.on_tts_started()
                elif status_upper.startswith('STATE:IDLE'):
                    self.shared_face_controller.on_processing_finished()
                    self.shared_face_controller.on_listening_finished()
                    self.shared_face_controller.on_tts_finished()
            except Exception:
                pass
        if hasattr(self, 'home_page'):
            self.home_page.update_robot_pose_from_status(status)

    def _refresh_runtime_capability_status(self) -> None:
        network_ok = self.is_network_available()
        mic_ok = self.is_microphone_available()
        self.hdr_network_lbl.setText("📶 연결됨" if network_ok else "📶 없음")
        self.hdr_network_lbl.setStyleSheet("color: #10B981;" if network_ok else "color: #EF4444;")
        self.hdr_mic_lbl.setText("🎙️ 인식됨" if mic_ok else "🎙️ 없음")
        self.hdr_mic_lbl.setStyleSheet("color: #10B981;" if mic_ok else "color: #EF4444;")

    @staticmethod
    def is_network_available() -> bool:
        try:
            socket.create_connection(("1.1.1.1", 53), timeout=1.5).close()
            return True
        except OSError:
            return False

    @staticmethod
    def is_microphone_available() -> bool:
        if shutil.which("arecord") is None:
            return False
        try:
            result = subprocess.run(["arecord", "-l"], capture_output=True, text=True, timeout=2)
            output = (result.stdout + result.stderr).lower()
            if "no soundcards found" in output:
                return False
            if result.returncode != 0:
                return False

            # Require at least one real capture device line.
            # Ignore virtual-only endpoints that often appear when no physical mic is connected.
            capture_lines = []
            for raw_line in result.stdout.splitlines():
                line = raw_line.strip().lower()
                has_card = "card " in line or "카드" in line
                has_device = "device " in line or "장치" in line
                if has_card and has_device:
                    capture_lines.append(line)
            if not capture_lines:
                return False

            real_lines = [line for line in capture_lines if "loopback" not in line and "dummy" not in line]
            return len(real_lines) > 0
        except Exception:
            return False

    def closeEvent(self, event):
        try:
            self._settings.setValue("window/fullscreen", self.isFullScreen())
            if not self.isFullScreen():
                self._settings.setValue("window/width", self.width())
                self._settings.setValue("window/height", self.height())
        except Exception:
            pass

        if hasattr(self, '_global_wakeword_controller'):
            try:
                self._global_wakeword_controller.stop()
            except Exception:
                pass

        if hasattr(self, 'shared_face_controller'):
            try:
                self.shared_face_controller.stop_timer()
            except Exception:
                pass
        if hasattr(self, 'battery_engine'):
            try:
                self.battery_engine.stop()
            except Exception:
                pass
        if hasattr(self, 'pose_engine'):
            try:
                self.pose_engine.stop()
            except Exception:
                pass
        if self._ros_bridge is not None:
            try:
                self._ros_bridge.stop()
            except Exception:
                pass
        super().closeEvent(event)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyleSheet(GLOBAL_STYLE)
    window = OmniMateMain()
    if getattr(window, "_pref_fullscreen", False):
        window.showFullScreen()
    else:
        window.show()
    sys.exit(app.exec())


def main() -> None:
    """ROS2 console_script 진입점."""
    app = QApplication(sys.argv)
    app.setStyleSheet(GLOBAL_STYLE)
    window = OmniMateMain()
    if getattr(window, "_pref_fullscreen", False):
        window.showFullScreen()
    else:
        window.show()
    sys.exit(app.exec())
