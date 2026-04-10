from __future__ import annotations

import ast
import math
import os
import re
import time
from collections import deque
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QWidget, QBoxLayout, QHBoxLayout, QVBoxLayout, QFrame, QLabel, QPushButton, QGridLayout, QMessageBox

try:
    from assistant_gui.map_view import RotatedMapView
except ModuleNotFoundError:
    from map_view import RotatedMapView


class HomePage(QWidget):
    def __init__(self, main_window, engine):
        super().__init__()
        self.main_window, self.engine = main_window, engine
        layout = QBoxLayout(QBoxLayout.LeftToRight, self)
        self._root_layout = layout
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(20)

        left_layout = QVBoxLayout()
        map_frame = QFrame()
        map_frame.setProperty("class", "CardFrame")
        map_lay = QVBoxLayout(map_frame)
        map_path, yaml_resolution, yaml_origin_x, yaml_origin_y, ref_w, ref_h = self._load_map_metadata()
        default_rot_deg = "0" if Path(map_path).suffix.lower() == ".pgm" else "-26"
        coord_rotation_deg = float(os.getenv("ASSISTANT_COORD_ROT_DEG", default_rot_deg))
        resolution = float(os.getenv("ASSISTANT_MAP_RESOLUTION", str(yaml_resolution)))
        origin_x = float(os.getenv("ASSISTANT_MAP_ORIGIN_X", str(yaml_origin_x)))
        origin_y = float(os.getenv("ASSISTANT_MAP_ORIGIN_Y", str(yaml_origin_y)))

        self.map_view = RotatedMapView(
            map_path=map_path,
            coord_rotation_deg=coord_rotation_deg,
            resolution_m_per_px=resolution,
            origin_xy=(origin_x, origin_y),
            reference_size_px=(ref_w, ref_h),
        )
        self.map_view.set_robot_world_pose(0.0, 0.0, is_default=True)
        self.map_view.map_clicked.connect(self._on_map_clicked_world)
        self.map_view.setStyleSheet("border-radius: 8px;")
        # 속도 추적용
        self._last_pose: tuple[float, float] | None = None
        self._last_pose_time: float = 0.0
        self._last_pose_source: str = ""
        self._last_yaw_rad: float = 0.0
        self._speed_samples: deque[float] = deque(maxlen=8)
        self._active_navigation_label = ""
        self._active_navigation_meta: dict[str, object] = {}
        self._arrival_distance_threshold_m = 0.22
        self._pending_navigation_queue: deque[dict[str, object]] = deque()
        self._navigation_stop_requested = False
        self._queue_resume_token = 0
        map_lay.addWidget(self.map_view, stretch=1)
        dest_lay = QBoxLayout(QBoxLayout.LeftToRight)
        self._destination_button_layout = dest_lay
        self._destination_buttons: list[QPushButton] = []
        orientation_toggle_btn = QPushButton("각도 정렬: ON")
        orientation_toggle_btn.setProperty("class", "PrimaryBtn")
        orientation_toggle_btn.clicked.connect(self._toggle_goal_orientation_requirement)
        self._orientation_toggle_button = orientation_toggle_btn
        dest_lay.addWidget(orientation_toggle_btn)
        stop_btn = QPushButton("안내 중지")
        stop_btn.setProperty("class", "StopBtn")
        stop_btn.clicked.connect(self._stop_navigation)
        self._stop_button = stop_btn
        dest_lay.addWidget(stop_btn)
        self._sync_goal_orientation_toggle_label()
        self.refresh_quick_destinations()
        map_lay.addLayout(dest_lay)
        left_layout.addWidget(map_frame)
        layout.addLayout(left_layout, stretch=6)

        right_layout = QVBoxLayout()
        self._menu_buttons: list[QPushButton] = []

        self.weather_card = QPushButton()
        self.weather_card.setObjectName("weather_card_btn")
        self.weather_card.setMinimumHeight(148)
        self.weather_card.clicked.connect(lambda: self.main_window.switch_page(10, manual=True))

        w_inner = QHBoxLayout(self.weather_card)
        w_inner.setContentsMargins(10, 25, 10, 10)
        w_inner.setSpacing(10)

        icon_box = QVBoxLayout()
        icon_box.setSpacing(0)
        self.icon_lbl = QLabel("--")
        self.icon_lbl.setAlignment(Qt.AlignCenter)
        self.icon_lbl.setStyleSheet("font-size: 77px; border:none;")
        self.desc_lbl = QLabel("확인중")
        self.desc_lbl.setAlignment(Qt.AlignCenter)
        self.desc_lbl.setStyleSheet("font-size: 20px; font-weight:bold; border:none; margin-top: -10px;")
        icon_box.addWidget(self.icon_lbl)
        icon_box.addWidget(self.desc_lbl)

        self.temp_lbl = QLabel("--°")
        self.temp_lbl.setAlignment(Qt.AlignCenter)
        self.temp_lbl.setStyleSheet("font-size: 70px; font-weight:bold; color:#3B82F6; border:none; margin-top: -15px;")

        air_box = QVBoxLayout()
        air_box.setSpacing(0)
        air_box.setContentsMargins(0, 0, 0, 0)
        self.air_face = QLabel("😊")
        self.air_face.setAlignment(Qt.AlignCenter)
        self.air_face.setStyleSheet("font-size: 65px; border:none; margin-bottom: -8px;")
        self.air_txt = QLabel("미세먼지\n보통")
        self.air_txt.setAlignment(Qt.AlignCenter)
        self.air_txt.setStyleSheet("font-size: 19px; font-weight:bold; border:none; margin-top: -26px;")
        air_box.addWidget(self.air_face)
        air_box.addWidget(self.air_txt)

        w_inner.addLayout(icon_box, 1)
        w_inner.addWidget(self.temp_lbl, 1)
        w_inner.addLayout(air_box, 1)
        right_layout.addWidget(self.weather_card)

        status_frame = QFrame()
        status_frame.setProperty("class", "CardFrame")
        status_lay = QVBoxLayout(status_frame)
        st_title = QLabel("현재 상태")
        st_title.setProperty("class", "TitleText")
        self.st_main = QLabel("대기 중...")
        self.st_main.setProperty("class", "StatusText")
        self.st_sub = QLabel("명령을 기다리고 있습니다.")
        self.st_sub.setProperty("class", "SubText")
        self.st_sub.setWordWrap(True)
        self.st_eta = QLabel("")
        self.st_eta.setProperty("class", "SubText")
        self.st_eta.setWordWrap(True)
        self.st_eta.setStyleSheet("color: #3B82F6; font-weight: bold;")
        self.st_pose = QLabel("📍 지도 좌표 수신 대기 중")
        self.st_pose.setProperty("class", "SubText")
        self.st_pose.setWordWrap(True)
        status_lay.addWidget(st_title)
        status_lay.addWidget(self.st_main)
        status_lay.addWidget(self.st_sub)
        status_lay.addWidget(self.st_eta)
        status_lay.addWidget(self.st_pose)
        right_layout.addWidget(status_frame)

        menu_frame = QFrame()
        menu_frame.setProperty("class", "CardFrame")
        grid = QGridLayout(menu_frame)
        btns = {"📅 일정": 2, "⏰ 알람": 4, "💊 복약 확인": 6, "✉️ 우편 전달": 7, "⚙️ 설정": 8, "🎤 음성 테스트": 9}
        positions = [(0, 0), (0, 1), (1, 0), (1, 1), (2, 0), (2, 1)]
        for i, (name, idx) in enumerate(btns.items()):
            btn = QPushButton(name)
            btn.setProperty("class", "ActionBtn")
            btn.clicked.connect(lambda checked=False, p=idx: self.main_window.switch_page(p, manual=True))
            self._menu_buttons.append(btn)
            grid.addWidget(btn, positions[i][0], positions[i][1])
        right_layout.addWidget(menu_frame)

        layout.addLayout(right_layout, stretch=4)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_ui)
        self.timer.start(500)
        self._apply_responsive_layout()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._apply_responsive_layout()

    def _apply_responsive_layout(self) -> None:
        width = max(1, self.width())
        height = max(1, self.height())
        compact = width < 1600 or height < 900
        stacked = width < 1460 or height < 800

        margins = 12 if compact else 20
        spacing = 12 if compact else 20
        self._root_layout.setDirection(QBoxLayout.TopToBottom if stacked else QBoxLayout.LeftToRight)
        self._root_layout.setContentsMargins(margins, margins, margins, margins)
        self._root_layout.setSpacing(spacing)

        base = min(width, height)
        icon_size = max(44, min(76, int(base * 0.10)))
        desc_size = max(16, min(20, int(base * 0.028)))
        temp_size = max(40, min(68, int(base * 0.085)))
        air_face_size = max(40, min(62, int(base * 0.082)))
        air_text_size = max(14, min(19, int(base * 0.026)))
        state_main_size = max(22, min(34, int(base * 0.036)))
        menu_button_height = 46 if compact else 54
        destination_button_height = 38 if compact else 44
        destination_font_size = 13 if compact else 14
        orientation_button_height = 40 if compact else 44
        stop_button_height = 40 if compact else 44

        self.weather_card.setMinimumHeight(136 if compact else 156)
        self._destination_button_layout.setDirection(QBoxLayout.TopToBottom if stacked else QBoxLayout.LeftToRight)
        self._destination_button_layout.setSpacing(8 if compact else 10)
        self.map_view.setMinimumHeight(120 if compact else 160)
        self.icon_lbl.setStyleSheet(f"font-size: {icon_size}px; border:none;")
        self.desc_lbl.setStyleSheet(f"font-size: {desc_size}px; font-weight:bold; border:none;")
        self.temp_lbl.setStyleSheet(f"font-size: {temp_size}px; font-weight:bold; color:#3B82F6; border:none;")
        self.air_face.setStyleSheet(f"font-size: {air_face_size}px; border:none;")
        self.air_txt.setStyleSheet(f"font-size: {air_text_size}px; font-weight:bold; border:none;")
        self.st_main.setStyleSheet(f"font-size: {state_main_size}px; font-weight: 700;")

        for label in (self.st_sub, self.st_eta, self.st_pose):
            label.setWordWrap(True)
        for button in self._menu_buttons:
            button.setMinimumHeight(menu_button_height)
        for button in self._destination_buttons:
            button.setMinimumHeight(destination_button_height)
            button.setStyleSheet(f"font-size: {destination_font_size}px;")
        self._orientation_toggle_button.setMinimumHeight(orientation_button_height)
        self._stop_button.setMinimumHeight(stop_button_height)

    def _sync_goal_orientation_toggle_label(self) -> None:
        enabled = True
        if hasattr(self.main_window, "is_goal_orientation_required"):
            try:
                enabled = bool(self.main_window.is_goal_orientation_required())
            except Exception:
                enabled = True
        self._orientation_toggle_button.setText("각도 정렬: ON" if enabled else "각도 정렬: OFF")

    def _toggle_goal_orientation_requirement(self) -> None:
        current_enabled = True
        if hasattr(self.main_window, "is_goal_orientation_required"):
            try:
                current_enabled = bool(self.main_window.is_goal_orientation_required())
            except Exception:
                current_enabled = True

        next_enabled = not current_enabled
        if hasattr(self.main_window, "set_goal_orientation_required"):
            ok, message = self.main_window.set_goal_orientation_required(next_enabled)
            if not ok:
                QMessageBox.warning(self, "각도 정렬 모드 변경 실패", message)
                return
        self._sync_goal_orientation_toggle_label()

    @staticmethod
    def _find_display_map_image_path() -> str:
        here = Path(__file__).resolve()

        primary_png = here.parent.parent / "map_0330_7clean.png"
        if primary_png.exists():
            return str(primary_png)

        env_path = os.getenv("ASSISTANT_MAP_IMAGE_PATH", "").strip()
        if env_path and Path(env_path).exists():
            return env_path
        candidates = (
            "src/assistant/assistant_gui/assistant_gui/map_0330_7clean.png",
            "assistant_gui/map_0330_7clean.png",
            "src/assistant/assistant_gui/assistant_gui/map_0330_7.pgm",
            "assistant_gui/map_0330_7.pgm",
            "src/assistant/assistant_gui/assistant_gui/clean_map_0330_7.pgm",
            "assistant_gui/clean_map_0330_7.pgm",
            "clean_map_0330_7_connected.pgm",
            "clean_map_0330_7.pgm",
        )
        for parent in here.parents:
            for name in candidates:
                candidate = parent / name
                if candidate.exists():
                    return str(candidate)
        return candidates[0]

    @classmethod
    def _load_map_metadata(cls) -> tuple[str, float, float, float, int, int]:
        default_map = cls._find_display_map_image_path()
        default_resolution = 0.05
        default_origin = (-10.0, -10.0)
        default_pix = QPixmap(default_map)
        default_w = max(1, default_pix.width()) if not default_pix.isNull() else 1
        default_h = max(1, default_pix.height()) if not default_pix.isNull() else 1

        here = Path(__file__).resolve()
        env_yaml = os.getenv("ASSISTANT_MAP_YAML_PATH", "").strip()
        yaml_candidates: list[Path] = []
        if env_yaml:
            yaml_candidates.append(Path(env_yaml))
        for parent in here.parents:
            yaml_candidates.extend(
                [
                    parent / "src/assistant/assistant_gui/assistant_gui/map_0330_7.yaml",
                    parent / "assistant_gui/map_0330_7.yaml",
                ]
            )

        yaml_path = next((p for p in yaml_candidates if p.exists()), None)
        if yaml_path is None:
            return default_map, default_resolution, default_origin[0], default_origin[1], default_w, default_h

        image_name = ""
        resolution = default_resolution
        origin_x, origin_y = default_origin
        try:
            for raw in yaml_path.read_text(encoding="utf-8").splitlines():
                line = raw.strip()
                if not line or line.startswith("#") or ":" not in line:
                    continue
                key, value = line.split(":", 1)
                key = key.strip()
                value = value.strip()
                if key == "image":
                    image_name = value.strip().strip("\"'")
                elif key == "resolution":
                    resolution = float(value)
                elif key == "origin":
                    parsed = ast.literal_eval(value)
                    if isinstance(parsed, (list, tuple)) and len(parsed) >= 2:
                        origin_x = float(parsed[0])
                        origin_y = float(parsed[1])
        except Exception:
            return default_map, default_resolution, default_origin[0], default_origin[1], default_w, default_h

        ref_w, ref_h = default_w, default_h
        if image_name:
            image_path = (yaml_path.parent / image_name).resolve()
            if image_path.exists():
                ref_pix = QPixmap(str(image_path))
                if not ref_pix.isNull():
                    ref_w = max(1, ref_pix.width())
                    ref_h = max(1, ref_pix.height())

        return default_map, resolution, origin_x, origin_y, ref_w, ref_h

    def update_robot_pose(self, x_m: float, y_m: float, yaw_rad: float = 0.0, source: str = "") -> None:
        now = time.monotonic()
        if self._last_pose is not None:
            dt = now - self._last_pose_time
            if 0.05 < dt < 5.0:
                dist = ((x_m - self._last_pose[0]) ** 2 + (y_m - self._last_pose[1]) ** 2) ** 0.5
                speed = dist / dt
                if speed < 3.0:
                    self._speed_samples.append(speed)
        self._last_pose = (x_m, y_m)
        self._last_pose_time = now
        self._last_yaw_rad = float(yaw_rad)
        source_label = str(source or "").strip()
        if source_label == "/amcl_pose":
            source_label = "amcl"
        elif source_label == "/odom":
            source_label = "odom"
        self._last_pose_source = source_label
        self.map_view.set_robot_world_pose(x_m, y_m, yaw_rad=float(yaw_rad), is_default=False)
        self._update_pose_tracking_status()
        self._maybe_mark_arrival(x_m, y_m)

    def update_robot_pose_from_status(self, status: str) -> None:
        patterns = [
            r"x\s*[:=]\s*(-?\d+(?:\.\d+)?)\s*[, ]+\s*y\s*[:=]\s*(-?\d+(?:\.\d+)?)",
            r"\(\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*\)",
        ]
        for pattern in patterns:
            match = re.search(pattern, status, flags=re.IGNORECASE)
            if match:
                self.update_robot_pose(float(match.group(1)), float(match.group(2)))
                break

    def _on_map_clicked_world(self, x_m: float, y_m: float) -> None:
        dlg = QMessageBox(self)
        dlg.setWindowTitle("좌표 이동")
        dlg.setText(f"이 좌표(x={x_m:.2f}, y={y_m:.2f})로 로봇을 이동시키겠습니까?")
        dlg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        dlg.setDefaultButton(QMessageBox.No)
        dlg.button(QMessageBox.Yes).setText("확인")
        dlg.button(QMessageBox.No).setText("취소")
        if dlg.exec() != QMessageBox.Yes:
            return

        if self._has_active_navigation():
            self._enqueue_navigation({"kind": "coordinate", "x": float(x_m), "y": float(y_m), "label": f"좌표 x={x_m:.2f}, y={y_m:.2f}"})
            return

        self._start_coordinate_navigation(x_m, y_m)

    def _has_active_navigation(self) -> bool:
        return bool(self._active_navigation_label and self.map_view.get_nav_target_world() is not None)

    def _enqueue_navigation(self, entry: dict[str, object]) -> None:
        label = str(entry.get("label", "다음 목표")).strip() or "다음 목표"
        self._pending_navigation_queue.append(entry)
        current_label = self._active_navigation_label or "현재 목표"
        self.st_main.setText(f"{current_label} 이동 중...")
        self.st_sub.setText(self._build_queue_status_text(prefix=f"대기열 {len(self._pending_navigation_queue)}건 추가: {label}"))

    def _build_queue_status_text(self, *, prefix: str = "") -> str:
        if not self._pending_navigation_queue:
            return prefix.strip()
        preview_limit = 3
        labels: list[str] = []
        for item in list(self._pending_navigation_queue)[:preview_limit]:
            label = str(item.get("label", "")).strip()
            if label:
                labels.append(label)
        if not labels:
            return prefix.strip()
        tail = "" if len(self._pending_navigation_queue) <= preview_limit else " ..."
        queue_preview = " -> ".join(labels) + tail
        if prefix.strip():
            return f"{prefix.strip()} | 대기열: {queue_preview}"
        return f"대기열: {queue_preview}"

    def _start_coordinate_navigation(self, x_m: float, y_m: float, *, meta: dict[str, object] | None = None) -> None:
        self._navigation_stop_requested = False
        self.st_sub.setText(f"선택 좌표: x={x_m:.2f}, y={y_m:.2f}")
        self.map_view.set_nav_target_preview(x_m, y_m)

        self.st_main.setText("이동 경로 계산 중...")
        self.st_sub.setText(f"목표 좌표: x={x_m:.2f}, y={y_m:.2f}")
        self.map_view.draw_path_to_target(x_m, y_m)
        path_len = self.map_view.get_path_length_m()
        if path_len is None:
            self.st_main.setText("경로 생성 실패")
            self.st_sub.setText("목표점 주변의 통로를 찾지 못했습니다.")
            return

        self.st_main.setText("좌표 이동 중...")
        queue_text = self._build_queue_status_text()
        if queue_text:
            self.st_sub.setText(f"목표까지 약 {path_len:.1f}m | {queue_text}")
        else:
            self.st_sub.setText(f"목표까지 약 {path_len:.1f}m")
        self._active_navigation_label = f"좌표 x={x_m:.2f}, y={y_m:.2f}"
        self._active_navigation_meta = dict(meta or {})
        self._active_navigation_meta.setdefault("kind", "coordinate")

        # 로봇에 이동 명령 전송
        if hasattr(self.main_window, "send_nav_to_coordinate"):
            ok, message = self.main_window.send_nav_to_coordinate(x_m, y_m)
            if not ok:
                self.st_main.setText("이동 명령 전송 실패")
                self.st_sub.setText(message)
                self.map_view.clear_route_path()
                self._active_navigation_label = ""
                self._start_next_queued_navigation()

    def refresh_quick_destinations(self) -> None:
        while self._destination_buttons:
            button = self._destination_buttons.pop()
            self._destination_button_layout.removeWidget(button)
            button.deleteLater()

        names: list[str] = []
        if hasattr(self.main_window, "get_quick_destination_names"):
            try:
                names = list(self.main_window.get_quick_destination_names(limit=3 if self.width() < 1480 else 4))
            except Exception:
                names = []

        for name in names:
            button = QPushButton(str(name))
            button.clicked.connect(lambda checked=False, place_name=str(name): self._navigate_to_named_place(place_name))
            self._destination_button_layout.insertWidget(max(self._destination_button_layout.count() - 1, 0), button)
            self._destination_buttons.append(button)

        if not names:
            placeholder = QPushButton("등록된 장소 없음")
            placeholder.setEnabled(False)
            self._destination_button_layout.insertWidget(max(self._destination_button_layout.count() - 1, 0), placeholder)
            self._destination_buttons.append(placeholder)

    def _navigate_to_named_place(self, place_name: str) -> None:
        place = None
        if hasattr(self.main_window, "get_named_place_lookup"):
            try:
                place = self.main_window.get_named_place_lookup().get(place_name)
            except Exception:
                place = None
        if not isinstance(place, dict):
            QMessageBox.warning(self, "장소 이동 실패", f"'{place_name}' 좌표를 찾지 못했습니다.")
            return

        try:
            x_m = float(place.get("x", 0.0))
            y_m = float(place.get("y", 0.0))
        except (TypeError, ValueError):
            QMessageBox.warning(self, "장소 이동 실패", f"'{place_name}' 좌표 값이 올바르지 않습니다.")
            return

        if self._has_active_navigation():
            self._enqueue_navigation({"kind": "named_place", "place_name": place_name, "label": place_name})
            return

        self._start_named_place_navigation(place_name, x_m, y_m)

    def _start_named_place_navigation(self, place_name: str, x_m: float, y_m: float, *, meta: dict[str, object] | None = None) -> None:
        self._navigation_stop_requested = False

        self.map_view.set_nav_target_preview(x_m, y_m)
        self.map_view.draw_path_to_target(x_m, y_m)
        path_len = self.map_view.get_path_length_m()
        if path_len is None:
            self.st_main.setText("경로 생성 실패")
            self.st_sub.setText(f"{place_name}까지의 통로를 찾지 못했습니다.")
            return

        self.st_main.setText(f"{place_name} 이동 중...")
        queue_text = self._build_queue_status_text()
        if queue_text:
            self.st_sub.setText(f"목표까지 약 {path_len:.1f}m | {queue_text}")
        else:
            self.st_sub.setText(f"목표까지 약 {path_len:.1f}m")
        self._active_navigation_label = place_name
        self._active_navigation_meta = dict(meta or {})
        self._active_navigation_meta.setdefault("kind", "named_place")
        self._active_navigation_meta.setdefault("place_name", place_name)

        if hasattr(self.main_window, "send_nav_to_named_place"):
            ok, message = self.main_window.send_nav_to_named_place(place_name)
            if not ok:
                self.st_main.setText("이동 명령 전송 실패")
                self.st_sub.setText(message)
                self.map_view.clear_route_path()
                self._active_navigation_label = ""
                self._start_next_queued_navigation()

    def _start_next_queued_navigation(self) -> None:
        if self._navigation_stop_requested:
            return
        if not self._pending_navigation_queue or self._has_active_navigation():
            return
        entry = self._pending_navigation_queue.popleft()
        kind = str(entry.get("kind", "")).strip()
        if kind == "coordinate":
            self._start_coordinate_navigation(
                float(entry.get("x", 0.0)),
                float(entry.get("y", 0.0)),
                meta=entry,
            )
            return
        if kind == "named_place":
            place_name = str(entry.get("place_name", "")).strip()
            place = self.main_window.get_named_place_lookup().get(place_name) if hasattr(self.main_window, "get_named_place_lookup") else None
            if isinstance(place, dict):
                try:
                    self._start_named_place_navigation(
                        place_name,
                        float(place.get("x", 0.0)),
                        float(place.get("y", 0.0)),
                        meta=entry,
                    )
                except (TypeError, ValueError):
                    pass

    def has_navigation_activity(self) -> bool:
        return self._has_active_navigation() or bool(self._pending_navigation_queue)

    def _stop_navigation(self) -> None:
        if not self._has_active_navigation() and not self._pending_navigation_queue:
            self.st_main.setText("안내 중지")
            self.st_sub.setText("중지할 안내 작업이 없습니다.")
            return

        cancelled = False
        cancel_message = ""
        if hasattr(self.main_window, "cancel_active_navigation"):
            ok, message = self.main_window.cancel_active_navigation()
            cancelled = bool(ok)
            cancel_message = str(message or "")
        elif hasattr(self.main_window, "submit_command_text"):
            ok, message = self.main_window.submit_command_text("중지해줘")
            cancelled = bool(ok)
            cancel_message = str(message or "")

        if not cancelled:
            QMessageBox.warning(self, "안내 중지 실패", cancel_message or "취소 요청을 전송하지 못했습니다.")
            return
        self._navigation_stop_requested = True
        self._queue_resume_token += 1
        self.map_view.clear_route_path()
        self._active_navigation_label = ""
        self._active_navigation_meta = {}
        self._pending_navigation_queue.clear()
        self.st_main.setText("안내 중지")
        self.st_sub.setText("이동 목표, 경로, 대기열을 초기화했습니다.")

    def update_ui(self):
        self.temp_lbl.setText(self.engine.temp)
        self.icon_lbl.setText(self.engine.icon)
        self.desc_lbl.setText(self.engine.desc)
        air_face_map = {
            "좋음": "😊",
            "보통": "🙂",
            "나쁨": "😷",
            "매우나쁨": "🤢",
        }
        self.air_face.setText(air_face_map.get(self.engine.air, "🙂"))
        self.air_txt.setText(f"미세먼지\n{self.engine.air}")
        self._update_eta()
        self._update_pose_tracking_status()

    def _update_pose_tracking_status(self) -> None:
        if self._last_pose is None or self._last_pose_time <= 0.0:
            self.st_pose.setText("📍 기본 위치 표시 중 · x=0.00, y=0.00")
            self.st_pose.setStyleSheet("color: #6B7280; font-weight: bold;")
            return

        age = time.monotonic() - self._last_pose_time
        x_m, y_m = self._last_pose
        source_suffix = f" · {self._last_pose_source}" if self._last_pose_source else ""
        heading_deg = int((math.degrees(self._last_yaw_rad) + 360.0) % 360.0)
        heading_suffix = f" · heading={heading_deg}°"

        if age <= 3.0:
            self.st_pose.setText(f"📍 실시간 좌표 수신 중{source_suffix} · x={x_m:.2f}, y={y_m:.2f}{heading_suffix}")
            self.st_pose.setStyleSheet("color: #10B981; font-weight: bold;")
            return

        self.st_pose.setText(f"📍 최근 좌표 유지 중{source_suffix} · x={x_m:.2f}, y={y_m:.2f}{heading_suffix}")
        self.st_pose.setStyleSheet("color: #F59E0B; font-weight: bold;")

    def _update_eta(self) -> None:
        path_len = self.map_view.get_path_length_m()
        if path_len is None or path_len < 0.1:
            self.st_eta.setText("")
            return
        if self._speed_samples:
            avg_speed = sum(self._speed_samples) / len(self._speed_samples)
        else:
            avg_speed = 0.0
        if avg_speed < 0.05:
            self.st_eta.setText(f"🗺 경로 거리: {path_len:.1f}m")
        else:
            eta_sec = path_len / avg_speed
            if eta_sec < 60:
                eta_str = f"{int(eta_sec)}초"
            else:
                eta_str = f"{int(eta_sec // 60)}분 {int(eta_sec % 60)}초"
            self.st_eta.setText(f"🗺 {path_len:.1f}m · 약 {eta_str} 후 도착")

    def _maybe_mark_arrival(self, x_m: float, y_m: float) -> None:
        if self._navigation_stop_requested:
            return
        target = self.map_view.get_nav_target_world()
        if target is None:
            return
        distance = ((float(target[0]) - x_m) ** 2 + (float(target[1]) - y_m) ** 2) ** 0.5
        if distance > self._arrival_distance_threshold_m:
            return

        label = self._active_navigation_label or "목표 지점"
        meta = dict(self._active_navigation_meta)
        next_label = ""
        if self._pending_navigation_queue:
            next_label = str(self._pending_navigation_queue[0].get("label", "")).strip()

        self.map_view.clear_route_path()
        self._active_navigation_label = ""
        self._active_navigation_meta = {}
        self._speed_samples.clear()
        self.st_main.setText("도착 완료")
        self.st_sub.setText(f"{label}에 도착했습니다.")
        self.st_eta.setText("")

        if hasattr(self.main_window, "on_navigation_arrived"):
            try:
                self.main_window.on_navigation_arrived(label, meta, next_label)
            except Exception:
                pass

        if self._pending_navigation_queue:
            dwell_ms = 200
            if hasattr(self.main_window, "get_navigation_dwell_ms"):
                try:
                    dwell_ms = int(self.main_window.get_navigation_dwell_ms())
                except Exception:
                    dwell_ms = 200
            resume_token = self._queue_resume_token

            def _resume_if_still_valid() -> None:
                if self._navigation_stop_requested:
                    return
                if resume_token != self._queue_resume_token:
                    return
                self._start_next_queued_navigation()

            QTimer.singleShot(max(0, dwell_ms), _resume_if_still_valid)
