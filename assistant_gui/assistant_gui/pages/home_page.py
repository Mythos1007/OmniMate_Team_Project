from __future__ import annotations

import ast
import os
import re
import time
from collections import deque
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QFrame, QLabel, QPushButton, QGridLayout, QMessageBox

try:
    from assistant_gui.map_view import RotatedMapView
except ModuleNotFoundError:
    from map_view import RotatedMapView


class HomePage(QWidget):
    def __init__(self, main_window, engine):
        super().__init__()
        self.main_window, self.engine = main_window, engine
        layout = QHBoxLayout(self)
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
        self._speed_samples: deque[float] = deque(maxlen=8)
        map_lay.addWidget(self.map_view, stretch=1)
        dest_lay = QHBoxLayout()
        for d in ["로비", "회의실 A", "탕비실"]:
            dest_lay.addWidget(QPushButton(d))
        stop_btn = QPushButton("안내 중지")
        stop_btn.setProperty("class", "StopBtn")
        dest_lay.addWidget(stop_btn)
        map_lay.addLayout(dest_lay)
        left_layout.addWidget(map_frame)
        layout.addLayout(left_layout, stretch=6)

        right_layout = QVBoxLayout()

        self.weather_card = QPushButton()
        self.weather_card.setObjectName("weather_card_btn")
        self.weather_card.setMinimumHeight(180)
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
        status_lay.addWidget(st_title)
        status_lay.addWidget(self.st_main)
        status_lay.addWidget(self.st_sub)
        status_lay.addWidget(self.st_eta)
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
            grid.addWidget(btn, positions[i][0], positions[i][1])
        right_layout.addWidget(menu_frame)

        layout.addLayout(right_layout, stretch=4)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_ui)
        self.timer.start(2000)

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

    def update_robot_pose(self, x_m: float, y_m: float) -> None:
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
        self.map_view.set_robot_world_pose(x_m, y_m, is_default=False)

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
        self.st_sub.setText(f"선택 좌표: x={x_m:.2f}, y={y_m:.2f}")

        # 먼저 점 미리보기 (경로 계획 전, 사용자가 위치 확인 가능)
        self.map_view.set_nav_target_preview(x_m, y_m)

        dlg = QMessageBox(self)
        dlg.setWindowTitle("좌표 이동")
        dlg.setText(f"이 좌표(x={x_m:.2f}, y={y_m:.2f})로 로봇을 이동시키겠습니까?")
        dlg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        dlg.setDefaultButton(QMessageBox.No)
        dlg.button(QMessageBox.Yes).setText("확인")
        dlg.button(QMessageBox.No).setText("취소")
        if dlg.exec() != QMessageBox.Yes:
            self.map_view.clear_nav_target_preview()
            return

        # 경로 표시 (점은 이미 표시됨, 이제 경로 계획)
        self.st_main.setText("이동 경로 계산 중...")
        self.st_sub.setText(f"목표 좌표: x={x_m:.2f}, y={y_m:.2f}")
        self.map_view.draw_path_to_target(x_m, y_m)
        path_len = self.map_view.get_path_length_m()
        if path_len is None:
            self.st_main.setText("경로 생성 실패")
            self.st_sub.setText("목표점 주변의 통로를 찾지 못했습니다.")
            return

        self.st_main.setText("좌표 이동 중...")
        self.st_sub.setText(f"목표까지 약 {path_len:.1f}m")

        # 로봇에 이동 명령 전송
        if hasattr(self.main_window, "send_nav_to_coordinate"):
            ok, message = self.main_window.send_nav_to_coordinate(x_m, y_m)
            if not ok:
                self.st_main.setText("이동 명령 전송 실패")
                self.st_sub.setText(message)

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
