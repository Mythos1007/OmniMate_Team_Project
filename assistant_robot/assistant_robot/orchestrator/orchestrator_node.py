from __future__ import annotations

import json
import logging
import time
from pathlib import Path

from geometry_msgs.msg import Twist
from std_msgs.msg import Bool, Float32, String

import rclpy
from rclpy.node import Node

from assistant_robot.adapters.action_navigation_controller import ActionNavigationController
from assistant_robot.adapters.place_resolving_navigation_controller import PlaceResolvingNavigationController
from assistant_robot.adapters.ros_confirmation_service import RosConfirmationService
from assistant_robot.adapters.ros_tts_provider import RosTopicTTSProvider
from assistant_robot.constants import (
    ASSISTANT_COMMAND_TOPIC,
    ASSISTANT_DATA_SYNC_REQUEST_TOPIC,
    ASSISTANT_DATA_SYNC_SNAPSHOT_TOPIC,
    ASSISTANT_LEGACY_GUI_COMMAND_TOPIC,
    ASSISTANT_LEGACY_VOICE_TEXT_TOPIC,
    ASSISTANT_PERSON_GREETING_ENABLED_TOPIC,
    ASSISTANT_PERSON_RECOGNIZED_TOPIC,
    ASSISTANT_ROBOT_COMMAND_TOPIC,
)
from assistant_robot.demo import build_mock_orchestrator
from assistant_robot.services.runtime_data_service import RuntimeDataService


