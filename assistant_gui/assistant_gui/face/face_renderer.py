from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QPixmap
from PySide6.QtSvg import QSvgRenderer

from .face_animation_manager import FaceOverlayState
from .face_asset_repository import AssetInfo, FaceAssetRepository
from .face_models import BlinkState, FaceContext, MouthState, TempExpression


@dataclass(slots=True)
class FaceRenderDebugInfo:
    display_state: str
    temp_expression: str
    blink_state: str
    mouth_state: str
    speaking_active: bool
    base_asset_name: str
    temp_asset_name: str
    blink_asset_name: str
    mouth_asset_name: str
    base_asset_exists: bool
    temp_asset_exists: bool
    blink_asset_exists: bool
    mouth_asset_exists: bool
    base_fallback_used: bool
    warnings: str


class FaceRenderer:
    """base + temp + overlay 레이어를 합성해 얼굴 pixmap을 만든다."""

    def __init__(self, repository: FaceAssetRepository) -> None:
        self._repo = repository

    @staticmethod
    def _pixmap_from_svg(path: Path, size: int) -> QPixmap:
        renderer = QSvgRenderer(path.as_posix())
        pm = QPixmap(size, size)
        pm.fill(Qt.transparent)
        painter = QPainter(pm)
        renderer.render(painter)
        painter.end()
        return pm

    @staticmethod
    def _pixmap_from_image(path: Path, size: int) -> QPixmap:
        pm = QPixmap(path.as_posix())
        if pm.isNull():
            return QPixmap(size, size)
        return pm.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)

    def _load_layer(self, path: Path | None, size: int) -> QPixmap | None:
        if path is None:
            return None
        suffix = path.suffix.lower()
        if suffix == ".svg":
            return self._pixmap_from_svg(path, size)
        if suffix in {".png", ".jpg", ".jpeg", ".webp"}:
            return self._pixmap_from_image(path, size)
        return None

    @staticmethod
    def _draw_fallback(size: int, text: str, context: FaceContext, overlay: FaceOverlayState) -> QPixmap:
        pm = QPixmap(size, size)
        pm.fill(QColor("#E5E7EB"))
        painter = QPainter(pm)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(QColor("#111827"))
        painter.setBrush(QColor("#93C5FD"))
        painter.drawEllipse(18, 18, size - 36, size - 36)

        cx = size / 2.0
        cy = size / 2.0
        face_radius = (size - 36) / 2.0

        eye_pen = QPen(QColor("#1D4ED8"), max(3, int(size * 0.014)))
        eye_pen.setCapStyle(Qt.RoundCap)
        painter.setPen(eye_pen)
        painter.setBrush(QColor("#1D4ED8"))

        eye_dx = face_radius * 0.36
        eye_y = cy - face_radius * 0.22
        eye_w = face_radius * 0.12
        eye_h = face_radius * 0.16

        if overlay.blink_state == BlinkState.OPEN:
            if context.temp_expression == TempExpression.SURPRISED:
                eye_w = face_radius * 0.15
                eye_h = face_radius * 0.2
            painter.drawEllipse(QRectF(cx - eye_dx - eye_w, eye_y - eye_h, eye_w * 2, eye_h * 2))
            painter.drawEllipse(QRectF(cx + eye_dx - eye_w, eye_y - eye_h, eye_w * 2, eye_h * 2))
        else:
            painter.drawLine(cx - eye_dx - eye_w, eye_y, cx - eye_dx + eye_w, eye_y)
            painter.drawLine(cx + eye_dx - eye_w, eye_y, cx + eye_dx + eye_w, eye_y)

        mouth_pen = QPen(QColor("#1D4ED8"), max(4, int(size * 0.018)))
        mouth_pen.setCapStyle(Qt.RoundCap)
        painter.setPen(mouth_pen)
        painter.setBrush(Qt.NoBrush)

        mouth_rect = QRectF(
            cx - face_radius * 0.28,
            cy + face_radius * 0.12,
            face_radius * 0.56,
            face_radius * 0.34,
        )

        speaking_active = context.tts_active and context.speaking_enabled
        if speaking_active:
            if overlay.mouth_state == MouthState.IDLE:
                painter.drawLine(mouth_rect.left(), mouth_rect.center().y(), mouth_rect.right(), mouth_rect.center().y())
            elif overlay.mouth_state == MouthState.FRAME_1:
                painter.drawArc(mouth_rect, 200 * 16, 140 * 16)
            elif overlay.mouth_state == MouthState.FRAME_2:
                open_rect = QRectF(cx - face_radius * 0.11, cy + face_radius * 0.16, face_radius * 0.22, face_radius * 0.2)
                painter.drawEllipse(open_rect)
            else:
                open_rect = QRectF(cx - face_radius * 0.16, cy + face_radius * 0.16, face_radius * 0.32, face_radius * 0.24)
                painter.drawEllipse(open_rect)
        elif context.temp_expression in {TempExpression.HAPPY, TempExpression.GREETING}:
            painter.drawArc(mouth_rect, 200 * 16, 140 * 16)
        elif context.temp_expression == TempExpression.APOLOGETIC:
            sad_rect = QRectF(mouth_rect.left(), mouth_rect.top() + face_radius * 0.14, mouth_rect.width(), mouth_rect.height())
            painter.drawArc(sad_rect, 20 * 16, 140 * 16)
        elif context.temp_expression == TempExpression.SURPRISED:
            surprised_rect = QRectF(cx - face_radius * 0.1, cy + face_radius * 0.16, face_radius * 0.2, face_radius * 0.2)
            painter.drawEllipse(surprised_rect)
        elif context.display_state.value == "thinking":
            painter.drawLine(mouth_rect.left(), mouth_rect.center().y(), mouth_rect.right(), mouth_rect.center().y())
        elif context.display_state.value in {"error", "emergency_stop", "low_battery"}:
            sad_rect = QRectF(mouth_rect.left(), mouth_rect.top() + face_radius * 0.14, mouth_rect.width(), mouth_rect.height())
            painter.drawArc(sad_rect, 20 * 16, 140 * 16)
        else:
            painter.drawArc(mouth_rect, 200 * 16, 140 * 16)

        painter.setPen(QColor("#1D4ED8"))
        painter.setFont(QFont("Sans Serif", 10, QFont.Bold))
        painter.drawText(pm.rect().adjusted(0, int(size * 0.31), 0, 0), Qt.AlignHCenter, text)
        painter.end()
        return pm

    @staticmethod
    def _layer_warning(info: AssetInfo) -> str:
        return info.warning.strip()

    def render(self, *, context: FaceContext, overlay: FaceOverlayState, size: int = 260) -> tuple[QPixmap, FaceRenderDebugInfo]:
        base_info = self._repo.get_base_asset_info(context.display_state)
        temp_info = self._repo.get_temp_asset_info(context.temp_expression)
        blink_info = self._repo.get_blink_asset_info(overlay.blink_state)
        mouth_info = self._repo.get_mouth_asset_info(overlay.mouth_state)

        canvas = self._load_layer(base_info.path, size)
        if canvas is None or canvas.isNull():
            canvas = self._draw_fallback(size, f"BASE\\n{context.display_state.value}", context, overlay)

        painter = QPainter(canvas)
        painter.setRenderHint(QPainter.Antialiasing)

        speaking_active = context.tts_active and context.speaking_enabled
        for layer in (
            self._load_layer(temp_info.path, size),
            self._load_layer(blink_info.path, size),
            self._load_layer(mouth_info.path, size) if speaking_active else None,
        ):
            if layer is not None and not layer.isNull():
                painter.drawPixmap(0, 0, layer)

        painter.end()

        warnings = [
            self._layer_warning(base_info),
            self._layer_warning(temp_info),
            self._layer_warning(blink_info),
            self._layer_warning(mouth_info),
        ]
        warning_text = " | ".join([w for w in warnings if w])

        debug = FaceRenderDebugInfo(
            display_state=context.display_state.value,
            temp_expression=context.temp_expression.value,
            blink_state=overlay.blink_state.value,
            mouth_state=overlay.mouth_state.value,
            speaking_active=speaking_active,
            base_asset_name=base_info.resolved_name,
            temp_asset_name=temp_info.resolved_name,
            blink_asset_name=blink_info.resolved_name,
            mouth_asset_name=mouth_info.resolved_name,
            base_asset_exists=base_info.exists,
            temp_asset_exists=temp_info.exists,
            blink_asset_exists=blink_info.exists,
            mouth_asset_exists=mouth_info.exists,
            base_fallback_used=base_info.fallback_used,
            warnings=warning_text,
        )
        return canvas, debug
