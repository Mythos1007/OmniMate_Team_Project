from __future__ import annotations

import re
import time
import os
import shutil
import subprocess

from PySide6.QtCore import QObject, QTimer

try:
    from assistant_gui.pages.voice_pages import SpeechRecognitionWorker
except ModuleNotFoundError:
    from pages.voice_pages import SpeechRecognitionWorker


GUI_WAKEWORD_VARIANTS = (
    "김루이엘리자베스돌쇠에드워드3세",
    "김루이",
    "루이",
    "김엘리자베스",
    "엘리자베스",
    "김돌쇠",
    "돌쇠야",
    "돌쇠",
    "김에드워드3세",
    "에드워드3세",
    "김에드워드",
    "에드워드",
)


def extract_command_after_wakeword(text: str) -> str:
    candidates = tuple(sorted(GUI_WAKEWORD_VARIANTS, key=len, reverse=True))
    stripped = text.strip()
    for keyword in candidates:
        idx = stripped.find(keyword)
        if idx >= 0:
            tail = stripped[idx + len(keyword):].strip(" \t,.;:!?~")
            return re.sub(r"^(야|아|여)\s*", "", tail)
    return ""


def is_wakeword_detected(text: str) -> bool:
    compact = re.sub(r"[^0-9A-Za-z가-힣]", "", text).lower()
    wakeword_variants = {
        re.sub(r"[^0-9A-Za-z가-힣]", "", variant).lower()
        for variant in GUI_WAKEWORD_VARIANTS
    }
    if compact in wakeword_variants:
        return True
    return any(variant in compact for variant in wakeword_variants)


