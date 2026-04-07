from __future__ import annotations

from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import QLabel, QSizePolicy, QVBoxLayout, QWidget

from .face_controller import FaceController


class FacePage(QWidget):
    """얼굴 렌더링 결과를 표시하는 재사용 가능한 위젯."""

    clicked = Signal()

    def __init__(
        self,
        controller: FaceController | None = None,
        parent: QWidget | None = None,
        *,
        autonomous: bool = True,
        tick_interval_ms: int = 100,
    ) -> None:
        super().__init__(parent)
        self.controller = controller or FaceController(self)
        self._source_pixmap = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.addStretch(1)

        self.face_label = QLabel()
        self.face_label.setAlignment(Qt.AlignCenter)
        self.face_label.setMinimumSize(280, 280)
        self.face_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        # 라벨 위를 눌러도 부모 FacePage가 클릭 이벤트를 받도록 한다.
        self.face_label.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        layout.addWidget(self.face_label)
        layout.addStretch(1)

        self.controller.face_updated.connect(self._on_face_updated)
        if autonomous:
            self.controller.start_timer(tick_interval_ms)
        else:
            # 외부 루프를 쓰는 경우에도 첫 프레임은 즉시 갱신한다.
            self.controller.tick()

    def _apply_scaled_pixmap(self) -> None:
        if self._source_pixmap is None or self._source_pixmap.isNull():
            return
        target = self.face_label.size()
        if target.width() <= 0 or target.height() <= 0:
            return
        scaled = self._source_pixmap.scaled(target, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.face_label.setPixmap(scaled)

    def _on_face_updated(self, pixmap, _debug_info) -> None:
        self._source_pixmap = pixmap
        self._apply_scaled_pixmap()

    def resizeEvent(self, event) -> None:
        self._apply_scaled_pixmap()
        super().resizeEvent(event)

    def mousePressEvent(self, event) -> None:
        self.clicked.emit()
        super().mousePressEvent(event)
