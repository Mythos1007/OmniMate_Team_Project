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


def _resolve_named_place_config_path() -> Path:
    env_path = os.environ.get("ASSISTANT_NAMED_PLACES_FILE", "").strip()
    if env_path:
        candidate = Path(env_path).expanduser().resolve()
        if candidate.exists() or candidate.parent.exists():
            return candidate

    candidates = (
        PACKAGE_PARENT.parent / "assistant_bringup" / "config" / "named_places_catalog.yaml",
        ROBOT_PACKAGE_PARENT / "assistant_robot" / "config" / "named_places.yaml",
    )
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


ROBOT_NAMED_PLACE_CONFIG = _resolve_named_place_config_path()
for candidate in (PACKAGE_PARENT, CURRENT_DIR, ROBOT_PACKAGE_PARENT):
    candidate_str = str(candidate)
    if candidate_str not in sys.path:
        sys.path.insert(0, candidate_str)

from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                               QHBoxLayout, QLabel, QPushButton, QStackedWidget,
                               QFrame)
from PySide6.QtCore import Qt, QTimer, QSettings, Signal
try:
    import rclpy
    from rclpy.action import ActionClient
    from rclpy.node import Node as RosNode
    from std_msgs.msg import Bool as RosBool
    from std_msgs.msg import Int32 as RosInt32
    from std_msgs.msg import String as RosString
    ROS_GUI_COMMANDS_AVAILABLE = True
except Exception:
    ActionClient = None
    RosNode = None
    RosBool = None
    RosInt32 = None
    RosString = None
    ROS_GUI_COMMANDS_AVAILABLE = False
try:
    from assistant_gui.engines.weather_engine import WeatherEngine
    from assistant_gui.engines.schedule_manager import ScheduleManager
    from assistant_gui.engines.alarm_manager import AlarmManager
    from assistant_gui.engines.battery_engine import BatteryEngine
    from assistant_gui.engines.pose_engine import PoseEngine
    from assistant_gui.runtime_paths import resolve_runtime_data_path
    from assistant_gui.integrations.ros_state_bridge import RosStateBridge
    from assistant_gui.integrations.data_sync_bridge import DataSyncBridge
    from assistant_gui.integrations.ros_runtime import get_shared_ros_runtime
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
    from engines.battery_engine import BatteryEngine
    from engines.pose_engine import PoseEngine
    from runtime_paths import resolve_runtime_data_path
    from integrations.ros_state_bridge import RosStateBridge
    from integrations.data_sync_bridge import DataSyncBridge
    from integrations.ros_runtime import get_shared_ros_runtime
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


class GuiRosCommandClient:
    def __init__(self) -> None:
        if not ROS_GUI_COMMANDS_AVAILABLE:
            raise RuntimeError("ROS command client unavailable")
        if not rclpy.ok():
            rclpy.init()
        geometry_msg_module = importlib.import_module("geometry_msgs.msg")
        self._pose_with_covariance_type = getattr(geometry_msg_module, "PoseWithCovarianceStamped")
        self._runtime = get_shared_ros_runtime()
        self._node = RosNode("assistant_gui_command_node")
        self._initial_pose_publisher = self._node.create_publisher(self._pose_with_covariance_type, "/initialpose", 10)
        self._guide_action_type = self._resolve_guide_action_type()
        self._guide_client = None
        if self._guide_action_type is not None:
            self._guide_client = ActionClient(self._node, self._guide_action_type, "/assistant/guide_to_named_place")
        self._publishers: dict[tuple[str, str], object] = {}
        self._runtime.add_node(self._node)
        self._pending_futures: list[object] = []
        self._active_goal_handles: list[object] = []
        self._active_result_futures: list[object] = []

    @staticmethod
    def _resolve_guide_action_type():
        for module_name in ("assistant_interfaces.action", "assistant_msgs.action"):
            try:
                guide_action_module = importlib.import_module(module_name)
                return getattr(guide_action_module, "GuideToNamedPlace")
            except Exception:
                continue
        return None

    def close(self) -> None:
        self._runtime.remove_node(self._node)

    def is_initial_pose_receiver_ready(self) -> bool:
        try:
            return self._initial_pose_publisher.get_subscription_count() > 0
        except Exception:
            return False

    def publish_initial_pose(self, *, x: float, y: float, yaw: float, frame_id: str = "map") -> None:
        message = self._pose_with_covariance_type()
        message.header.frame_id = frame_id
        message.header.stamp = self._node.get_clock().now().to_msg()
        message.pose.pose.position.x = float(x)
        message.pose.pose.position.y = float(y)
        message.pose.pose.position.z = 0.0
        message.pose.pose.orientation.z = math.sin(float(yaw) / 2.0)
        message.pose.pose.orientation.w = math.cos(float(yaw) / 2.0)
        covariance = [0.0] * 36
        covariance[0] = 0.25
        covariance[7] = 0.25
        covariance[35] = 0.06853891945200942
        message.pose.covariance = covariance
        self._initial_pose_publisher.publish(message)

    def _get_cached_publisher(self, topic_name: str, message_type: object):
        key = (str(topic_name), getattr(message_type, "__name__", str(message_type)))
        publisher = self._publishers.get(key)
        if publisher is None:
            publisher = self._node.create_publisher(message_type, topic_name, 10)
            self._publishers[key] = publisher
        return publisher

    @staticmethod
    def _wait_for_subscriber(publisher: object, *, timeout_sec: float) -> bool:
        deadline = time.monotonic() + max(0.0, float(timeout_sec))
        while time.monotonic() < deadline:
            try:
                if publisher.get_subscription_count() > 0:
                    return True
            except Exception:
                return False
            time.sleep(0.05)
        try:
            return publisher.get_subscription_count() > 0
        except Exception:
            return False

    def publish_string(self, topic_name: str, text: str, *, timeout_sec: float = 0.45) -> tuple[bool, str]:
        publisher = self._get_cached_publisher(topic_name, RosString)
        if not self._wait_for_subscriber(publisher, timeout_sec=timeout_sec):
            return False, "Timed out waiting for subscribers"
        message = RosString()
        message.data = str(text)
        publisher.publish(message)
        return True, "ok"

    def publish_bool(self, topic_name: str, value: bool, *, timeout_sec: float = 0.45) -> tuple[bool, str]:
        publisher = self._get_cached_publisher(topic_name, RosBool)
        if not self._wait_for_subscriber(publisher, timeout_sec=timeout_sec):
            return False, "Timed out waiting for subscribers"
        message = RosBool()
        message.data = bool(value)
        publisher.publish(message)
        return True, "ok"

    def publish_int(self, topic_name: str, value: int, *, timeout_sec: float = 0.45) -> tuple[bool, str]:
        publisher = self._get_cached_publisher(topic_name, RosInt32)
        if not self._wait_for_subscriber(publisher, timeout_sec=timeout_sec):
            return False, "Timed out waiting for subscribers"
        message = RosInt32()
        message.data = int(value)
        publisher.publish(message)
        return True, "ok"

    def send_guide_goal(self, place_name: str) -> tuple[bool, str]:
        if self._guide_client is None or self._guide_action_type is None:
            return False, "guide_to_named_place 액션 타입을 불러오지 못했습니다."
        if not self._guide_client.wait_for_server(timeout_sec=1.5):
            return False, "guide_to_named_place 액션 서버를 찾지 못했습니다."
        goal = self._guide_action_type.Goal()
        goal.place_name = str(place_name)
        future = self._guide_client.send_goal_async(goal)
        self._pending_futures.append(future)

        def _cleanup_done(done_future):
            try:
                goal_handle = done_future.result()
                if goal_handle is None:
                    return
                if not goal_handle.accepted:
                    print(f"[GuiRosCommandClient] guide goal rejected: {place_name}")
                    return

                self._active_goal_handles.append(goal_handle)
                result_future = goal_handle.get_result_async()
                self._active_result_futures.append(result_future)

                def _release_result(done_result_future):
                    try:
                        self._active_result_futures.remove(done_result_future)
                    except ValueError:
                        pass
                    try:
                        self._active_goal_handles.remove(goal_handle)
                    except ValueError:
                        pass

                result_future.add_done_callback(_release_result)
            except Exception as exc:
                print(f"[GuiRosCommandClient] guide goal error: {exc}")
            finally:
                try:
                    self._pending_futures.remove(done_future)
                except ValueError:
                    pass

        future.add_done_callback(_cleanup_done)
        return True, "ok"

    def cancel_active_guide_goals(self) -> tuple[bool, str]:
        cancelled_count = 0

        pending_futures = list(self._pending_futures)
        for future in pending_futures:
            try:
                if not future.done():
                    if future.cancel():
                        cancelled_count += 1
            except Exception:
                continue

        active_handles = list(self._active_goal_handles)
        for goal_handle in active_handles:
            try:
                goal_handle.cancel_goal_async()
                cancelled_count += 1
            except Exception:
                continue

        if cancelled_count <= 0:
            return False, "취소 가능한 직접 안내 goal이 없습니다."
        return True, f"직접 안내 goal {cancelled_count}건에 취소를 요청했습니다."


