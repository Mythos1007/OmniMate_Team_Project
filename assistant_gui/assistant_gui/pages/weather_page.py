from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QLabel,
    QPushButton,
    QFrame,
    QSizePolicy,
)


class WeatherForecastPage(QWidget):
    def __init__(self, engine, main_window):
        super().__init__()
        self.engine = engine
        self.main_window = main_window
        self._hourly_rows: list[dict] = []
        self._weekly_rows: list[dict] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        hdr = QHBoxLayout()
        hdr.setSpacing(10)
        title = QLabel("📅 상세 날씨 및 3일 예보")
        title.setProperty("class", "TitleText")

        subtitle = QLabel("오늘 시간대별 날씨와 3일 예보를 한눈에 볼 수 있어요")
        subtitle.setProperty("class", "SubText")

        title_wrap = QVBoxLayout()
        title_wrap.setSpacing(2)
        title_wrap.addWidget(title)
        title_wrap.addWidget(subtitle)

        back = QPushButton("닫기")
        back.setProperty("class", "PrimaryBtn")
        back.setFixedWidth(120)
        back.clicked.connect(lambda: self.main_window.switch_page(1, manual=True))
        hdr.addLayout(title_wrap)
        hdr.addStretch()
        hdr.addWidget(back)
        layout.addLayout(hdr)

        self.hourly_frame = QFrame()
        self.hourly_frame.setProperty("class", "CardFrame")
        self.hourly_frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.hourly_root = QVBoxLayout(self.hourly_frame)
        self.hourly_root.setContentsMargins(16, 14, 16, 14)
        self.hourly_root.setSpacing(10)
        self.hourly_root.setAlignment(Qt.AlignTop)
        hourly_title = QLabel("오늘 시간별 예보")
        hourly_title.setProperty("class", "TitleText")
        self.hourly_root.addWidget(hourly_title)
        self.h_lay = QGridLayout()
        self.h_lay.setHorizontalSpacing(18)
        self.h_lay.setVerticalSpacing(14)
        self.h_lay.setAlignment(Qt.AlignTop)
        self.hourly_root.addLayout(self.h_lay)

        self.weekly_frame = QFrame()
        self.weekly_frame.setProperty("class", "CardFrame")
        self.weekly_frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.weekly_root = QVBoxLayout(self.weekly_frame)
        self.weekly_root.setContentsMargins(16, 14, 16, 14)
        self.weekly_root.setSpacing(10)
        self.weekly_root.setAlignment(Qt.AlignTop)
        weekly_title = QLabel("3일 주간 예보")
        weekly_title.setProperty("class", "TitleText")
        self.weekly_root.addWidget(weekly_title)
        self.w_lay = QGridLayout()
        self.w_lay.setHorizontalSpacing(20)
        self.w_lay.setVerticalSpacing(14)
        self.w_lay.setAlignment(Qt.AlignTop)
        self.weekly_root.addLayout(self.w_lay)

        layout.addWidget(self.hourly_frame, 1)
        layout.addWidget(self.weekly_frame, 1)

        self.update_ui()

        if hasattr(self.engine, "weather_updated"):
            self.engine.weather_updated.connect(self.update_ui)

    def _clear_layout(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _is_dark_theme(self) -> bool:
        return getattr(self.main_window, "_theme_mode", "light") == "dark"

    def _create_data_card(
        self,
        lines: list[str],
        min_height: int = 160,
        min_width: int = 180,
        fixed_width: int | None = None,
        *,
        card_type: str = "default",
    ) -> QFrame:
        card = QFrame()
        card.setProperty("class", "CardFrame")
        is_dark = self._is_dark_theme()
        if card_type == "hourly" and is_dark:
            card.setStyleSheet(
                "QFrame {"
                " border-radius: 12px; padding: 6px;"
                " background-color: #263447;"
                " border: 1px solid #3B4F68;"
                "}"
            )
        elif card_type == "hourly":
            card.setStyleSheet(
                "QFrame {"
                " border-radius: 12px; padding: 6px;"
                " background-color: #F8FBFF;"
                " border: 1px solid #DCEBFF;"
                "}"
            )
        elif is_dark:
            card.setStyleSheet(
                "QFrame {"
                " border-radius: 12px; padding: 6px;"
                " background-color: #2A313D;"
                " border: 1px solid #454F5F;"
                "}"
            )
        else:
            card.setStyleSheet(
                "QFrame {"
                " border-radius: 12px; padding: 6px;"
                " background-color: #FAFAFB;"
                " border: 1px solid #E6E8EC;"
                "}"
            )
        if fixed_width is None:
            card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        else:
            card.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
        card.setMinimumWidth(min_width)
        if fixed_width is not None:
            card.setFixedWidth(fixed_width)
        card.setMinimumHeight(min_height)
        box = QVBoxLayout(card)
        box.setContentsMargins(12, 10, 12, 10)
        box.setSpacing(4)
        if card_type == "hourly":
            box.setSpacing(8)
            box.setAlignment(Qt.AlignCenter)
        else:
            box.setAlignment(Qt.AlignTop)

        for i, text in enumerate(lines):
            lbl = QLabel(text)
            if card_type == "hourly":
                lbl.setAlignment(Qt.AlignCenter)
                if i == 0:
                    lbl.setStyleSheet("font-size: 30px; font-weight: bold; border: none; background: transparent;")
                elif i == 1:
                    lbl.setStyleSheet("font-size: 88px; border: none; background: transparent;")
                    lbl.setMinimumHeight(124)
                    lbl.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
                else:
                    lbl.setStyleSheet("font-size: 34px; font-weight: bold; border: none; background: transparent;")
            else:
                lbl.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
                if i == 1:
                    lbl.setStyleSheet("font-size: 64px; border: none; background: transparent;")
                    lbl.setMinimumHeight(112)
                    lbl.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
                elif i == 0:
                    lbl.setStyleSheet("font-size: 20px; font-weight: bold; border: none; background: transparent;")
                elif i == 3:
                    lbl.setStyleSheet("font-size: 22px; font-weight: bold; border: none; background: transparent; margin-top: -6px;")
                else:
                    lbl.setStyleSheet("font-size: 22px; font-weight: bold; border: none; background: transparent;")
            box.addWidget(lbl)
        card.adjustSize()
        return card

    def _hourly_card_width(self, item_count: int) -> int:
        if item_count <= 0:
            return 175
        usable = max(1, self.hourly_frame.width() - 48)
        total_spacing = max(0, (item_count - 1) * self.h_lay.horizontalSpacing())
        width = (usable - total_spacing) // item_count
        return max(145, min(210, width))

    def _fill_grid(
        self,
        layout: QGridLayout,
        cards: list[QFrame],
        cols: int,
        *,
        stretch_columns: bool,
        valign_top: bool,
    ):
        for idx, card in enumerate(cards):
            row = idx // cols
            col = idx % cols
            layout.addWidget(card, row, col)
        if valign_top:
            layout.setAlignment(Qt.AlignTop | Qt.AlignHCenter)
        else:
            layout.setAlignment(Qt.AlignVCenter | Qt.AlignHCenter)
        for col in range(cols):
            layout.setColumnStretch(col, 1 if stretch_columns else 0)
        rows = (len(cards) + cols - 1) // cols
        layout.setRowStretch(rows, 1)

    @staticmethod
    def _air_emoji(label: str) -> str:
        return {
            "좋음": "😊",
            "보통": "🙂",
            "나쁨": "😷",
            "매우나쁨": "🤢",
        }.get(label, "🙂")

    def update_ui(self):
        self._clear_layout(self.h_lay)
        self._clear_layout(self.w_lay)

        self._hourly_rows = getattr(self.engine, "forecast_hourly", [])[:6]
        self._weekly_rows = getattr(self.engine, "forecast_weekly", [])[:3]
        self._render_sections()

    def _render_sections(self):
        self._clear_layout(self.h_lay)
        self._clear_layout(self.w_lay)

        hourly = self._hourly_rows
        weekly = self._weekly_rows

        if not hourly:
            no_data = QLabel("시간별 예보 데이터 없음")
            no_data.setAlignment(Qt.AlignCenter)
            no_data.setProperty("class", "SubText")
            self.h_lay.addWidget(no_data, 0, 0, Qt.AlignCenter)
            self.h_lay.setColumnStretch(0, 1)
            self.h_lay.setRowStretch(0, 1)
        else:
            h_cards: list[QFrame] = []
            h_width = self._hourly_card_width(len(hourly))
            for row in hourly:
                card = self._create_data_card([
                    str(row.get("time", "--:--")),
                    str(row.get("icon", "☁️")),
                    f"{row.get('temp', '--')}°",
                ], min_height=275, min_width=145, fixed_width=h_width, card_type="hourly")
                h_cards.append(card)
            h_cols = len(h_cards)
            self._fill_grid(self.h_lay, h_cards, h_cols, stretch_columns=False, valign_top=False)

        if not weekly:
            no_data = QLabel("주간 예보 데이터 없음")
            no_data.setAlignment(Qt.AlignCenter)
            no_data.setProperty("class", "SubText")
            self.w_lay.addWidget(no_data, 0, 0, Qt.AlignCenter)
            self.w_lay.setColumnStretch(0, 1)
            self.w_lay.setRowStretch(0, 1)
        else:
            w_cards: list[QFrame] = []
            for row in weekly:
                air = getattr(self.engine, "air", "보통")
                card = self._create_data_card([
                    str(row.get("date", "-")),
                    str(row.get("icon", "☁️")),
                    str(row.get("temp_range", "--°/--°")),
                    f"미세먼지 {self._air_emoji(str(air))} {air}",
                ], min_height=290, min_width=240)
                w_cards.append(card)
            w_cols = len(w_cards)
            self._fill_grid(self.w_lay, w_cards, w_cols, stretch_columns=True, valign_top=True)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._render_sections()