class GlobalWakewordController(QObject):
    def __init__(self, main_window) -> None:
        super().__init__(main_window)
        self._main_window = main_window
        self._loop_enabled = bool(getattr(main_window, "_face_voice_loop_enabled", True))
        self._loop_active = False
        self._stage = "wakeword"
        self._worker = None
        self._command_started_monotonic = 0.0
        self._silence_retries = 0
        self._wake_listen_sec = max(3.0, float(getattr(main_window, "_face_voice_wake_listen_sec", 8.0)))
        self._command_listen_sec = max(2.0, float(getattr(main_window, "_face_voice_command_listen_sec", 4.0)))
        self._wake_restart_delay_ms = max(0, int(getattr(main_window, "_face_voice_wake_restart_delay_ms", 180)))
        self._command_restart_delay_ms = max(0, int(getattr(main_window, "_face_voice_command_restart_delay_ms", 100)))
        self._command_timeout_sec = float(getattr(main_window, "_face_voice_command_timeout_sec", 10.0))
        self._max_silence_retries = int(getattr(main_window, "_face_voice_max_silence_retries", 2))
        self._pause_until = 0.0

    def sync(self) -> None:
        self._loop_enabled = bool(getattr(self._main_window, "_face_voice_loop_enabled", True))
        should_run = self._loop_enabled
        if should_run and not self._loop_active:
            self._loop_active = True
            self._stage = "wakeword"
            self._command_started_monotonic = 0.0
            self._silence_retries = 0
            self._start_worker(delay_ms=200)
            return

        if not should_run and self._loop_active:
            self.stop()

    def stop(self) -> None:
        self._loop_active = False
        self._stage = "wakeword"
        self._command_started_monotonic = 0.0
        self._silence_retries = 0
        if hasattr(self._main_window, "shared_face_controller"):
            try:
                self._main_window.shared_face_controller.on_listening_finished()
                self._main_window.shared_face_controller.on_tts_finished()
            except Exception:
                pass
        if self._worker is not None:
            try:
                if self._worker.isRunning():
                    self._worker.wait(11000)
            except Exception:
                pass
            self._worker = None

    def _start_worker(self, *, delay_ms: int = 0) -> None:
        if not self._loop_active:
            return
        if self._worker is not None:
            return

        def _kickoff() -> None:
            if not self._loop_active or self._worker is not None:
                return
            if time.monotonic() < self._pause_until:
                QTimer.singleShot(250, lambda: self._start_worker(delay_ms=0))
                return
            if not self._main_window.is_microphone_available() or not self._main_window.is_network_available():
                QTimer.singleShot(2500, lambda: self._start_worker(delay_ms=0))
                return

            record_seconds = self._wake_listen_sec if self._stage == "wakeword" else self._command_listen_sec
            worker = SpeechRecognitionWorker(language="ko-KR", record_seconds=record_seconds, parent=self._main_window)
            self._worker = worker
            worker.recognized.connect(self._on_recognized)
            worker.failed.connect(self._on_failed)
            worker.finished.connect(self._on_finished)
            worker.start()

        if delay_ms > 0:
            QTimer.singleShot(delay_ms, _kickoff)
        else:
            _kickoff()

    def _on_recognized(self, text: str) -> None:
        wakeword_hit = is_wakeword_detected(text)

        if self._stage == "wakeword":
            if not wakeword_hit:
                return

            inline_command = extract_command_after_wakeword(text)
            if hasattr(self._main_window, "shared_face_controller"):
                try:
                    self._main_window.shared_face_controller.on_wakeword_detected()
                    if inline_command:
                        self._main_window.shared_face_controller.on_listening_finished()
                    else:
                        self._main_window.shared_face_controller.on_listening_started()
                except Exception:
                    pass

            if inline_command:
                self._handle_command(inline_command)
                return

            self._set_header_state("🎧 호출어 인식, 명령 대기 중...", "#3B82F6")
            wakeword_prompt = self._main_window.render_tts_scenario("wakeword_prompt")
            if self._speak_text(wakeword_prompt):
                if bool(getattr(self._main_window, "_wakeword_reply_only", False)):
                    self._stage = "wakeword"
                    self._command_started_monotonic = 0.0
                    self._silence_retries = 0
                    self._set_header_state("🎤️ 호출어 대기 중...", "#10B981")
                    return
                self._stage = "command"
                self._command_started_monotonic = time.monotonic()
                self._silence_retries = 0
            else:
                self._stage = "wakeword"
                self._command_started_monotonic = 0.0
                self._silence_retries = 0
                self._set_header_state("⚠️ 음성 출력 실패 (TTS 확인 필요)", "#EF4444")
            return

        if wakeword_hit:
            inline_command = extract_command_after_wakeword(text)
            if inline_command:
                if bool(getattr(self._main_window, "_wakeword_reply_only", False)):
                    self._speak_text(self._main_window.render_tts_scenario("wakeword_only_mode"))
                    self._stage = "wakeword"
                    self._command_started_monotonic = 0.0
                    self._silence_retries = 0
                    return
                self._handle_command(inline_command)
                return

            wakeword_prompt = self._main_window.render_tts_scenario("wakeword_prompt")
            if self._speak_text(wakeword_prompt):
                if bool(getattr(self._main_window, "_wakeword_reply_only", False)):
                    self._stage = "wakeword"
                    self._command_started_monotonic = 0.0
                    self._silence_retries = 0
                    return
                self._command_started_monotonic = time.monotonic()
                self._silence_retries = 0
            else:
                self._stage = "wakeword"
                self._command_started_monotonic = 0.0
                self._silence_retries = 0
            return

        self._handle_command(text)

    def _handle_command(self, command_text: str) -> None:
        if hasattr(self._main_window, "shared_face_controller"):
            try:
                self._main_window.shared_face_controller.on_listening_finished()
                self._main_window.shared_face_controller.on_processing_started()
            except Exception:
                pass
        self._set_header_state("🤔 명령 이해 중...", "#F59E0B")
        submitted, message, handled_locally = self._main_window.dispatch_voice_command(command_text)
        if submitted and handled_locally:
            self._set_header_state("💬 로컬 응답 완료", "#10B981")
            self._speak_text(message)
        elif submitted:
            self._set_header_state("📝 명령을 전달했습니다", "#10B981")
            self._speak_text("등록했습니다.")
        else:
            self._set_header_state("⚠️ 명령 전송 실패", "#EF4444")
            if hasattr(self._main_window, "shared_face_controller"):
                try:
                    self._main_window.shared_face_controller.on_processing_finished()
                except Exception:
                    pass
            self._speak_text(f"명령 전송에 실패했습니다. {message}")
        self._stage = "wakeword"
        self._command_started_monotonic = 0.0
        self._silence_retries = 0

    def _on_failed(self, message: str) -> None:
        if self._stage != "command":
            return

        self._silence_retries += 1
        elapsed = 0.0
        if self._command_started_monotonic > 0.0:
            elapsed = time.monotonic() - self._command_started_monotonic

        timeout_hit = elapsed >= self._command_timeout_sec
        retry_hit = self._silence_retries >= self._max_silence_retries
        if timeout_hit or retry_hit or ("초과" in message):
            self._stage = "wakeword"
            self._command_started_monotonic = 0.0
            self._silence_retries = 0
            if hasattr(self._main_window, "shared_face_controller"):
                try:
                    self._main_window.shared_face_controller.on_listening_finished()
                except Exception:
                    pass
            self._set_header_state("🎤️ 호출어 대기 중...", "#10B981")

    def _on_finished(self) -> None:
        self._worker = None
        if self._loop_active and self._stage == "wakeword":
            self._set_header_state("🎤️ 호출어 대기 중...", "#10B981")
        if self._loop_active:
            next_delay = self._command_restart_delay_ms if self._stage == "command" else self._wake_restart_delay_ms
            self._start_worker(delay_ms=next_delay)

    def _set_header_state(self, label: str, color: str) -> None:
        self._main_window.hdr_voiceState_Lbl.setText(label)
        self._main_window.hdr_voiceState_Lbl.setStyleSheet(
            f"font-size: 16px; font-weight: bold; color: {color};"
        )

    def _speak_text(self, text: str) -> bool:
        ok, message = self._main_window.speak_text(text, target="pc")
        if not ok:
            self._set_header_state("⚠️ 음성 출력 실패 (TTS 확인 필요)", "#EF4444")
            return False
        return True