class OmniMateMain(QMainWindow):
    runtime_capability_status_ready = Signal(bool, bool)
    remote_audio_sync_finished = Signal(bool, bool)

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
        self._pending_mail_delivery_target = ""
        self._mail_confirmation_pending = False
        self._mail_returning_home = False
        self._last_runtime_status_text = ""
        self._temporary_navigation_place_name = ""
        self._initial_pose_published = False
        self._initial_pose_attempts = 0
        self._initial_pose_wait_checks = 0
        self._localized_pose_received = False
        self._ros_command_client = None
        self._runtime_status_probe_inflight = False
        self._data_sync_bridge = None
        self._data_sync_version = 0
        self._remote_audio_sync_inflight = False
        self._remote_robot_audio_available = False
        self._last_remote_audio_apply_ok = False
        self._startup_audio_sync_active = True
        self._startup_audio_sync_attempts = 0
        self._startup_audio_sync_max_attempts = 12
        self._last_robot_tts_config_payload = ""
        self._last_robot_tts_config_sent_at = 0.0
        self._pending_direct_navigation_timer = None
        self._pending_direct_navigation_target = ""
        self._require_goal_orientation = str(
            self._settings.value(
                "navigation/require_goal_orientation",
                os.getenv("ASSISTANT_NAV_REQUIRE_GOAL_ORIENTATION", "false"),
            )
        ).strip().lower() in {"1", "true", "yes", "on"}
        self.runtime_capability_status_ready.connect(self._apply_runtime_capability_status)
        self.remote_audio_sync_finished.connect(self._on_remote_audio_sync_finished)
        self._load_tts_templates()
        schedule_path = str(resolve_runtime_data_path(__file__, "ASSISTANT_SCHEDULES_FILE", "schedules.json"))
        self.schedule_mgr = ScheduleManager(
            filename=schedule_path,
            on_save=lambda _payload: self._on_runtime_data_saved("schedule"),
        )
        alarm_path = str(resolve_runtime_data_path(__file__, "ASSISTANT_ALARMS_FILE", "alarms.json"))
        self.alarm_mgr = AlarmManager(
            filename=alarm_path,
            on_save=lambda _payload: self._on_runtime_data_saved("alarm"),
        )
        self._start_ocr_warmup_if_available()

        self.weather_engine = WeatherEngine()
        self.weather_engine.start()

        self.battery_engine = BatteryEngine()
        self.battery_engine.battery_changed.connect(self._on_battery_changed)
        self.battery_engine.start()

        self.pose_engine = PoseEngine()
        self.pose_engine.pose_changed.connect(self._on_pose_changed)
        self.pose_engine.start()

        self.setWindowTitle("OmniMate - AI Robot Dashboard")
        self.setMinimumSize(960, 540)
        self.apply_window_size(1920, 1080)

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
            self._start_data_sync_bridge()

        self._status_poll_timer = QTimer(self)
        self._status_poll_timer.timeout.connect(self._refresh_runtime_capability_status)
        self._status_poll_timer.start(3000)
        self._refresh_runtime_capability_status()
        QTimer.singleShot(500, self._get_ros_command_client)

        self._restore_ui_preferences()
        self._schedule_startup_audio_sync(delay_ms=900)
        QTimer.singleShot(1200, self._sync_face_voice_loop)
        QTimer.singleShot(2200, self._auto_publish_initial_pose_if_needed)

    def _schedule_startup_audio_sync(self, *, delay_ms: int = 0) -> None:
        if not self._startup_audio_sync_active:
            return
        if self._startup_audio_sync_attempts >= self._startup_audio_sync_max_attempts:
            self._startup_audio_sync_active = False
            return
        QTimer.singleShot(max(0, int(delay_ms)), self._run_startup_audio_sync_once)

    def _run_startup_audio_sync_once(self) -> None:
        if not self._startup_audio_sync_active:
            return
        self._startup_audio_sync_attempts += 1
        self._sync_remote_audio_preferences(publish_preferences=True)

    def _start_ocr_warmup_if_available(self) -> None:
        try:
            from assistant_gui.engines.ocr_engine import OcrEngine
        except Exception:
            try:
                from engines.ocr_engine import OcrEngine
            except Exception:
                return
        OcrEngine.start_reader_warmup()

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
        self.apply_default_voice_backend(voice_backend, publish=False)
        self.apply_default_edge_voice(edge_voice, publish=False)
        self.apply_wakeword_reply_only(wakeword_reply_only)
        self._apply_preferred_wakeword_audio_mode()
        self.apply_person_greeting_enabled(
            str(self._settings.value("behavior/person_greeting_enabled", "true" if self._person_greeting_enabled else "false")),
            publish=False,
        )
        self.apply_robot_speaker_volume(robot_speaker_volume, publish=False)

        width = int(self._settings.value("window/width", 1920))
        height = int(self._settings.value("window/height", 1080))
        self.apply_window_size(width, height)
        self._pref_fullscreen = str(self._settings.value("window/fullscreen", "false")).lower() in {"1", "true", "yes"}

    def _apply_preferred_wakeword_audio_mode(self) -> None:
        prefer_pc_local_voice = self.is_microphone_available()
        self.apply_pc_local_voice_enabled(prefer_pc_local_voice)
        self.apply_robot_voice_input_enabled(False, publish=False)

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

    def _on_pose_changed(self, x_m: float, y_m: float, yaw_rad: float, source: str) -> None:
        if str(source).strip() == "/amcl_pose":
            self._localized_pose_received = True
        if hasattr(self, "home_page"):
            try:
                self.home_page.update_robot_pose(x_m, y_m, yaw_rad, source)
            except Exception:
                pass

    def apply_window_size(self, width: int, height: int) -> None:
        screen = self.screen()
        if screen is None:
            app = QApplication.instance()
            if app is not None:
                screen = app.primaryScreen()
        max_w = 3840
        max_h = 2160
        if screen is not None:
            geometry = screen.availableGeometry()
            max_w = max(1024, geometry.width() - 24)
            max_h = max(480, geometry.height() - 24)
        width = max(960, min(max_w, int(width)))
        min_balanced_height = max(540, min(max_h, int(width / 2.2)))
        height = max(min_balanced_height, min(max_h, int(height)))
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

    def apply_default_voice_backend(self, backend: str, *, publish: bool = True) -> tuple[bool, str]:
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
        if not publish:
            return True, f"기본 음성 엔진을 {normalized}로 저장했습니다."
        return self.publish_robot_tts_config(force=True)

    def apply_default_edge_voice(self, voice_name: str, *, publish: bool = True) -> tuple[bool, str]:
        voice = str(voice_name).strip() or "ko-KR-SunHiNeural"
        self._default_edge_voice = voice
        self._settings.setValue("voice/edge_voice", voice)
        if not publish:
            return True, f"기본 Edge 음성을 {voice}로 저장했습니다."
        return self.publish_robot_tts_config(force=True)

    @staticmethod
    def _is_male_edge_voice(voice_name: str) -> bool:
        voice = str(voice_name or "").strip()
        return any(token in voice for token in ("InJoon", "BongJin", "GookMin", "Hyunsu", "Guy", "Keita"))

    def build_robot_tts_config(self) -> dict[str, object]:
        selected_backend = str(getattr(self, "_default_voice_backend", "auto")).strip().lower()
        edge_voice = str(getattr(self, "_default_edge_voice", "ko-KR-SunHiNeural")).strip() or "ko-KR-SunHiNeural"
        fallback_voice_name = "male1" if self._is_male_edge_voice(edge_voice) else "female1"

        backend_mapping = {
            "auto": "edge_tts",
            "edge_tts": "edge_tts",
            "speech_dispatcher": "speech_dispatcher",
            "espeak_ng": "speech_dispatcher",
        }
        robot_backend = backend_mapping.get(selected_backend, "edge_tts")
        voice_name = edge_voice if robot_backend == "edge_tts" else fallback_voice_name

        return {
            "tts_backend": robot_backend,
            "voice_name": voice_name,
            "language": "ko",
            "fallback_voice_name": fallback_voice_name,
        }

    def publish_robot_tts_config(self, *, force: bool = True) -> tuple[bool, str]:
        payload = json.dumps(self.build_robot_tts_config(), ensure_ascii=False)
        now = time.monotonic()
        if not force and payload == self._last_robot_tts_config_payload and (now - self._last_robot_tts_config_sent_at) < 10.0:
            config = self.build_robot_tts_config()
            return True, f"로봇 TTS 설정 유지: {config.get('tts_backend')} / {config.get('voice_name')}"

        ok, message = self._publish_string_topic('/assistant/audio/tts_config', payload)
        if not ok:
            return ok, message
        self._last_robot_tts_config_payload = payload
        self._last_robot_tts_config_sent_at = now
        config = self.build_robot_tts_config()
        return True, f"로봇 TTS 설정 반영: {config.get('tts_backend')} / {config.get('voice_name')}"

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
        if self._face_voice_loop_enabled and bool(getattr(self, "_robot_voice_input_enabled", False)):
            # Keep a single wake/STT path active to avoid microphone contention.
            self.apply_robot_voice_input_enabled(False, publish=True)
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

    def publish_confirmation_signal(self) -> tuple[bool, str]:
        ok, message = self._publish_bool_topic('/assistant/confirmation', True)
        if ok:
            return True, 'ok'
        return False, '전달 확인 구독자 없음 또는 ROS 연결 불일치로 확인 신호를 보내지 못했습니다.'

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

    @staticmethod
    def _extract_delivery_target(command_text: str) -> str:
        text = str(command_text or "").strip()
        if not text:
            return ""
        delivery_keywords = r"(?:우편|배달|배송|전달)"
        match = re.search(
            rf"(?P<target>[가-힣A-Za-z0-9_ ]+?)(?:에|로|으로)\s*{delivery_keywords}",
            text,
        )
        if not match:
            return ""
        return str(match.group("target") or "").strip()

    def _handle_gui_delivery_request(self, command_text: str) -> tuple[bool, str, bool]:
        target = self._extract_delivery_target(command_text)
        if target:
            return False, "", False

        self.switch_page(7, manual=True)
        if hasattr(self, "home_page"):
            self.home_page.st_main.setText("우편 전달")
            self.home_page.st_sub.setText("수취인을 스캔할 수 있도록 우편 화면을 열었습니다.")
        return True, "우편 배달 요청을 받았습니다. 수취인을 스캔해주세요.", True

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

        if self.classify_tts_scenario(text) == "delivery_request":
            handled, message, local = self._handle_gui_delivery_request(text)
            if handled:
                return handled, message, local

        if self._is_always_local_voice_command(text):
            return True, self.build_local_voice_response(text), True

        submitted, message = self.submit_command_text(text)
        if not submitted and self._can_fallback_to_local_voice_command(text):
            return True, self.build_local_voice_response(text), True
        return submitted, message, False

    def prefers_robot_tts(self) -> bool:
        return bool(getattr(self, "_remote_robot_audio_available", False))

    def speak_text(self, text: str, *, target: str = "pc") -> tuple[bool, str]:
        # Topic delivery debugging mode: always use robot /assistant/speak path.
        _ = target
        return self.publish_tts_to_robot(text)

    def submit_command_text(self, command_text: str) -> tuple[bool, str]:
        text = str(command_text or "").strip()
        if not text:
            return False, "빈 명령입니다."
        return self._publish_string_topic("/assistant/command_text", text)

    def is_goal_orientation_required(self) -> bool:
        return bool(self._require_goal_orientation)

    def set_goal_orientation_required(self, enabled: bool) -> tuple[bool, str]:
        self._require_goal_orientation = bool(enabled)
        self._settings.setValue("navigation/require_goal_orientation", self._require_goal_orientation)
        return self._publish_goal_orientation_requirement(self._require_goal_orientation)

    def cancel_active_navigation(self) -> tuple[bool, str]:
        messages: list[str] = []

        if self._cancel_pending_direct_navigation_dispatch():
            messages.append("직접 안내 시작 예약을 취소했습니다.")
            return True, " | ".join(messages)

        command_client = self._get_ros_command_client()
        if command_client is not None:
            direct_ok, direct_message = command_client.cancel_active_guide_goals()
            if direct_ok:
                if direct_message:
                    messages.append(direct_message)
                return True, " | ".join(messages) if messages else "직접 안내 goal 취소를 요청했습니다."
            if direct_message:
                messages.append(direct_message)

        submit_ok, submit_message = self.submit_command_text("중지해줘")
        if submit_message:
            messages.append(submit_message)

        if submit_ok:
            return True, " | ".join(messages)
        return False, " | ".join(messages) if messages else "안내 취소 요청을 전송하지 못했습니다."

    def _publish_goal_orientation_requirement(self, enabled: bool) -> tuple[bool, str]:
        command_client = self._get_ros_command_client()
        if command_client is None:
            return False, "ROS direct navigation client를 초기화하지 못했습니다."
        return command_client.publish_bool("/assistant/navigation/require_goal_orientation", bool(enabled))

    def send_nav_to_coordinate(self, x_m: float, y_m: float) -> tuple[bool, str]:
        """지도 클릭 좌표를 직접 navigation target 문자열로 보내는 기능."""
        coordinate_target = f"navigate:x={float(x_m):.3f},y={float(y_m):.3f},frame=map"
        ok, message = self.start_direct_navigation_to_named_place(
            coordinate_target,
            announcement_text="안내를 시작합니다.",
            require_orientation=self._require_goal_orientation,
        )
        return (ok, message if not ok else "ok")

    def _build_named_place_navigation_announcement(self, place_name: str) -> str:
        name = str(place_name or "").strip()
        if not name:
            return "안내를 시작합니다."
        return f"{name}로 안내를 시작합니다."

    def send_nav_to_named_place(self, place_name: str, *, announcement_text: str | None = None) -> tuple[bool, str]:
        name = str(place_name or "").strip()
        if not name:
            return False, "장소 이름이 비어 있습니다."
        spoken_text = str(announcement_text).strip() if announcement_text is not None else self._build_named_place_navigation_announcement(name)
        ok, message = self.start_direct_navigation_to_named_place(
            name,
            announcement_text=spoken_text,
            require_orientation=self._require_goal_orientation,
        )
        if ok:
            return True, "ok"
        if spoken_text:
            self.publish_tts_to_robot(spoken_text)
        return self.submit_command_text(f"{name}으로 안내해줘")

    def _get_ros_command_client(self) -> GuiRosCommandClient | None:
        if self._ros_command_client is not None:
            return self._ros_command_client
        try:
            self._ros_command_client = GuiRosCommandClient()
        except Exception:
            self._ros_command_client = None
        return self._ros_command_client

    def start_direct_navigation_to_named_place(
        self,
        place_name: str,
        *,
        announcement_text: str = "안내를 시작합니다.",
        delay_ms: int = 350,
        require_orientation: bool | None = None,
    ) -> tuple[bool, str]:
        name = str(place_name or "").strip()
        if not name:
            return False, "장소 이름이 비어 있습니다."

        command_client = self._get_ros_command_client()
        if command_client is None:
            return False, "ROS direct navigation client를 초기화하지 못했습니다."

        orientation_required = self._require_goal_orientation if require_orientation is None else bool(require_orientation)
        publish_ok, publish_message = self._publish_goal_orientation_requirement(orientation_required)
        if not publish_ok:
            print(f"[OmniMateMain] navigation orientation mode publish failed: {publish_message}")

        effective_delay_ms = max(0, int(delay_ms))
        if announcement_text.strip():
            speak_ok, speak_message = self.publish_tts_to_robot(announcement_text)
            if not speak_ok:
                print(f"[OmniMateMain] navigation announcement publish failed: {speak_message}")
            effective_delay_ms = max(effective_delay_ms, self._estimate_navigation_tts_wait_ms(announcement_text))

        self._cancel_pending_direct_navigation_dispatch()
        self._pending_direct_navigation_target = name

        def _dispatch_goal() -> None:
            self._clear_pending_direct_navigation_dispatch()
            ok, message = command_client.send_guide_goal(name)
            if not ok:
                print(f"[OmniMateMain] direct navigation failed: {message}")

        timer = QTimer(self)
        timer.setSingleShot(True)
        timer.timeout.connect(_dispatch_goal)
        self._pending_direct_navigation_timer = timer
        timer.start(effective_delay_ms)
        return True, "ok"

    def _cancel_pending_direct_navigation_dispatch(self) -> bool:
        timer = getattr(self, "_pending_direct_navigation_timer", None)
        if timer is None:
            return False
        if not timer.isActive():
            self._clear_pending_direct_navigation_dispatch()
            return False
        timer.stop()
        self._clear_pending_direct_navigation_dispatch()
        return True

    def _clear_pending_direct_navigation_dispatch(self) -> None:
        timer = getattr(self, "_pending_direct_navigation_timer", None)
        self._pending_direct_navigation_timer = None
        self._pending_direct_navigation_target = ""
        if timer is not None:
            try:
                timer.deleteLater()
            except Exception:
                pass

    @staticmethod
    def _estimate_navigation_tts_wait_ms(announcement_text: str) -> int:
        # If explicitly configured, honor fixed delay for deterministic demos.
        configured = os.getenv("ASSISTANT_NAV_TTS_WAIT_MS", "").strip()
        if configured:
            try:
                return max(0, int(configured))
            except ValueError:
                pass

        text = str(announcement_text or "").strip()
        if not text:
            return 350

        # Rough Korean TTS estimate: base latency + per-character speech duration.
        estimated = 900 + (len(text) * 110)
        return max(1400, min(6500, estimated))

    @staticmethod
    def get_navigation_dwell_ms() -> int:
        configured = os.getenv("ASSISTANT_NAV_DWELL_MS", "").strip()
        if configured:
            try:
                return max(0, int(configured))
            except ValueError:
                pass
        return 1800

    def _load_named_place_document(self) -> dict:
        config_path = ROBOT_NAMED_PLACE_CONFIG
        if not config_path.exists():
            return {"medication_targets": [], "named_places": {}}
        loaded = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        return loaded if isinstance(loaded, dict) else {"medication_targets": [], "named_places": {}}

    def _mark_named_place_target_on_home_map(self, place_name: str) -> float | None:
        if not hasattr(self, 'home_page') or not hasattr(self.home_page, 'map_view'):
            return None
        place = self.get_named_place_lookup().get(str(place_name or '').strip())
        if not isinstance(place, dict):
            return None
        try:
            x_m = float(place.get('x', 0.0))
            y_m = float(place.get('y', 0.0))
        except (TypeError, ValueError):
            return None

        self.home_page.map_view.set_nav_target_preview(x_m, y_m)
        self.home_page.map_view.draw_path_to_target(x_m, y_m)
        try:
            self.home_page._active_navigation_label = str(place_name or '').strip()
        except Exception:
            pass
        return self.home_page.map_view.get_path_length_m()

    @staticmethod
    def _return_skip_distance_m() -> float:
        configured = os.getenv("ASSISTANT_RETURN_SKIP_DISTANCE_M", "0.35").strip()
        try:
            return max(0.0, float(configured))
        except ValueError:
            return 0.35

    def _distance_to_named_place_m(self, place_name: str) -> float | None:
        if not hasattr(self, 'home_page'):
            return None
        pose = getattr(self.home_page, '_last_pose', None)
        if pose is None or len(pose) != 2:
            return None

        place = self.get_named_place_lookup().get(str(place_name or '').strip())
        if not isinstance(place, dict):
            return None

        try:
            robot_x, robot_y = float(pose[0]), float(pose[1])
            place_x = float(place.get('x', 0.0))
            place_y = float(place.get('y', 0.0))
        except (TypeError, ValueError):
            return None

        return math.hypot(place_x - robot_x, place_y - robot_y)

    def _clear_home_navigation_context(self) -> None:
        if not hasattr(self, 'home_page') or self.home_page is None:
            return
        if hasattr(self.home_page, 'clear_navigation_activity'):
            self.home_page.clear_navigation_activity(clear_queue=False)

    def _finalize_mail_return_home(self) -> None:
        self._clear_home_navigation_context()
        if hasattr(self, 'home_page'):
            self.home_page.st_main.setText('대기 중...')
            self.home_page.st_sub.setText('명령을 기다리고 있습니다.')
            self.home_page.st_eta.setText('')
        self.switch_page(1, manual=True)
        self._mail_returning_home = False
        self._mail_confirmation_pending = False
        self._pending_mail_delivery_target = ''

    def _write_named_place_document(self, document: dict) -> None:
        config_path = ROBOT_NAMED_PLACE_CONFIG
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(
            yaml.safe_dump(document, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )

    def _upsert_temporary_navigation_place(self, x_m: float, y_m: float) -> tuple[bool, str]:
        document = self._load_named_place_document()
        named_places = document.get("named_places", {})
        if not isinstance(named_places, dict):
            named_places = {}

        place_name = "__tmp_click_target__"
        named_places[place_name] = {
            "source": "temporary",
            "frame_id": "map",
            "x": round(float(x_m), 3),
            "y": round(float(y_m), 3),
            "yaw": 0.0,
            "aliases": [place_name],
            "ocr_enabled": False,
        }
        document["named_places"] = named_places
        self._write_named_place_document(document)
        self._temporary_navigation_place_name = place_name
        return True, place_name

    def _cleanup_temporary_navigation_place(self) -> None:
        place_name = str(getattr(self, "_temporary_navigation_place_name", "")).strip()
        if not place_name:
            return

        document = self._load_named_place_document()
        named_places = document.get("named_places", {})
        if not isinstance(named_places, dict):
            self._temporary_navigation_place_name = ""
            return

        if place_name in named_places:
            named_places.pop(place_name, None)
            document["named_places"] = named_places
            self._write_named_place_document(document)
        self._temporary_navigation_place_name = ""

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
        preferred = [
            item["name"]
            for item in self.get_named_place_items()
            if item.get("name") and item.get("name") != "home" and item.get("source") != "temporary"
        ]
        if not preferred:
            preferred = [
                item["name"]
                for item in self.get_named_place_items()
                if item.get("name") and item.get("source") != "temporary"
            ]
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

        self._write_named_place_document(
            {
                "medication_targets": medication_targets,
                "named_places": named_places,
            }
        )

        if hasattr(self, "home_page") and self.home_page is not None and hasattr(self.home_page, "refresh_quick_destinations"):
            self.home_page.refresh_quick_destinations()
        return True, f"장소 {len(named_places)}개를 저장했습니다."

    def publish_tts_to_robot(self, text: str) -> tuple[bool, str]:
        self.publish_robot_tts_config(force=False)

        command_client = self._get_ros_command_client()
        if command_client is not None:
            try:
                ok, message = command_client.publish_string("/assistant/speak", text, timeout_sec=0.45)
                if ok:
                    return True, "ok"
                if self._is_subscriber_timeout(message):
                    cli_ok, cli_message = self._publish_string_via_cli("/assistant/speak", text)
                    if cli_ok:
                        return True, "ok"
                    return False, (
                        "구독자 없음: 로봇 tts_node 미실행 또는 ROS_DOMAIN_ID/RMW 불일치"
                        f" (CLI 재시도 실패: {cli_message})"
                    )
                return False, message
            except Exception as exc:
                message = str(exc)
                if "Connection refused" in message or "연결이 거부" in message:
                    return False, "로봇 연결이 거부되었습니다. 로봇측 ROS2 노드/네트워크/도메인(ROS_DOMAIN_ID=142) 설정을 확인하세요."
                return False, message

        ok, message = self._publish_string_via_cli("/assistant/speak", text)
        if ok:
            return True, "ok"
        if self._is_subscriber_timeout(message):
            return False, "구독자 없음: 로봇 tts_node 미실행 또는 ROS_DOMAIN_ID/RMW 불일치"
        if "Connection refused" in message or "연결이 거부" in message:
            return False, "로봇 연결이 거부되었습니다. 로봇측 ROS2 노드/네트워크/도메인(ROS_DOMAIN_ID=142) 설정을 확인하세요."
        return False, message

    def _publish_string_topic(self, topic_name: str, text: str) -> tuple[bool, str]:
        command_client = self._get_ros_command_client()
        if command_client is not None:
            try:
                ok, message = command_client.publish_string(topic_name, text, timeout_sec=0.45)
                if ok:
                    return True, "ok"
                if self._is_subscriber_timeout(message):
                    cli_ok, cli_message = self._publish_string_via_cli(topic_name, text)
                    if cli_ok:
                        return True, "ok"
                    err = (
                        "명령 구독자 없음: ROS 노드가 아직 안 떠 있거나 "
                        "orchestrator_node/intent_parser_node 미실행, 또는 ROS_DOMAIN_ID/RMW 설정이 다릅니다."
                    )
                    if topic_name == "/assistant/audio/tts_config":
                        err = "로봇 오디오 구독자 없음: tts_node 미실행 또는 ROS_DOMAIN_ID/RMW 설정 불일치"
                    return False, f"{err} (CLI 재시도 실패: {cli_message})"
                return False, message
            except Exception as exc:
                message = str(exc)
                if "Connection refused" in message or "연결이 거부" in message:
                    return False, "ROS 연결이 거부되었습니다. 로봇측 ROS2 노드/네트워크/도메인 설정을 확인하세요."
                return False, message

        ok, message = self._publish_string_via_cli(topic_name, text)
        if ok:
            return True, "ok"
        if self._is_subscriber_timeout(message):
            err = (
                "명령 구독자 없음: ROS 노드가 아직 안 떠 있거나 "
                "orchestrator_node/intent_parser_node 미실행, 또는 ROS_DOMAIN_ID/RMW 설정이 다릅니다."
            )
            if topic_name == "/assistant/audio/tts_config":
                err = "로봇 오디오 구독자 없음: tts_node 미실행 또는 ROS_DOMAIN_ID/RMW 설정 불일치"
            return False, err
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
        command_client = self._get_ros_command_client()
        if command_client is not None:
            try:
                ok, message = command_client.publish_int(topic_name, value, timeout_sec=0.45)
                if ok:
                    return True, f"로봇 스피커 볼륨을 {int(value)}%로 적용했습니다."
                if self._is_subscriber_timeout(message):
                    cli_ok, cli_message = self._publish_int_via_cli(topic_name, int(value))
                    if cli_ok:
                        return True, f"로봇 스피커 볼륨을 {int(value)}%로 적용했습니다."
                    return False, (
                        "로봇 오디오 구독자 없음: tts_node 미실행 또는 ROS_DOMAIN_ID/RMW 설정 불일치"
                        f" (CLI 재시도 실패: {cli_message})"
                    )
                return False, message
            except Exception as exc:
                message = str(exc)
                if "Connection refused" in message or "연결이 거부" in message:
                    return False, "로봇 연결이 거부되었습니다. 로봇측 ROS2 오디오 노드/네트워크/도메인 설정을 확인하세요."
                return False, message

        ok, message = self._publish_int_via_cli(topic_name, int(value))
        if ok:
            return True, f"로봇 스피커 볼륨을 {int(value)}%로 적용했습니다."
        if self._is_subscriber_timeout(message):
            return False, "로봇 오디오 구독자 없음: tts_node 미실행 또는 ROS_DOMAIN_ID/RMW 설정 불일치"
        if "Connection refused" in message or "연결이 거부" in message:
            return False, "로봇 연결이 거부되었습니다. 로봇측 ROS2 오디오 노드/네트워크/도메인 설정을 확인하세요."
        return False, message

    def _publish_bool_topic(self, topic_name: str, value: bool) -> tuple[bool, str]:
        command_client = self._get_ros_command_client()
        if command_client is not None:
            try:
                ok, message = command_client.publish_bool(topic_name, value, timeout_sec=0.45)
                if ok:
                    return True, "ok"
                if self._is_subscriber_timeout(message):
                    cli_ok, cli_message = self._publish_bool_via_cli(topic_name, bool(value))
                    if cli_ok:
                        return True, "ok"
                    return False, (
                        "로봇 오디오 제어 구독자 없음: 로봇 오디오 노드 미실행 또는 ROS 설정 불일치"
                        f" (CLI 재시도 실패: {cli_message})"
                    )
                return False, message
            except Exception as exc:
                message = str(exc)
                if "Connection refused" in message or "연결이 거부" in message:
                    return False, "로봇 연결이 거부되었습니다. 로봇측 ROS2 오디오 노드/네트워크/도메인 설정을 확인하세요."
                return False, message

        ok, message = self._publish_bool_via_cli(topic_name, bool(value))
        if ok:
            return True, "ok"
        if self._is_subscriber_timeout(message):
            return False, "로봇 오디오 제어 구독자 없음: 로봇 오디오 노드 미실행 또는 ROS 설정 불일치"
        if "Connection refused" in message or "연결이 거부" in message:
            return False, "로봇 연결이 거부되었습니다. 로봇측 ROS2 오디오 노드/네트워크/도메인 설정을 확인하세요."
        return False, message

    @staticmethod
    def _is_subscriber_timeout(message: str) -> bool:
        return "Timed out waiting for subscribers" in str(message or "")

    def _publish_string_via_cli(self, topic_name: str, text: str) -> tuple[bool, str]:
        if not shutil.which("ros2"):
            return False, "ros2 CLI를 찾을 수 없습니다."
        payload = json.dumps({"data": str(text)}, ensure_ascii=False)
        cmd = [
            "ros2", "topic", "pub", "--once",
            "-w", "1",
            str(topic_name), "std_msgs/msg/String", payload,
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=2, env=self._build_ros_cli_env())
            if result.returncode != 0:
                return False, (result.stderr.strip() or result.stdout.strip() or "ros2 topic pub 실패")
            return True, "ok"
        except Exception as exc:
            return False, str(exc)

    def _publish_int_via_cli(self, topic_name: str, value: int) -> tuple[bool, str]:
        if not shutil.which("ros2"):
            return False, "ros2 CLI를 찾을 수 없습니다."
        payload = json.dumps({"data": int(value)}, ensure_ascii=False)
        cmd = [
            "ros2", "topic", "pub", "--once",
            "-w", "1",
            str(topic_name), "std_msgs/msg/Int32", payload,
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=2, env=self._build_ros_cli_env())
            if result.returncode != 0:
                return False, (result.stderr.strip() or result.stdout.strip() or "ros2 topic pub 실패")
            return True, "ok"
        except Exception as exc:
            return False, str(exc)

    def _publish_bool_via_cli(self, topic_name: str, value: bool) -> tuple[bool, str]:
        if not shutil.which("ros2"):
            return False, "ros2 CLI를 찾을 수 없습니다."
        payload = json.dumps({"data": bool(value)}, ensure_ascii=False)
        cmd = [
            "ros2", "topic", "pub", "--once",
            "-w", "1",
            str(topic_name), "std_msgs/msg/Bool", payload,
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=2, env=self._build_ros_cli_env())
            if result.returncode != 0:
                return False, (result.stderr.strip() or result.stdout.strip() or "ros2 topic pub 실패")
            return True, "ok"
        except Exception as exc:
            return False, str(exc)

    def _sync_remote_audio_preferences(self, *, publish_preferences: bool = True) -> None:
        if self._remote_audio_sync_inflight:
            return

        self._remote_audio_sync_inflight = True
        requested_robot_voice_input = bool(self._robot_voice_input_enabled)
        requested_person_greeting = bool(self._person_greeting_enabled)

        def _worker() -> None:
            remote_input_available = False
            remote_tts_available = False
            apply_ok = not publish_preferences
            try:
                remote_input_available = self._query_remote_bool_topic('/assistant/audio/robot/input_available')
                remote_tts_available = (
                    self._query_topic_has_subscriber('/assistant/speak')
                    or self._query_topic_has_subscriber('/assistant/audio/tts_config')
                )
                if publish_preferences:
                    effective_robot_voice_input = requested_robot_voice_input and remote_input_available
                    ok_voice, _ = self.publish_robot_voice_input_enabled(effective_robot_voice_input)
                    ok_greeting, _ = self.publish_person_greeting_enabled(requested_person_greeting)
                    ok_tts, _ = self.publish_robot_tts_config(force=True)
                    apply_ok = bool(ok_voice and ok_greeting and ok_tts)
            except Exception:
                pass
            finally:
                self._last_remote_audio_apply_ok = apply_ok
                self.remote_audio_sync_finished.emit(remote_input_available, remote_tts_available)

        threading.Thread(target=_worker, daemon=True).start()

    def _on_remote_audio_sync_finished(self, remote_input_available: bool, remote_tts_available: bool) -> None:
        self._remote_audio_sync_inflight = False
        self._remote_robot_audio_available = bool(remote_tts_available)
        if not remote_input_available:
            self.apply_robot_voice_input_enabled(False, publish=False)
        if self._startup_audio_sync_active:
            startup_sync_done = bool(
                remote_input_available
                and remote_tts_available
                and self._last_remote_audio_apply_ok
            )
            if startup_sync_done:
                self._startup_audio_sync_active = False
            else:
                self._schedule_startup_audio_sync(delay_ms=1800)

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
                timeout=1.5,
                env=self._build_ros_cli_env(),
            )
            if result.returncode != 0:
                return False
            output = (result.stdout or "").lower()
            return "data: true" in output
        except Exception:
            return False

    def _query_topic_has_subscriber(self, topic_name: str) -> bool:
        if not shutil.which("ros2"):
            return False

        cmd = ["ros2", "topic", "info", topic_name]
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=1.5,
                env=self._build_ros_cli_env(),
            )
            if result.returncode != 0:
                return False
            output = (result.stdout or "").lower()
            for line in output.splitlines():
                normalized = line.strip()
                if normalized.startswith('subscription count:'):
                    try:
                        return int(normalized.split(':', 1)[1].strip()) > 0
                    except ValueError:
                        return False
            return False
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

    def _resolve_initial_pose(self) -> tuple[float, float, float, str]:
        home = self.get_named_place_lookup().get("home", {})
        frame_id = str(home.get("frame_id", "map")).strip() or "map"
        try:
            x_value = float(home.get("x", 0.0))
            y_value = float(home.get("y", 0.0))
            yaw_value = float(home.get("yaw", math.radians(64.0)))
        except (TypeError, ValueError):
            x_value = 0.0
            y_value = 0.0
            yaw_value = math.radians(64.0)

        if not home:
            x_value = 0.0
            y_value = 0.0
            yaw_value = math.radians(64.0)
        return x_value, y_value, yaw_value, frame_id

    def _auto_publish_initial_pose_if_needed(self) -> None:
        if self._localized_pose_received:
            self._initial_pose_published = True
            return
        if self._initial_pose_attempts >= 4:
            return
        if str(os.getenv("ASSISTANT_AUTO_INITIAL_POSE", "1")).strip().lower() not in {"1", "true", "yes", "on"}:
            return
        command_client = self._get_ros_command_client()
        if command_client is None:
            return
        if not command_client.is_initial_pose_receiver_ready():
            self._initial_pose_wait_checks += 1
            if self._initial_pose_wait_checks <= 30:
                QTimer.singleShot(1000, self._auto_publish_initial_pose_if_needed)
            return
        x_value, y_value, yaw_value, frame_id = self._resolve_initial_pose()
        try:
            command_client.publish_initial_pose(x=x_value, y=y_value, yaw=yaw_value, frame_id=frame_id)
            self._initial_pose_attempts += 1
            self._initial_pose_wait_checks = 0
            if self._localized_pose_received:
                self._initial_pose_published = True
                return
            QTimer.singleShot(1500, self._auto_publish_initial_pose_if_needed)
        except Exception as exc:
            print(f"[OmniMateMain] initial pose publish failed: {exc}")

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

    def _start_data_sync_bridge(self) -> None:
        self._data_sync_bridge = DataSyncBridge(parent=self)
        self._data_sync_bridge.snapshot_requested.connect(self._on_data_sync_request)
        self._data_sync_bridge.start()
        QTimer.singleShot(1200, lambda: self._publish_runtime_data_snapshot("startup"))

    def _collect_runtime_data_snapshot(self) -> dict[str, object]:
        schedules = dict(getattr(self.schedule_mgr, "schedules", {}) or {})
        alarms = list(getattr(self.alarm_mgr, "alarms", []) or [])

        medications: dict[str, object] = {"last_run_date": "", "meds": []}
        if hasattr(self, "medication_page") and hasattr(self.medication_page, "med_mgr"):
            med_mgr = self.medication_page.med_mgr
            medications = {
                "last_run_date": str(getattr(med_mgr, "last_run_date", "") or ""),
                "meds": list(getattr(med_mgr, "meds", []) or []),
            }

        self._data_sync_version += 1
        return {
            "source": "pc_gui",
            "version": self._data_sync_version,
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "schedules": schedules,
            "alarms": alarms,
            "medications": medications,
        }

    def _publish_runtime_data_snapshot(self, reason: str) -> None:
        if self._data_sync_bridge is None:
            return
        payload = self._collect_runtime_data_snapshot()
        payload["reason"] = str(reason or "")
        self._data_sync_bridge.publish_snapshot(payload)

    def _on_runtime_data_saved(self, source: str) -> None:
        self._publish_runtime_data_snapshot(f"save:{source}")

    def _on_data_sync_request(self, request_id: str) -> None:
        request = str(request_id or "").strip()
        self._publish_runtime_data_snapshot(f"request:{request or 'unknown'}")

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
        elif state == 'WAITING_CONFIRMATION' and hasattr(self, 'gesture_page'):
            target, kind = self._resolve_confirmation_context()
            if hasattr(self.gesture_page, 'set_confirmation_context'):
                self.gesture_page.set_confirmation_context(target, kind)
            else:
                self.gesture_page.set_target(target)
            self.switch_page(12, manual=True)
        elif state == 'IDLE' and self._mail_returning_home:
            self._finalize_mail_return_home()
        elif state == 'IDLE' and getattr(self, '_pending_mail_delivery_target', '') and not self._mail_confirmation_pending:
            target = str(getattr(self, '_pending_mail_delivery_target', '')).strip()
            if target and hasattr(self, 'home_page'):
                self.home_page.st_main.setText(f"{target} 배송 완료")
                self.home_page.st_sub.setText(f"{target}에 우편 배달을 완료했습니다.")
            elif hasattr(self, 'home_page'):
                self.home_page.st_main.setText("배송 완료")
                self.home_page.st_sub.setText("우편 배달이 완료되었습니다.")
            self.switch_page(1, manual=True)
            self._pending_mail_delivery_target = ""

        if state in {'IDLE', 'ERROR'}:
            self._cleanup_temporary_navigation_place()

    def _on_ros_status_changed(self, status: str) -> None:
        """status_text 로그 수신 (필요 시 팁소 또는 상태 표시에 사용할 수 있다)."""
        status_text = str(status or '').strip()
        if not status_text:
            return
        self._last_runtime_status_text = status_text
        self._maybe_show_confirmation_page_from_status(status_text)
        if hasattr(self, 'shared_face_controller'):
            status_upper = status_text.upper()
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

        if not status_text.upper().startswith('STATE:'):
            self._apply_runtime_status_text(status_text)

    def _maybe_show_confirmation_page_from_status(self, status_text: str) -> None:
        text = str(status_text or '').strip()
        if not text or not hasattr(self, 'gesture_page'):
            return

        waiting_keywords = (
            '복약 확인 응답을 기다리는 중입니다',
            '전달 확인 응답을 기다리는 중입니다',
            '알림 확인 응답을 기다리는 중입니다',
            '확인 응답을 기다리는 중입니다',
            '확인 대기',
        )
        if not any(keyword in text for keyword in waiting_keywords):
            return

        kind = 'generic'
        if '복약 확인' in text:
            kind = 'medication'
        elif '전달 확인' in text or '배송 확인' in text:
            kind = 'delivery'
        elif '알림 확인' in text or '알람 확인' in text:
            kind = 'alarm'

        target = ''
        match = re.search(r'대상:\s*([^·]+)', text)
        if match:
            target = match.group(1).strip()
        if not target:
            target = str(getattr(self, '_pending_mail_delivery_target', '')).strip() or '현재 대상'

        current_index = self.stacked_widget.currentIndex() if hasattr(self, 'stacked_widget') else -1
        if current_index == 12 and getattr(self.gesture_page, 'is_returning', False):
            return

        if hasattr(self.gesture_page, 'set_confirmation_context'):
            self.gesture_page.set_confirmation_context(target, kind)
        else:
            self.gesture_page.set_target(target)
        self.switch_page(12, manual=True)

    def _resolve_confirmation_context(self) -> tuple[str, str]:
        text = str(getattr(self, '_last_runtime_status_text', '')).strip()
        target = str(getattr(self, '_pending_mail_delivery_target', '')).strip()

        kind = 'generic'
        if self._mail_confirmation_pending and target:
            kind = 'delivery'
        elif '복약 확인' in text:
            kind = 'medication'
        elif '전달 확인' in text or '배송 확인' in text:
            kind = 'delivery'
        elif '알림 확인' in text or '알람 확인' in text:
            kind = 'alarm'

        if not target and text:
            match = re.search(r'대상:\s*([^·]+)', text)
            if match:
                target = match.group(1).strip()

        if not target:
            target = '현재 대상'

        return target, kind

    def _apply_runtime_status_text(self, status_text: str) -> None:
        text = str(status_text or '').strip()
        if not text:
            return

        ignored_prefixes = (
            '로봇 TTS 설정 적용:',
            '음성 응답 처리 시작:',
            '음성 응답 출력 중:',
            '로봇 스피커 볼륨',
        )
        if any(text.startswith(prefix) for prefix in ignored_prefixes):
            return

        if hasattr(self, 'home_page') and self.home_page is not None:
            if hasattr(self.home_page, 'has_navigation_activity') and self.home_page.has_navigation_activity():
                # Keep navigation/queue context visible while movement is active.
                return
            self.home_page.st_main.setText(self._headline_from_runtime_status(text))
            self.home_page.st_sub.setText(text)

    @staticmethod
    def _build_alarm_arrival_text(meta: dict[str, object]) -> str:
        content = str(meta.get('alarm_content') or meta.get('content') or '').strip()
        hour = meta.get('hour')
        minute = meta.get('minute')
        try:
            if hour is not None and minute is not None:
                return f"{int(hour)}시 {int(minute):02d}분, {content or '설정된 알람 시간입니다.'}"
        except (TypeError, ValueError):
            pass
        if content:
            return f"알람 내용은 {content} 입니다."
        return '설정된 알람 시간입니다.'

    @staticmethod
    def _build_medication_arrival_text(meta: dict[str, object], fallback_label: str) -> str:
        person_name = str(meta.get('person_name') or meta.get('target_name') or '').strip()
        if not person_name:
            person_name = str(fallback_label or '').strip()
        if not person_name:
            return '약 드실 시간입니다.'
        if person_name.endswith('님'):
            return f'{person_name} 약 드실 시간입니다.'
        return f'{person_name}님 약 드실 시간입니다.'

    def on_navigation_arrived(self, current_label: str, meta: dict[str, object] | None = None, next_label: str = '') -> None:
        label = str(current_label or '').strip() or '현재 목표'
        payload = dict(meta or {})
        kind = str(payload.get('kind') or '').strip().lower()

        messages: list[str] = [f'{label} 안내를 종료합니다.']
        if kind == 'alarm':
            messages.append(self._build_alarm_arrival_text(payload))
        elif kind in {'medication', 'medicine'}:
            messages.append(self._build_medication_arrival_text(payload, label))

        upcoming = str(next_label or '').strip()
        if upcoming:
            messages.append(f'다음 목표 {upcoming}로 안내를 시작합니다.')

        self.publish_tts_to_robot(' '.join(part for part in messages if part).strip())

    @staticmethod
    def _headline_from_runtime_status(status_text: str) -> str:
        text = str(status_text or '').strip()
        if not text:
            return '대기 중...'
        if '복약' in text:
            return '복약 진행 중'
        if '우편' in text or '전달' in text or '배송' in text:
            return '우편 전달 진행 중'
        if '알람' in text or '알림' in text:
            return '알람 진행 중'
        if '복귀' in text:
            return '복귀 중'
        if '충전' in text:
            return '충전 중'
        if '오류' in text:
            return '오류 상태'
        if '대기 중' in text:
            return '대기 중...'
        return '현재 상태'

    def begin_mail_delivery(self, target: str) -> tuple[bool, str]:
        target_name = str(target or '').strip()
        if not target_name:
            return False, '배송 대상이 비어 있습니다.'
        place = self.get_named_place_lookup().get(target_name)
        if not isinstance(place, dict):
            return False, f"'{target_name}' 장소 설정을 찾지 못했습니다."
        self._pending_mail_delivery_target = target_name
        self._mail_confirmation_pending = True
        self._mail_returning_home = False
        path_len = self._mark_named_place_target_on_home_map(target_name)
        if hasattr(self, 'home_page'):
            self.home_page.st_main.setText(f"{target_name} 배송 준비 중")
            if path_len is not None and path_len >= 0.1:
                self.home_page.st_sub.setText(f"목표까지 약 {path_len:.1f}m")
            else:
                self.home_page.st_sub.setText(f"현재 {target_name} 방향입니다.")
        ok, message = self.submit_command_text(f'{target_name}으로 배송해줘')
        if not ok:
            self._pending_mail_delivery_target = ""
            self._mail_confirmation_pending = False
            return False, message
        return True, 'ok'

    def _resolve_home_place_name(self) -> str | None:
        lookup = self.get_named_place_lookup()
        if 'home' in lookup:
            return 'home'
        for item in self.get_named_place_items():
            aliases = item.get('aliases', []) or []
            alias_set = {str(alias).strip() for alias in aliases if str(alias).strip()}
            if {'집', '대기위치', 'home'} & alias_set:
                return str(item.get('name', '')).strip() or None
        return None

    def begin_mail_return_home(self) -> tuple[bool, str]:
        home_place = self._resolve_home_place_name()
        if not home_place:
            return False, 'home 장소 설정을 찾지 못했습니다.'

        near_home_distance = self._distance_to_named_place_m(home_place)
        if near_home_distance is not None and near_home_distance <= self._return_skip_distance_m():
            self._mail_returning_home = False
            self._clear_home_navigation_context()
            return True, f'이미 대기 위치 근처({near_home_distance:.2f}m)라 복귀를 생략합니다.'

        ok, message = self.start_direct_navigation_to_named_place(
            home_place,
            announcement_text='대기 위치로 복귀를 시작합니다.',
        )
        if not ok:
            fallback_ok, fallback_message = self.submit_command_text('복귀해줘')
            if not fallback_ok:
                return False, f"{message} / fallback 실패: {fallback_message}"
        self._mail_returning_home = True
        path_len = self._mark_named_place_target_on_home_map(home_place)
        if hasattr(self, 'home_page'):
            self.home_page.st_main.setText('복귀 중...')
            if path_len is not None and path_len >= 0.1:
                self.home_page.st_sub.setText(f'대기 위치까지 약 {path_len:.1f}m')
            else:
                self.home_page.st_sub.setText('대기 위치로 복귀하고 있습니다.')
        return True, 'ok'

    def confirm_mail_delivery_and_return_home(self) -> tuple[bool, str]:
        ok, message = self.publish_confirmation_signal()
        self._mail_confirmation_pending = False
        self._mail_returning_home = False
        self._clear_home_navigation_context()
        if not ok:
            return True, f'전달 확인 신호 전송 실패(경고): {message}'
        return True, 'ok'

    def _refresh_runtime_capability_status(self) -> None:
        if self._runtime_status_probe_inflight:
            return

        self._runtime_status_probe_inflight = True

        def _worker() -> None:
            try:
                network_ok = self.is_network_available()
                mic_ok = self.is_microphone_available()
            except Exception:
                network_ok = False
                mic_ok = False
            self.runtime_capability_status_ready.emit(network_ok, mic_ok)

        threading.Thread(target=_worker, daemon=True).start()

    def _apply_runtime_capability_status(self, network_ok: bool, mic_ok: bool) -> None:
        self._runtime_status_probe_inflight = False
        self.hdr_network_lbl.setText("📶 연결됨" if network_ok else "📶 없음")
        self.hdr_network_lbl.setStyleSheet("color: #10B981;" if network_ok else "color: #EF4444;")
        self.hdr_mic_lbl.setText("🎙️ 인식됨" if mic_ok else "🎙️ 없음")
        self.hdr_mic_lbl.setStyleSheet("color: #10B981;" if mic_ok else "color: #EF4444;")
        if network_ok:
            self._sync_remote_audio_preferences(publish_preferences=False)
        else:
            self._remote_robot_audio_available = False

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
        if self._data_sync_bridge is not None:
            try:
                self._data_sync_bridge.stop()
            except Exception:
                pass
        if self._ros_command_client is not None:
            try:
                self._ros_command_client.close()
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
