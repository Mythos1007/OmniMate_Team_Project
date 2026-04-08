from __future__ import annotations

import time

from PySide6.QtCore import Qt, Signal, QPointF, QRect
from PySide6.QtGui import QPixmap, QPainter, QTransform, QColor, QPen, QPainterPath
from PySide6.QtWidgets import QWidget

try:
    from assistant_gui.route_path_overlay import RoutePathOverlay
    from assistant_gui.path_planner import RoutePathPlanner
except ModuleNotFoundError:
    from route_path_overlay import RoutePathOverlay
    from path_planner import RoutePathPlanner


class RotatedMapView(QWidget):
    """Render map and overlays, while planning in rotated map coordinates."""

    map_clicked = Signal(float, float)

    def __init__(
        self,
        *,
        map_path: str,
        coord_rotation_deg: float = 28.0,
        resolution_m_per_px: float = 0.05,
        origin_xy: tuple[float, float] = (-10.0, -10.0),
        reference_size_px: tuple[int, int] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setMinimumHeight(170)
        self._map_path = map_path
        self._coord_rotation_deg = coord_rotation_deg
        self._resolution = resolution_m_per_px
        self._origin_x, self._origin_y = origin_xy
        self._reference_size_px = reference_size_px
        self._base_map: QPixmap | None = None
        self._coord_rot_tf: QTransform | None = None
        self._robot_rot_pt: QPointF | None = None
        self._target_rot_pt: QPointF | None = None
        self._path_points: list = []
        self._pose_is_default = True
        self._route_overlay = RoutePathOverlay(max_points=700, min_distance_px=2.0)
        self._path_planner = RoutePathPlanner(
            wall_threshold=200,
            wall_inflate_pixels=5,
            max_snap_distance=40,
        )
        self._cached_obstacle_map = None
        self._nav_target_world: tuple[float, float] | None = None
        self._last_replan_ts = 0.0
        self._last_replan_robot_pt: QPointF | None = None
        self._load_map()

    def _load_map(self) -> None:
        pixmap = QPixmap(self._map_path)
        if pixmap.isNull():
            self._base_map = None
            self._route_overlay.reset()
            self.update()
            return
        self._base_map = pixmap
        self._cached_obstacle_map = None
        self._rebuild_coord_transform()
        if self._robot_rot_pt is None:
            self.set_robot_world_pose(0.0, 0.0, is_default=True)

    def _rebuild_coord_transform(self) -> None:
        if self._base_map is None:
            self._coord_rot_tf = None
            return
        w = float(self._base_map.width())
        h = float(self._base_map.height())
        tf = QTransform()
        tf.translate(w / 2.0, h / 2.0)
        tf.rotate(self._coord_rotation_deg)
        tf.translate(-w / 2.0, -h / 2.0)
        self._coord_rot_tf = tf

    def set_robot_world_pose(self, x_m: float, y_m: float, *, is_default: bool = False) -> None:
        if self._base_map is None or self._coord_rot_tf is None:
            return
        display_w = float(self._base_map.width())
        display_h = float(self._base_map.height())

        if self._reference_size_px is not None and self._reference_size_px[0] > 0 and self._reference_size_px[1] > 0:
            ref_w = float(self._reference_size_px[0])
            ref_h = float(self._reference_size_px[1])
        else:
            ref_w = display_w
            ref_h = display_h

        px_ref = (x_m - self._origin_x) / self._resolution
        py_ref = ref_h - ((y_m - self._origin_y) / self._resolution)
        px_ref = max(0.0, min(ref_w - 1.0, px_ref))
        py_ref = max(0.0, min(ref_h - 1.0, py_ref))

        px = px_ref * (display_w / ref_w)
        py = py_ref * (display_h / ref_h)
        self._robot_rot_pt = self._coord_rot_tf.map(QPointF(px, py))
        self._pose_is_default = is_default
        if is_default:
            self._route_overlay.reset()
            self._nav_target_world = None
        else:
            self._route_overlay.add_point(self._robot_rot_pt)
            if self._nav_target_world is not None:
                now = time.monotonic()
                should_replan = False
                if now - self._last_replan_ts >= 0.25:
                    if self._last_replan_robot_pt is None:
                        should_replan = True
                    else:
                        dx = self._robot_rot_pt.x() - self._last_replan_robot_pt.x()
                        dy = self._robot_rot_pt.y() - self._last_replan_robot_pt.y()
                        should_replan = (dx * dx + dy * dy) >= 9.0
                if should_replan:
                    wx, wy = self._nav_target_world
                    self.draw_path_to_target(wx, wy)
                    return
        self.update()

    def get_path_length_m(self) -> float | None:
        """현재 경로의 남은 거리 미터값 반환 기능. 경로 부재 시 None 반환."""
        if len(self._path_points) < 2 or self._base_map is None:
            return None
        display_w = float(self._base_map.width())
        ref_size = self._reference_size_px or (self._base_map.width(), self._base_map.height())
        ref_w = float(ref_size[0])
        px_to_ref = ref_w / display_w if display_w > 0 else 1.0
        total = 0.0
        for i in range(len(self._path_points) - 1):
            p1, p2 = self._path_points[i], self._path_points[i + 1]
            total += ((p2.x() - p1.x()) ** 2 + (p2.y() - p1.y()) ** 2) ** 0.5
        return total * px_to_ref * self._resolution

    def set_nav_target_preview(self, target_world_x: float, target_world_y: float) -> None:
        """클릭 위치 미리보기 점 표시 기능. 경로 계획은 제외."""
        if self._base_map is None or self._coord_rot_tf is None:
            return
        ref_size = self._reference_size_px or (self._base_map.width(), self._base_map.height())
        ref_w, ref_h = float(ref_size[0]), float(ref_size[1])
        display_w, display_h = float(self._base_map.width()), float(self._base_map.height())
        px_ref = (target_world_x - self._origin_x) / self._resolution
        py_ref = ref_h - ((target_world_y - self._origin_y) / self._resolution)
        px_ref = max(0.0, min(ref_w - 1.0, px_ref))
        py_ref = max(0.0, min(ref_h - 1.0, py_ref))
        goal_display_px = px_ref * (display_w / ref_w)
        goal_display_py = py_ref * (display_h / ref_h)
        self._target_rot_pt = self._coord_rot_tf.map(QPointF(goal_display_px, goal_display_py))
        self._path_points = []
        self.update()

    def clear_nav_target_preview(self) -> None:
        """미리보기 점/경로 초기화 기능. nav_target_world 값은 유지."""
        self._target_rot_pt = None
        self._path_points = []
        self.update()

    def clear_route_path(self) -> None:
        self._route_overlay.reset()
        self._target_rot_pt = None
        self._path_points = []
        self._nav_target_world = None
        self.update()

    def draw_path_to_target(self, target_world_x: float, target_world_y: float) -> None:
        if self._base_map is None or self._coord_rot_tf is None or self._robot_rot_pt is None:
            return

        self._nav_target_world = (float(target_world_x), float(target_world_y))

        ref_size = self._reference_size_px or (self._base_map.width(), self._base_map.height())
        ref_w, ref_h = float(ref_size[0]), float(ref_size[1])
        display_w, display_h = float(self._base_map.width()), float(self._base_map.height())

        px_ref = (target_world_x - self._origin_x) / self._resolution
        py_ref = ref_h - ((target_world_y - self._origin_y) / self._resolution)
        px_ref = max(0.0, min(ref_w - 1.0, px_ref))
        py_ref = max(0.0, min(ref_h - 1.0, py_ref))

        goal_display_px = px_ref * (display_w / ref_w)
        goal_display_py = py_ref * (display_h / ref_h)
        self._target_rot_pt = self._coord_rot_tf.map(QPointF(goal_display_px, goal_display_py))

        if self._cached_obstacle_map is None:
            self._cached_obstacle_map = self._path_planner.build_obstacle_map(self._base_map)
        obstacle_map = self._cached_obstacle_map
        if obstacle_map is None:
            self._path_points = []
            self.update()
            return

        # Plan directly in image pixel space — same space as _robot_rot_pt / _target_rot_pt.
        # No coordinate transform needed here; world coords are only used when sending nav commands.
        start_xy = (float(self._robot_rot_pt.x()), float(self._robot_rot_pt.y()))
        goal_xy = (float(self._target_rot_pt.x()), float(self._target_rot_pt.y()))

        path = self._path_planner.plan(
            start_xy,
            goal_xy,
            obstacle_map,
            start_radius=40,
            goal_radius=40,
        )

        if not path:
            self._path_points = []
            self.update()
            return

        self._path_points = [QPointF(p[0], p[1]) for p in path]
        if self._path_points:
            self._path_points[0] = QPointF(self._robot_rot_pt)
            self._path_points[-1] = QPointF(self._target_rot_pt)
        self._last_replan_ts = time.monotonic()
        self._last_replan_robot_pt = QPointF(self._robot_rot_pt)
        self.update()

    def _current_draw_geometry(self) -> tuple[float, float, float, float, float] | None:
        if self._base_map is None:
            return None
        rw = float(self._base_map.width())
        rh = float(self._base_map.height())
        if rw <= 0.0 or rh <= 0.0:
            return None
        scale = max(self.width() / rw, self.height() / rh)
        draw_w = max(1.0, rw * scale)
        draw_h = max(1.0, rh * scale)
        x0 = (self.width() - draw_w) / 2.0
        y0 = (self.height() - draw_h) / 2.0
        return scale, x0, y0, rw, rh

    def mousePressEvent(self, event) -> None:
        if event.button() != Qt.LeftButton:
            super().mousePressEvent(event)
            return
        if self._base_map is None or self._coord_rot_tf is None:
            super().mousePressEvent(event)
            return

        geom = self._current_draw_geometry()
        if geom is None:
            super().mousePressEvent(event)
            return

        scale, x0, y0, rw, rh = geom
        click_x = float(event.position().x())
        click_y = float(event.position().y())

        rot_px = (click_x - x0) / scale
        rot_py = (click_y - y0) / scale
        rot_px = max(0.0, min(rw - 1.0, rot_px))
        rot_py = max(0.0, min(rh - 1.0, rot_py))

        inv_tf, invertible = self._coord_rot_tf.inverted()
        if not invertible:
            super().mousePressEvent(event)
            return

        unrot_pt = inv_tf.map(QPointF(rot_px, rot_py))
        unrot_px = max(0.0, min(rw - 1.0, float(unrot_pt.x())))
        unrot_py = max(0.0, min(rh - 1.0, float(unrot_pt.y())))

        if self._reference_size_px is not None and self._reference_size_px[0] > 0 and self._reference_size_px[1] > 0:
            ref_w = float(self._reference_size_px[0])
            ref_h = float(self._reference_size_px[1])
        else:
            ref_w = rw
            ref_h = rh

        px_ref = unrot_px * (ref_w / rw)
        py_ref = unrot_py * (ref_h / rh)
        world_x = self._origin_x + (px_ref * self._resolution)
        world_y = self._origin_y + ((ref_h - py_ref) * self._resolution)

        self.map_clicked.emit(float(world_x), float(world_y))
        super().mousePressEvent(event)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(), QColor("#E5E7EB"))

        if self._base_map is None:
            painter.setPen(QColor("#FFFFFF"))
            painter.drawText(self.rect(), Qt.AlignCenter, "지도 이미지를 찾지 못했습니다")
            return

        rw = self._base_map.width()
        rh = self._base_map.height()
        if rw <= 0 or rh <= 0:
            return

        scale = max(self.width() / rw, self.height() / rh)
        draw_w = max(1, int(rw * scale))
        draw_h = max(1, int(rh * scale))
        x0 = (self.width() - draw_w) // 2
        y0 = (self.height() - draw_h) // 2
        target = QRect(x0, y0, draw_w, draw_h)
        painter.drawPixmap(target, self._base_map)
        self._route_overlay.draw(painter, scale=scale, offset_x=float(x0), offset_y=float(y0))

        if len(self._path_points) > 1:
            display_points = [
                QPointF(x0 + p.x() * scale, y0 + p.y() * scale)
                for p in self._path_points
            ]

            path = QPainterPath(display_points[0])
            for pt in display_points[1:]:
                path.lineTo(pt)

            painter.save()

            # Base guide line + main route line for stronger visibility on dark maps.
            guide_pen = QPen(QColor("#B8C0CC"), 2.0)
            guide_pen.setCapStyle(Qt.RoundCap)
            guide_pen.setJoinStyle(Qt.RoundJoin)
            painter.setPen(guide_pen)
            painter.drawPath(path)

            route_pen = QPen(QColor("#FF3B30"), 3.0)
            route_pen.setCapStyle(Qt.RoundCap)
            route_pen.setJoinStyle(Qt.RoundJoin)
            painter.setPen(route_pen)
            painter.drawPath(path)

            painter.restore()

        if self._target_rot_pt is not None:
            tar_x = x0 + self._target_rot_pt.x() * scale
            tar_y = y0 + self._target_rot_pt.y() * scale
            target_pen = QPen(QColor("#FF6B35"), 2.0)
            painter.setPen(target_pen)
            painter.setBrush(QColor("#FFE5D9"))
            painter.drawEllipse(int(tar_x - 10), int(tar_y - 10), 20, 20)
            painter.drawLine(int(tar_x - 6), int(tar_y - 6), int(tar_x + 6), int(tar_y + 6))
            painter.drawLine(int(tar_x - 6), int(tar_y + 6), int(tar_x + 6), int(tar_y - 6))

        if self._robot_rot_pt is not None:
            mx = x0 + self._robot_rot_pt.x() * scale
            my = y0 + self._robot_rot_pt.y() * scale
        else:
            mx = float(self.width() / 2.0)
            my = float(self.height() / 2.0)

        label = "현위치"
        mx = float(min(max(mx, 6.0), max(6.0, self.width() - 6.0)))
        my = float(min(max(my, 6.0), max(6.0, self.height() - 6.0)))
        painter.setPen(QPen(QColor("#FFFFFF"), 2))
        painter.setBrush(QColor("#EF4444"))
        painter.drawEllipse(QPointF(mx, my), 9.0, 9.0)
        painter.setPen(QPen(QColor("#FFFFFF"), 2))
        painter.drawLine(QPointF(mx - 7.0, my), QPointF(mx + 7.0, my))
        painter.drawLine(QPointF(mx, my - 7.0), QPointF(mx, my + 7.0))

        fm = painter.fontMetrics()
        label_w = fm.horizontalAdvance(label) + 12
        label_h = fm.height() + 6
        label_x = float(mx - (label_w / 2.0))
        label_x = float(min(max(label_x, 6.0), max(6.0, self.width() - label_w - 6.0)))

        label_y = float(my - 14.0 - label_h)
        if label_y < 6.0:
            label_y = float(min(self.height() - label_h - 6.0, my + 14.0))

        badge_rect = QRect(int(label_x), int(label_y), int(label_w), int(label_h))
        painter.setPen(QPen(QColor("#065F46"), 1))
        painter.setBrush(QColor("#ECFDF5"))
        painter.drawRoundedRect(badge_rect, 6, 6)

        painter.setPen(QPen(QColor("#059669"), 1))
        painter.drawText(badge_rect, Qt.AlignCenter, label)