class OrchestratorNode(Node):
    """기능: ROS topic과 순수 Python orchestrator를 연결하는 브리지 노드."""

    def __init__(self) -> None:
        super().__init__("omni_orchestrator_node")
        self.declare_parameter("tts_profile", "demo")
        self.declare_parameter('greeting_cooldown_seconds', 30)
        self.declare_parameter('greeting_once_per_user', True)
        self.declare_parameter('greeting_forward_speed_mps', 0.08)
        self.declare_parameter('greeting_forward_duration_sec', 1.6)
        self.declare_parameter('greeting_turn_speed_radps', 1.4)
        self.declare_parameter('greeting_turn_duration_sec', 4.5)
        tts_profile = str(self.get_parameter("tts_profile").value)
        self._runtime_data_service = RuntimeDataService()
        self._latest_sync_version = -1
        navigation_controller = PlaceResolvingNavigationController(ActionNavigationController(self))
        self._speak_publisher = self.create_publisher(String, '/assistant/speak', 10)
        self._cmd_vel_publisher = self.create_publisher(Twist, '/assistant/cmd_vel', 10)
        self._orchestrator, _ = build_mock_orchestrator(
            tts_profile=tts_profile,
            navigation_controller=navigation_controller,
            confirmation_service=RosConfirmationService(self),
            tts_provider=RosTopicTTSProvider(self),
            greeting_cooldown_seconds=int(self.get_parameter('greeting_cooldown_seconds').value),
            greeting_once_per_user=bool(self.get_parameter('greeting_once_per_user').value),
            runtime_data_service=self._runtime_data_service,
        )
        self._status_publisher = self.create_publisher(String, "/assistant/orchestrator/status", 10)
        self._data_sync_request_publisher = self.create_publisher(String, ASSISTANT_DATA_SYNC_REQUEST_TOPIC, 10)
        self.create_subscription(String, ASSISTANT_COMMAND_TOPIC, self._on_command_text, 10)
        self.create_subscription(String, ASSISTANT_ROBOT_COMMAND_TOPIC, self._on_command_text, 10)
        self.create_subscription(String, ASSISTANT_LEGACY_VOICE_TEXT_TOPIC, self._on_command_text, 10)
        self.create_subscription(String, ASSISTANT_LEGACY_GUI_COMMAND_TOPIC, self._on_command_text, 10)
        self.create_subscription(String, ASSISTANT_DATA_SYNC_SNAPSHOT_TOPIC, self._on_data_sync_snapshot, 10)
        self.create_subscription(String, ASSISTANT_PERSON_RECOGNIZED_TOPIC, self._on_person_recognized, 10)
        self.create_subscription(Bool, ASSISTANT_PERSON_GREETING_ENABLED_TOPIC, self._on_person_greeting_enabled, 10)
        self.create_subscription(Float32, "/assistant/battery_percent", self._on_battery_percent, 10)
        self.create_subscription(Bool, "/assistant/charging", self._on_charging, 10)
        self._charging = False
        self._person_greeting_enabled = False
        self._person_greeting_active = False
        self._person_greeting_paused_navigation = False
        self._person_greeting_steps: list[tuple[str, dict[str, float | str]]] = []
        self._person_greeting_step_timer = None
        self._person_greeting_motion_timer = None
        self._person_greeting_motion_end_time = 0.0
        self._person_greeting_motion_twist = Twist()
        self._person_greeting_active_user = ''
        self._person_greeting_include_motion = False
        # 기능: executor step을 주기적으로 진행시키는 heartbeat 타이머.
        self.create_timer(0.5, self._on_tick)
        self._sync_request_timer = self.create_timer(1.0, self._request_runtime_data_snapshot_once)
        self.get_logger().info("Omni orchestrator node ready.")

    def _request_runtime_data_snapshot_once(self) -> None:
        if self._sync_request_timer is not None:
            self._sync_request_timer.cancel()
            self.destroy_timer(self._sync_request_timer)
            self._sync_request_timer = None
        request_id = f"robot_orchestrator:{int(time.time())}"
        self._data_sync_request_publisher.publish(String(data=request_id))
        self.get_logger().info("Requested runtime data snapshot from GUI.")

    @staticmethod
    def _write_json_file(path: Path, payload: object) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def _on_data_sync_snapshot(self, message: String) -> None:
        try:
            payload = json.loads(message.data)
        except Exception:
            self.get_logger().warning("Ignored invalid runtime data snapshot payload.")
            return

        if not isinstance(payload, dict):
            return

        version = int(payload.get("version", -1)) if str(payload.get("version", "")).isdigit() else -1
        if version >= 0 and version <= self._latest_sync_version:
            return

        schedules = payload.get("schedules", {})
        alarms = payload.get("alarms", [])
        medications = payload.get("medications", {"last_run_date": "", "meds": []})

        if not isinstance(schedules, dict):
            schedules = {}
        if not isinstance(alarms, list):
            alarms = []
        if isinstance(medications, list):
            medications = {"last_run_date": "", "meds": medications}
        if not isinstance(medications, dict):
            medications = {"last_run_date": "", "meds": []}

        try:
            self._write_json_file(self._runtime_data_service.schedule_path, schedules)
            self._write_json_file(self._runtime_data_service.alarm_path, alarms)
            self._write_json_file(self._runtime_data_service.medication_path, medications)
            self._latest_sync_version = max(self._latest_sync_version, version)
            meds_count = len(medications.get("meds", []) if isinstance(medications.get("meds", []), list) else [])
            self.get_logger().info(
                f"Runtime data synced: schedules={len(schedules)}, alarms={len(alarms)}, "
                f"meds={meds_count}, version={payload.get('version', 'n/a')}"
            )
        except Exception as exc:
            self.get_logger().error(f"Failed to persist runtime data snapshot: {exc}")

    def _on_command_text(self, message: String) -> None:
        decision, _ = self._orchestrator.ingest_voice_text(message.data)
        self.get_logger().info(f"Command intake: {decision}")
        self._publish_state()

    def _on_battery_percent(self, message: Float32) -> None:
        self._orchestrator.update_battery(battery_level=float(message.data), charging=self._charging)
        self._publish_state()

    def _on_charging(self, message: Bool) -> None:
        self._charging = bool(message.data)
        self._orchestrator.update_battery(
            battery_level=self._orchestrator.state.battery_level,
            charging=self._charging,
        )
        self._publish_state()

    def _on_tick(self) -> None:
        if self._person_greeting_active:
            self._publish_state()
            return
        self._orchestrator.tick()
        self._publish_state()

    def _on_person_greeting_enabled(self, message: Bool) -> None:
        self._person_greeting_enabled = bool(message.data)

    def _on_person_recognized(self, message: String) -> None:
        user_name = message.data.strip()
        if not user_name or not self._person_greeting_enabled or self._person_greeting_active:
            return
        if not self._orchestrator.should_greet_registered_person(user_name):
            return
        self._person_greeting_paused_navigation = False
        self._start_person_greeting_sequence(user_name, include_motion=False)

    def _start_person_greeting_sequence(self, user_name: str, *, include_motion: bool) -> None:
        self._person_greeting_active = True
        self._person_greeting_active_user = user_name
        self._person_greeting_include_motion = False
        self._person_greeting_steps = [
            ('speak', {'text': f'{user_name}님 안녕하세요. 오늘도 좋은 하루 보내세요.'}),
            ('wait', {'duration': 2.0}),
        ]
        self.get_logger().info(
            f'Starting person greeting overlay for {user_name} (tts_only=True)'
        )
        self._run_next_person_greeting_step()

    def _run_next_person_greeting_step(self) -> None:
        self._cancel_person_greeting_step_timer()
        if not self._person_greeting_steps:
            self._finish_person_greeting_sequence()
            return

        kind, payload = self._person_greeting_steps.pop(0)
        if kind == 'speak':
            text = str(payload.get('text', '')).strip()
            if text:
                self._speak_publisher.publish(String(data=text))
            self._schedule_person_greeting_step(0.1)
            return
        if kind == 'wait':
            self._schedule_person_greeting_step(float(payload.get('duration', 0.5)))
            return
        if kind == 'motion':
            self._start_person_greeting_motion(
                linear=float(payload.get('linear', 0.0)),
                angular=float(payload.get('angular', 0.0)),
                duration=float(payload.get('duration', 0.5)),
            )
            return

        self._schedule_person_greeting_step(0.1)

    def _schedule_person_greeting_step(self, delay_sec: float) -> None:
        def _advance() -> None:
            self._cancel_person_greeting_step_timer()
            self._run_next_person_greeting_step()

        self._person_greeting_step_timer = self.create_timer(max(0.05, delay_sec), _advance)

    def _cancel_person_greeting_step_timer(self) -> None:
        if self._person_greeting_step_timer is None:
            return
        self._person_greeting_step_timer.cancel()
        self.destroy_timer(self._person_greeting_step_timer)
        self._person_greeting_step_timer = None

    def _start_person_greeting_motion(self, *, linear: float, angular: float, duration: float) -> None:
        self._stop_person_greeting_motion()
        self._person_greeting_motion_twist = Twist()
        self._person_greeting_motion_twist.linear.x = float(linear)
        self._person_greeting_motion_twist.angular.z = float(angular)
        self._person_greeting_motion_end_time = time.monotonic() + max(0.1, duration)
        self._person_greeting_motion_timer = self.create_timer(0.1, self._publish_person_greeting_motion)

    def _publish_person_greeting_motion(self) -> None:
        if time.monotonic() >= self._person_greeting_motion_end_time:
            self._stop_person_greeting_motion()
            self._run_next_person_greeting_step()
            return
        self._cmd_vel_publisher.publish(self._person_greeting_motion_twist)

    def _stop_person_greeting_motion(self) -> None:
        if self._person_greeting_motion_timer is not None:
            self._person_greeting_motion_timer.cancel()
            self.destroy_timer(self._person_greeting_motion_timer)
            self._person_greeting_motion_timer = None
        self._person_greeting_motion_end_time = 0.0
        self._cmd_vel_publisher.publish(Twist())

    def _finish_person_greeting_sequence(self) -> None:
        self._cancel_person_greeting_step_timer()
        self._stop_person_greeting_motion()
        self._person_greeting_paused_navigation = False
        self._person_greeting_active = False
        self._person_greeting_active_user = ''
        self._person_greeting_include_motion = False
        self._publish_state()

    def _publish_state(self) -> None:
        # 기능: GUI/외부 노드가 바로 파싱 가능한 JSON 상태 스냅샷을 publish.
        state = self._orchestrator.state
        self._status_publisher.publish(String(data=json.dumps({
            "top_state": state.top_state.value,
            "current_mission_id": state.current_mission_id,
            "battery_level": state.battery_level,
            "charging": state.charging,
            "low_battery_restricted": state.low_battery_restricted,
            "pending_count": state.pending_count,
            "status_message_for_gui": state.status_message_for_gui,
            "current_mission_type": state.current_mission_type,
            "current_detail": state.current_detail,
        }, ensure_ascii=False)))


def main(args: list[str] | None = None) -> None:
    logging.basicConfig(level=logging.INFO)
    rclpy.init(args=args)
    node = OrchestratorNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()
