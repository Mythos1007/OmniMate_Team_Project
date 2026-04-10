from __future__ import annotations

from datetime import datetime, timedelta
import logging

from assistant_robot.executors.base import BaseMissionExecution
from assistant_robot.interfaces.intent_parser import BaseIntentParser, IntentParseResult
from assistant_robot.models.command_request import CommandRequest
from assistant_robot.models.enums import MissionStatus, MissionType, TtsPriority
from assistant_robot.models.mission import Mission
from assistant_robot.models.mission_result import IntakeDecision, MissionEvent, MissionResult
from assistant_robot.models.robot_state import RobotState
from assistant_robot.orchestrator.battery_policy import BatteryPolicy
from assistant_robot.orchestrator.mission_dispatcher import MissionDispatcher
from assistant_robot.orchestrator.mission_queue import MissionQueue
from assistant_robot.orchestrator.next_mission_resolver import NextMissionResolver
from assistant_robot.orchestrator.state_machine import RobotStateMachine
from assistant_robot.services.greeting_manager import GreetingManager
from assistant_robot.services.runtime_data_service import RuntimeDataService
from assistant_robot.services.tts_manager import TTSManager


class OmniOrchestrator:
    """기능: 전체 미션 흐름을 중앙에서 조율하는 오케스트레이터.

    정책 요약:
    - 실행은 항상 1개 미션만 수행
    - 새 요청은 실행 중이어도 큐에 등록 가능
    - 저전력 제한에서는 이동 미션 intake/dispatch를 정책적으로 차단
    - 얼굴 인사 같은 overlay 이벤트는 메인 미션을 중단하지 않음
    """

    def __init__(
        self,
        *,
        mission_queue: MissionQueue,
        state_machine: RobotStateMachine,
        battery_policy: BatteryPolicy,
        dispatcher: MissionDispatcher,
        next_mission_resolver: NextMissionResolver,
        intent_parser: BaseIntentParser,
        tts_manager: TTSManager,
        greeting_manager: GreetingManager,
        runtime_data_service: RuntimeDataService | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self._queue = mission_queue
        self._state_machine = state_machine
        self._battery_policy = battery_policy
        self._dispatcher = dispatcher
        self._next_mission_resolver = next_mission_resolver
        self._intent_parser = intent_parser
        self._tts_manager = tts_manager
        self._greeting_manager = greeting_manager
        self._runtime_data_service = runtime_data_service
        self._logger = logger or logging.getLogger(__name__)
        self._active_mission: Mission | None = None
        self._active_execution: BaseMissionExecution | None = None
        self._last_command_time: datetime | None = None
        self._state_machine.boot_completed()

    @property
    def state(self) -> RobotState:
        self._sync_pending_count()
        return self._state_machine.snapshot()

    @property
    def active_mission(self) -> Mission | None:
        return self._active_mission

    @property
    def active_execution(self) -> BaseMissionExecution | None:
        return self._active_execution

    def update_battery(self, *, battery_level: float, charging: bool, charging_eta_minutes: int | None = None) -> None:
        self._state_machine.update_battery(
            battery_level=battery_level,
            charging=charging,
            charging_eta_minutes=charging_eta_minutes,
        )
        self._sync_pending_count()

    def ingest_voice_text(self, raw_text: str) -> tuple[IntakeDecision, IntentParseResult]:
        # 기능: 음성 문장을 정형 intent로 변환하고, 첫 번째 유효 명령만 접수 기능.
        self._last_command_time = datetime.utcnow()
        parse_result = self._intent_parser.parse(raw_text)
        if parse_result.rejected_commands and parse_result.rejection_message_key:
            self._tts_manager.speak_message(parse_result.rejection_message_key, priority=TtsPriority.HIGH)
        if parse_result.primary_command is None:
            decision = IntakeDecision(
                accepted=False,
                reason="no_valid_command",
                gui_message="유효한 요청을 찾지 못했습니다.",
                tts_message_key="error.general",
            )
            self._tts_manager.speak_message("error.general", priority=TtsPriority.HIGH)
            return decision, parse_result
        decision = self.submit_command(parse_result.primary_command)
        return decision, parse_result

    def submit_command(self, command: CommandRequest) -> IntakeDecision:
        # 기능: intake 정책 검사 -> mission 생성 -> queue 등록 -> 필요 시 즉시 dispatch.
        self._sync_pending_count()
        action = str(command.payload.get("action", "")).strip()
        if action == "cancel_request":
            return self._cancel_active_mission()

        state = self._state_machine.state
        accepted, reason = self._battery_policy.can_accept_command(command, state)
        if not accepted:
            decision = IntakeDecision(
                accepted=False,
                reason=reason,
                gui_message="지금은 이동 명령을 받을 수 없습니다.",
                tts_message_key=reason,
            )
            if decision.tts_message_key:
                self._tts_manager.speak_message(decision.tts_message_key, priority=TtsPriority.HIGH)
            return decision

        priority = int(command.parsed_intent.get("priority", self._default_priority(command.mission_type)))
        requires_confirmation = bool(command.parsed_intent.get("requires_confirmation", False))
        mission = Mission.from_command(
            command,
            priority=priority,
            requires_confirmation=requires_confirmation,
        )
        if mission.mission_type == MissionType.STATUS_BRIEF and self._active_mission is not None:
            # 기능: "어디가?" 질의는 현재 진행 중인 목적지를 우선 안내하도록 payload를 주입 기능.
            destination = self._active_mission.target_location or self._active_mission.target_user
            if destination:
                mission.payload["active_destination"] = destination

        if self._should_execute_overlay(command, mission):
            self._execute_overlay_mission(mission)
            return IntakeDecision(
                accepted=True,
                reason="overlay_executed",
                gui_message="요청을 즉시 처리했습니다.",
                mission_id=mission.mission_id,
                queued=False,
            )

        self._queue.push(mission)
        self._sync_pending_count()

        pending_count = self._queue.get_pending_count()
        key = "queue.accepted_with_pending" if pending_count > 1 or self._active_mission is not None else "queue.accepted"
        decision = IntakeDecision(
            accepted=True,
            reason="accepted",
            gui_message="요청이 등록되었습니다." if key == "queue.accepted" else "요청이 등록되었고 대기열에 추가되었습니다.",
            tts_message_key=key,
            tts_message_params={"pending_count": pending_count - (1 if self._active_mission is None else 0)},
            mission_id=mission.mission_id,
            queued=self._active_mission is not None,
        )
        if decision.tts_message_key:
            self._tts_manager.speak_message(decision.tts_message_key, **decision.tts_message_params)
        if self._active_mission is None:
            self.dispatch_next()
        return decision

    def _cancel_active_mission(self) -> IntakeDecision:
        if self._active_mission is None or self._active_execution is None:
            self._tts_manager.speak("현재 취소할 작업이 없습니다.", priority=TtsPriority.HIGH)
            return IntakeDecision(
                accepted=True,
                reason="no_active_mission",
                gui_message="현재 취소할 작업이 없습니다.",
            )

        try:
            self._active_execution.cancel()
        except Exception as exc:
            self._logger.warning("Failed to cancel active execution %s: %s", self._active_mission.mission_id, exc)

        cancelled_mission_id = self._active_mission.mission_id
        self._active_mission.status = MissionStatus.CANCELLED
        self._active_execution = None
        self._active_mission = None
        self._state_machine.clear_active_mission()
        self._sync_pending_count()
        self._tts_manager.speak("현재 작업을 취소했습니다.", priority=TtsPriority.HIGH)
        self.dispatch_next()
        return IntakeDecision(
            accepted=True,
            reason="cancelled_active_mission",
            gui_message="현재 작업을 취소했습니다.",
            mission_id=cancelled_mission_id,
            queued=False,
        )

    def _should_execute_overlay(self, command: CommandRequest, mission: Mission) -> bool:
        if self._active_mission is None:
            return False
        if command.requires_movement:
            return False
        return mission.mission_type in {MissionType.WEATHER_TTS, MissionType.STATUS_BRIEF}

    def _execute_overlay_mission(self, mission: Mission) -> None:
        mission.status = MissionStatus.RUNNING
        execution = self._dispatcher.dispatch(mission)
        self._logger.info("Executing overlay mission %s (%s)", mission.mission_id, mission.mission_type.value)

        for _ in range(8):
            event = execution.step()
            speak_text = str(event.details.get("speak_text", "")).strip() if event.details else ""
            if speak_text:
                self._tts_manager.speak(speak_text)
            if event.message_key:
                self._tts_manager.speak_message(event.message_key, **event.message_params)
            if event.terminal:
                mission.status = MissionStatus(
                    event.details.get("status", MissionStatus.COMPLETED.value)
                ) if event.details.get("status") else MissionStatus.COMPLETED
                return

        self._logger.warning(
            "Overlay mission %s (%s) did not terminate within step budget",
            mission.mission_id,
            mission.mission_type.value,
        )

    def dispatch_next(self) -> Mission | None:
        # 기능: 현재 실행 중이 아니면 dispatch 가능한 다음 미션 하나를 선택 기능.
        if self._active_mission is not None:
            return self._active_mission
        mission = self._next_mission_resolver.pop_dispatchable(state=self._state_machine.state)
        self._sync_pending_count()
        if mission is None:
            return None
        mission.status = MissionStatus.RUNNING
        self._active_mission = mission
        self._active_execution = self._dispatcher.dispatch(mission)
        self._state_machine.set_active_mission(mission)
        self._logger.info("Dispatching mission %s (%s)", mission.mission_id, mission.mission_type.value)
        return mission

    def tick(self) -> MissionResult | None:
        # 기능: 실행기의 step 이벤트를 1회 처리하는 heartbeat 루프.
        if self._active_execution is None:
            self.dispatch_next()
            return None

        event = self._active_execution.step()
        result = self._handle_event(event)
        if event.terminal:
            # 정책: 저전력 제한 중 현재 미션이 끝나면 복귀 미션을 자동 삽입 기능.
            finished_mission = self._active_mission
            self._active_execution = None
            self._active_mission = None
            if finished_mission is not None and self._battery_policy.should_return_after_current(
                self._state_machine.state,
                current_mission=finished_mission,
            ):
                self._queue.push(self._battery_policy.build_return_mission())
            self._sync_pending_count()
            self.dispatch_next()
        return result

    def handle_face_recognized(self, user_name: str, *, now: datetime | None = None) -> bool:
        # 기능: 인사 overlay 이벤트. 메인 상태/미션을 건드리지 않고 TTS만 출력 기능.
        if not self.should_greet_registered_person(user_name, now=now):
            return False
        self.speak_message("greeting.registered_person", user_name=user_name)
        return True

    def should_greet_registered_person(self, user_name: str, *, now: datetime | None = None) -> bool:
        current_time = now or datetime.utcnow()
        return self._greeting_manager.should_greet(user_name, now=current_time)

    def pause_active_navigation_for_overlay(self) -> bool:
        if self._active_execution is None:
            return False
        try:
            return bool(self._active_execution.pause_navigation())
        except Exception as exc:
            self._logger.warning("Failed to pause active navigation for overlay: %s", exc)
            return False

    def resume_active_navigation_after_overlay(self) -> bool:
        if self._active_execution is None:
            return False
        try:
            return bool(self._active_execution.resume_navigation())
        except Exception as exc:
            self._logger.warning("Failed to resume active navigation after overlay: %s", exc)
            return False

    def speak_text(self, text: str, *, priority: TtsPriority = TtsPriority.NORMAL, interrupt: bool = False) -> None:
        self._tts_manager.speak(text, priority=priority, interrupt=interrupt)

    def speak_message(
        self,
        key: str,
        *,
        priority: TtsPriority = TtsPriority.NORMAL,
        interrupt: bool = False,
        **kwargs: object,
    ) -> str:
        return self._tts_manager.speak_message(key, priority=priority, interrupt=interrupt, **kwargs)

    def check_idle_timeout(self, *, timeout_seconds: float = 30.0) -> bool:
        """기능: 마지막 명령 이후 timeout_seconds 초 이상 입력이 없으면 복귀 미션을 삽입 기능.

        - 이미 활성 미션이 있거나 아직 명령을 받은 적 없으면 아무것도 하지 않는다.
        - 복귀할 위치가 없는 경우 TTS로만 안내한다.
        - 반환값 True: 타임아웃이 발동되어 복귀 미션을 삽입했음.
        """
        if self._active_mission is not None:
            return False
        if self._last_command_time is None:
            return False
        elapsed = (datetime.utcnow() - self._last_command_time).total_seconds()
        if elapsed < timeout_seconds:
            return False
        # 타임아웃 — 대기열에 pending 미션이 있으면 자연스럽게 이어서 실행
        if self._queue.get_pending_count() > 0:
            self._last_command_time = datetime.utcnow()
            self.dispatch_next()
            return True
        # 대기열도 비어 있으면 베이스로 복귀
        return_mission = self._battery_policy.build_return_mission()
        self._queue.push(return_mission)
        self._last_command_time = datetime.utcnow()
        self._logger.info("Idle timeout (%.0fs): queuing return-to-base mission", elapsed)
        self._tts_manager.speak_message("status.idle_timeout", priority=TtsPriority.HIGH)
        self.dispatch_next()
        return True

    def list_pending_missions(self) -> list[Mission]:
        return self._queue.list_pending()

    def _handle_event(self, event: MissionEvent) -> MissionResult:
        # 기능: executor 이벤트를 상태머신/TTS로 반영해 최종 미션 결과로 변환 기능.
        status = MissionStatus(event.details.get("status", MissionStatus.RUNNING.value)) if event.details.get("status") else None
        if (
            status == MissionStatus.COMPLETED
            and self._active_mission is not None
            and self._active_mission.mission_type == MissionType.MEDICATION
            and self._runtime_data_service is not None
        ):
            try:
                self._runtime_data_service.mark_medication_completed(
                    target_user=str(self._active_mission.target_user or "").strip(),
                )
            except Exception as exc:
                self._logger.warning("Failed to persist medication completion: %s", exc)
        if self._active_mission is not None:
            self._state_machine.apply_event(self._active_mission, event_type=event.event_type, status=status)
        speak_text = str(event.details.get("speak_text", "")).strip() if event.details else ""
        if speak_text:
            self._tts_manager.speak(speak_text)
        if event.message_key:
            self._tts_manager.speak_message(event.message_key, **event.message_params)
        self._sync_pending_count()
        result_status = status or MissionStatus.RUNNING
        return MissionResult(mission_id=event.mission_id, status=result_status, events=[event])

    def _sync_pending_count(self) -> None:
        self._state_machine.set_pending_count(self._queue.get_pending_count())

    @staticmethod
    def _default_priority(mission_type: MissionType) -> int:
        priorities = {
            MissionType.ALARM: 300,
            MissionType.MEDICATION: 320,
            MissionType.DELIVERY: 200,
            MissionType.CALL: 180,
            MissionType.WEATHER_TTS: 50,
            MissionType.STATUS_BRIEF: 40,
            MissionType.RETURN_TO_BASE: 1000,
        }
        return priorities.get(mission_type, 100)
