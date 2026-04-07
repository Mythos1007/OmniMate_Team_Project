from __future__ import annotations

import math
from typing import List

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen


class RoutePathOverlay:
    """Keeps and draws a smooth trail of robot movement on top of the map."""

    def __init__(self, *, max_points: int = 600, min_distance_px: float = 2.5) -> None:
        self._max_points = max(10, int(max_points))
        self._min_distance_px = max(0.1, float(min_distance_px))
        self._points: List[QPointF] = []

    def reset(self) -> None:
        self._points.clear()

    def add_point(self, point: QPointF) -> None:
        if not self._points:
            self._points.append(QPointF(point))
            return

        last = self._points[-1]
        dx = point.x() - last.x()
        dy = point.y() - last.y()
        if math.hypot(dx, dy) < self._min_distance_px:
            return

        self._points.append(QPointF(point))
        overflow = len(self._points) - self._max_points
        if overflow > 0:
            del self._points[:overflow]

    def draw(self, painter: QPainter, *, scale: float, offset_x: float, offset_y: float) -> None:
        if len(self._points) < 2:
            return

        display_points = [
            QPointF(offset_x + pt.x() * scale, offset_y + pt.y() * scale)
            for pt in self._points
        ]

        path = QPainterPath(display_points[0])
        if len(display_points) == 2:
            path.lineTo(display_points[1])
        else:
            for i in range(1, len(display_points) - 1):
                curr = display_points[i]
                nxt = display_points[i + 1]
                mid = QPointF((curr.x() + nxt.x()) * 0.5, (curr.y() + nxt.y()) * 0.5)
                path.quadTo(curr, mid)
            path.lineTo(display_points[-1])

        painter.save()

        glow = QColor("#3B82F6")
        glow.setAlpha(70)
        glow_pen = QPen(glow, 10.0)
        glow_pen.setCapStyle(Qt.RoundCap)
        glow_pen.setJoinStyle(Qt.RoundJoin)
        painter.setPen(glow_pen)
        painter.setBrush(QColor("transparent"))
        painter.drawPath(path)

        line_pen = QPen(QColor("#2563EB"), 4.0)
        line_pen.setCapStyle(Qt.RoundCap)
        line_pen.setJoinStyle(Qt.RoundJoin)
        painter.setPen(line_pen)
        painter.drawPath(path)

        painter.restore()
