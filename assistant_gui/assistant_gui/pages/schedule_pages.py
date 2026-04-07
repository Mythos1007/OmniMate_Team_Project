from __future__ import annotations

from PySide6.QtCore import Qt, QDate, QTime, QPropertyAnimation
from PySide6.QtGui import QColor, QBrush, QPainter, QTextCharFormat
from PySide6.QtWidgets import (
    QWidget,
    QCalendarWidget,
    QHBoxLayout,
    QVBoxLayout,
    QFrame,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QCheckBox,
    QMessageBox,
    QGraphicsOpacityEffect,
    QFormLayout,
    QDateEdit,
    QTimeEdit,
    QLineEdit,
    QSizePolicy,
    QGridLayout,
)


class CalendarWidgetModified(QCalendarWidget):
    def __init__(self, parent=None, schedule_mgr=None):
        super().__init__(parent)
        self.schedule_mgr = schedule_mgr
        self.point_color = QColor("#3B82F6")
        self.point_color_selected = QColor("#1E40AF")

    def set_marker_colors(self, normal: QColor, selected: QColor):
        self.point_color = QColor(normal)
        self.point_color_selected = QColor(selected)

    def paintCell(self, painter, rect, date):
        super().paintCell(painter, rect, date)
        date_str = date.toString("yyyy-MM-dd")
        if self.schedule_mgr and self.schedule_mgr.get_schedules_for_date(date_str):
            painter.save()
            painter.setPen(Qt.NoPen)
            marker = self.point_color_selected if date == self.selectedDate() else self.point_color
            painter.setBrush(QBrush(marker))
            # Keep marker fully inside each date cell so it aligns with grid boundaries.
            bar_height = 8
            top_margin = 2
            side_margin = 1
            painter.drawRect(
                rect.x() + side_margin,
                rect.y() + top_margin,
                max(0, rect.width() - (side_margin * 2)),
                bar_height,
            )
            painter.restore()


class SchedulePage(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(20)

        sch_cal_frm = QFrame()
        sch_cal_frm.setProperty("class", "CardFrame")
        cal_layout = QVBoxLayout(sch_cal_frm)
        self.cal = CalendarWidgetModified(self, self.main_window.schedule_mgr)
        self.cal.setGridVisible(False)
        self.cal.clicked.connect(self.update_schedule_list)
        cal_layout.addWidget(self.cal)
        layout.addWidget(sch_cal_frm, stretch=7)

        sch_detail_frm = QFrame()
        sch_detail_frm.setProperty("class", "CardFrame")
        detail_layout = QVBoxLayout(sch_detail_frm)
        self.date_lbl = QLabel("선택된 날짜 일정")
        self.date_lbl.setProperty("class", "TitleText")

        self.list_w = QListWidget()
        self.date_lbl.setStyleSheet("font-size: 28px; font-weight: 800;")
        self._apply_list_theme_style()
        self._apply_calendar_theme_style()

        add_btn = QPushButton("새 일정 추가")
        add_btn.setProperty("class", "PrimaryBtn")
        add_btn.setMinimumHeight(44)
        add_btn.clicked.connect(self.go_to_add_mode)

        self.edit_btn = QPushButton("선택 일정 수정")
        self.edit_btn.setMinimumHeight(42)
        self.edit_btn.clicked.connect(self.handle_edit)

        self.del_btn = QPushButton("선택 일정 삭제")
        self.del_btn.setMinimumHeight(42)
        self.del_btn.clicked.connect(self.handle_delete)

        detail_layout.addWidget(self.date_lbl)
        detail_layout.addWidget(self.list_w)
        detail_layout.addWidget(add_btn)
        detail_layout.addWidget(self.edit_btn)
        detail_layout.addWidget(self.del_btn)
        layout.addWidget(sch_detail_frm, stretch=3)

    def go_to_add_mode(self):
        add_page = self.main_window.schedule_add_page
        add_page.set_add_mode()
        self.main_window.switch_page(3, manual=True)

    def _apply_list_theme_style(self):
        theme = getattr(self.main_window, "_theme_mode", "light") if self.main_window is not None else "light"
        if theme == "dark":
            self.list_w.setStyleSheet(
                "QListWidget { background-color: #111827; color: #F3F4F6; border: 1px solid #374151;"
                " border-radius: 10px; font-size: 16px; outline: none; }"
                "QListWidget::item { padding: 11px; border: none; }"
                "QListWidget::item:selected { background-color: #243447; color: #FFFFFF; border: none; }"
            )
            return
        self.list_w.setStyleSheet(
            "QListWidget { background-color: #FFFFFF; color: #0F172A; border: 1px solid #CBD5E1;"
            " border-radius: 10px; font-size: 16px; outline: none; }"
            "QListWidget::item { padding: 11px; border: none; }"
            "QListWidget::item:selected { background-color: #E4EBF8; color: #1E3A8A; border: none; }"
        )

    def _apply_calendar_theme_style(self):
        theme = getattr(self.main_window, "_theme_mode", "light") if self.main_window is not None else "light"
        if theme == "dark":
            self.cal.setGridVisible(True)
            self.cal.set_marker_colors(QColor("#3B82F6"), QColor("#1D4ED8"))
            weekday_fmt = QTextCharFormat()
            weekday_fmt.setForeground(QBrush(QColor("#CBD5E1")))
            saturday_fmt = QTextCharFormat()
            saturday_fmt.setForeground(QBrush(QColor("#93C5FD")))
            sunday_fmt = QTextCharFormat()
            sunday_fmt.setForeground(QBrush(QColor("#FCA5A5")))
            self.cal.setWeekdayTextFormat(Qt.Monday, weekday_fmt)
            self.cal.setWeekdayTextFormat(Qt.Tuesday, weekday_fmt)
            self.cal.setWeekdayTextFormat(Qt.Wednesday, weekday_fmt)
            self.cal.setWeekdayTextFormat(Qt.Thursday, weekday_fmt)
            self.cal.setWeekdayTextFormat(Qt.Friday, weekday_fmt)
            self.cal.setWeekdayTextFormat(Qt.Saturday, saturday_fmt)
            self.cal.setWeekdayTextFormat(Qt.Sunday, sunday_fmt)
            self.cal.setStyleSheet(
                "QCalendarWidget { background-color: #0F172A; border: 1px solid #334155; border-radius: 12px; }"
                "QCalendarWidget QWidget { background-color: #0F172A; color: #F4F8FF; }"
                "QCalendarWidget QWidget#qt_calendar_navigationbar { background-color: #1E293B; border-bottom: 1px solid #334155; }"
                "QCalendarWidget QToolButton { background-color: #1E293B; color: #E2E8F0; border: none; font-size: 15px; font-weight: 800; height: 36px; padding: 0 8px; }"
                "QCalendarWidget QToolButton:hover { background-color: #334155; }"
                "QCalendarWidget QMenu { background-color: #1E293B; color: #E2E8F0; }"
                "QCalendarWidget QSpinBox { background-color: #1E293B; color: #E2E8F0; selection-background-color: #2563EB; selection-color: #FFFFFF; border: none; }"
                "QCalendarWidget QAbstractItemView:enabled { background-color: #111827; color: #EEF5FF; selection-background-color: #3B82F6; selection-color: #FFFFFF; font-size: 15px; outline: none; }"
                "QCalendarWidget QTableView { alternate-background-color: #0F172A; gridline-color: #334155; }"
                "QCalendarWidget QHeaderView::section { background-color: #0B1220; color: #A7C7FF; font-size: 13px; font-weight: 800; padding: 6px 0; border: none; border-bottom: 1px solid #334155; }"
            )
            return

        self.cal.setGridVisible(False)
        self.cal.set_marker_colors(QColor("#4064B7"), QColor("#1D4ED8"))
        weekday_fmt = QTextCharFormat()
        weekday_fmt.setForeground(QBrush(QColor("#334155")))
        saturday_fmt = QTextCharFormat()
        saturday_fmt.setForeground(QBrush(QColor("#1D4ED8")))
        sunday_fmt = QTextCharFormat()
        sunday_fmt.setForeground(QBrush(QColor("#DC2626")))
        self.cal.setWeekdayTextFormat(Qt.Monday, weekday_fmt)
        self.cal.setWeekdayTextFormat(Qt.Tuesday, weekday_fmt)
        self.cal.setWeekdayTextFormat(Qt.Wednesday, weekday_fmt)
        self.cal.setWeekdayTextFormat(Qt.Thursday, weekday_fmt)
        self.cal.setWeekdayTextFormat(Qt.Friday, weekday_fmt)
        self.cal.setWeekdayTextFormat(Qt.Saturday, saturday_fmt)
        self.cal.setWeekdayTextFormat(Qt.Sunday, sunday_fmt)
        self.cal.setStyleSheet(
            "QCalendarWidget QWidget { background-color: #F3F6FB; color: #1F2937; }"
            "QCalendarWidget QToolButton { background-color: #DCE6F8; color: #2A3C60; border: none; font-size: 15px; font-weight: 700; height: 34px; }"
            "QCalendarWidget QMenu { background-color: #FFFFFF; color: #1F2937; }"
            "QCalendarWidget QSpinBox { background-color: #FFFFFF; color: #1F2937; selection-background-color: #6D8ED8; selection-color: #FFFFFF; }"
            "QCalendarWidget QAbstractItemView:enabled { background-color: #FFFFFF; color: #1F2937; selection-background-color: #8FA9E0; selection-color: #FFFFFF; font-size: 15px; outline: none; }"
            "QCalendarWidget QTableView { alternate-background-color: #F8FAFD; gridline-color: transparent; }"
        )

    def update_schedule_list(self):
        self.list_w.clear()
        self.cal.update()
        selected_date = self.cal.selectedDate().toString("yyyy-MM-dd")
        self.date_lbl.setText(f"선택 날짜: {selected_date}")

        schedules = self.main_window.schedule_mgr.get_schedules_for_date(selected_date)
        if schedules:
            for item in schedules:
                place = f" ({item['place']})" if item.get("place") else ""
                self.list_w.addItem(f"{item['time']} - {item['todo']}{place}")
            self.edit_btn.setEnabled(True)
            self.del_btn.setEnabled(True)
            self.animate_list_fade(start=0.4, end=1.0)
        else:
            self.list_w.addItem("일정이 없습니다.")
            self.edit_btn.setEnabled(False)
            self.del_btn.setEnabled(False)

    def handle_edit(self):
        row = self.list_w.currentRow()
        selected_date = self.cal.selectedDate().toString("yyyy-MM-dd")
        schedules = self.main_window.schedule_mgr.get_schedules_for_date(selected_date)
        if row < 0 or row >= len(schedules):
            QMessageBox.information(self, "안내", "수정할 일정을 선택해주세요.")
            return

        self.main_window.schedule_add_page.set_edit_mode(selected_date, row, schedules[row])
        self.main_window.switch_page(3, manual=True)

    def handle_delete(self):
        row = self.list_w.currentRow()
        selected_date = self.cal.selectedDate().toString("yyyy-MM-dd")
        schedules = self.main_window.schedule_mgr.get_schedules_for_date(selected_date)
        if row < 0 or row >= len(schedules):
            QMessageBox.information(self, "안내", "삭제할 일정을 선택해주세요.")
            return

        reply = QMessageBox.question(
            self,
            "일정 삭제",
            "선택한 일정을 삭제할까요?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self.animate_list_fade(start=1.0, end=0.0, callback=lambda: self._delete_confirmed(selected_date, row))

    def _delete_confirmed(self, selected_date: str, row: int):
        self.main_window.schedule_mgr.delete_item(selected_date, row)
        self.cal.update()
        self.update_schedule_list()
        self.animate_list_fade(start=0.0, end=1.0)

    def animate_list_fade(self, start=0.0, end=1.0, duration=220, callback=None):
        effect = QGraphicsOpacityEffect(self.list_w)
        self.list_w.setGraphicsEffect(effect)

        self._list_fade_anim = QPropertyAnimation(effect, b"opacity")
        self._list_fade_anim.setDuration(duration)
        self._list_fade_anim.setStartValue(start)
        self._list_fade_anim.setEndValue(end)
        if callback is not None:
            self._list_fade_anim.finished.connect(callback)
        self._list_fade_anim.start()

    def update_calendar_markers(self):
        self.cal.update()

    def showEvent(self, event):
        super().showEvent(event)
        self._apply_list_theme_style()
        self._apply_calendar_theme_style()
        self.update_calendar_markers()
        self.update_schedule_list()


class ScheduleAddPage(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self.edit_index = -1
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)

        frm = QFrame()
        frm.setProperty("class", "CardFrame")
        frm.setFixedSize(500, 400)
        frm_layout = QVBoxLayout(frm)

        self.title_lbl = QLabel("새 일정 등록")
        self.title_lbl.setProperty("class", "TitleText")
        frm_layout.addWidget(self.title_lbl)

        form_layout = QFormLayout()
        self.date_input = QDateEdit(QDate.currentDate())
        self.date_input.setCalendarPopup(True)
        self.time_input = QTimeEdit(QTime.currentTime())
        self.todo_input = QLineEdit()
        self.place_input = QLineEdit()

        form_layout.addRow("날짜:", self.date_input)
        form_layout.addRow("시간:", self.time_input)
        form_layout.addRow("내용:", self.todo_input)
        form_layout.addRow("장소:", self.place_input)
        frm_layout.addLayout(form_layout)

        btn_layout = QHBoxLayout()
        cancel_btn = QPushButton("취소")
        cancel_btn.clicked.connect(self.handle_cancel)
        self.save_btn = QPushButton("저장")
        self.save_btn.setProperty("class", "PrimaryBtn")
        self.save_btn.clicked.connect(self.handle_save)
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(self.save_btn)

        frm_layout.addStretch()
        frm_layout.addLayout(btn_layout)
        layout.addWidget(frm)

    def set_add_mode(self):
        self.edit_index = -1
        self.title_lbl.setText("새 일정 등록")
        self.save_btn.setText("저장")
        self.date_input.setDate(QDate.currentDate())
        self.time_input.setTime(QTime.currentTime())
        self.todo_input.clear()
        self.place_input.clear()

    def set_edit_mode(self, date_str: str, index: int, data: dict):
        self.edit_index = index
        self.title_lbl.setText("일정 수정")
        self.save_btn.setText("수정")
        self.date_input.setDate(QDate.fromString(date_str, "yyyy-MM-dd"))
        self.time_input.setTime(QTime.fromString(data.get("time", "00:00"), "HH:mm"))
        self.todo_input.setText(data.get("todo", ""))
        self.place_input.setText(data.get("place", ""))

    def handle_save(self):
        date_str = self.date_input.date().toString("yyyy-MM-dd")
        time_str = self.time_input.time().toString("HH:mm")
        todo = self.todo_input.text().strip()
        place = self.place_input.text().strip()

        if not todo:
            QMessageBox.warning(self, "알림", "일정 내용을 입력해주세요.")
            return

        if self.edit_index < 0:
            self.main_window.schedule_mgr.add_item(date_str, time_str, todo, place)
        else:
            self.main_window.schedule_mgr.update_item(date_str, self.edit_index, time_str, todo, place)

        self.main_window.schedule_page.update_calendar_markers()
        self.main_window.schedule_page.update_schedule_list()
        self.main_window.switch_page(2, manual=True)

    def handle_cancel(self):
        self.main_window.switch_page(2, manual=True)


class TrackToggleButton(QPushButton):
    def __init__(self, theme: str = "light", parent=None):
        super().__init__(parent)
        self._theme = theme
        self.setCheckable(True)
        self.setText("")

    def set_theme(self, theme: str):
        self._theme = theme
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        rect = self.rect().adjusted(1, 1, -1, -1)
        is_on = self.isChecked()

        if self._theme == "dark":
            track_color = QColor("#6366F1") if is_on else QColor("#9CA3AF")
        else:
            track_color = QColor("#6366F1") if is_on else QColor("#D1D5DB")

        painter.setPen(Qt.NoPen)
        painter.setBrush(track_color)
        radius = rect.height() / 2
        painter.drawRoundedRect(rect, radius, radius)

        # Keep the knob large and vertically centered to avoid top/bottom clipping.
        knob_d = max(24, rect.height() - 8)
        y = rect.y() + (rect.height() - knob_d) / 2
        if is_on:
            x = rect.right() - knob_d - 3
        else:
            x = rect.x() + 3

        painter.setBrush(QColor("#FFFFFF"))
        painter.drawEllipse(int(x), int(y), int(knob_d), int(knob_d))


class AlarmCardWidget(QWidget):
    def __init__(self, time: str, target: str, place: str, days: list[str], memo: str, is_active: bool, theme: str = "light"):
        super().__init__()
        root = QHBoxLayout(self)
        root.setContentsMargins(16, 12, 16, 12)
        root.setSpacing(14)

        left = QVBoxLayout()
        left.setSpacing(9)

        top = QHBoxLayout()
        top.setSpacing(6)

        self.time_lbl = QLabel(time)
        self.time_lbl.setFixedHeight(50)
        self.time_lbl.setMinimumWidth(92)
        self.time_lbl.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        self.switch = TrackToggleButton(theme=theme)
        self.switch.setChecked(bool(is_active))
        self.switch.setFixedSize(92, 42)
        self.switch.toggled.connect(self._on_toggle_changed)

        self.target_lbl = QLabel(f"📍 {target}")
        self.target_lbl.setStyleSheet("font-size: 16px; font-weight: 800;")
        self.place_lbl = QLabel(f"🏁 {place}")
        self.place_lbl.setStyleSheet("font-size: 16px; font-weight: 800;")

        info_col = QVBoxLayout()
        info_col.setContentsMargins(0, 0, 0, 0)
        info_col.setSpacing(2)
        info_col.addWidget(self.target_lbl)
        info_col.addWidget(self.place_lbl)

        top.addWidget(self.time_lbl)
        top.addSpacing(2)
        top.addLayout(info_col)
        top.addStretch(1)

        days_row = QHBoxLayout()
        days_row.setSpacing(6)
        self.day_chip_labels = {}
        selected_days = set(days or [])
        for day in ["월", "화", "수", "목", "금", "토", "일"]:
            chip = QLabel(day)
            chip.setAlignment(Qt.AlignCenter)
            chip.setMinimumWidth(24)
            chip.setProperty("selected", day in selected_days)
            self.day_chip_labels[day] = chip
            days_row.addWidget(chip)
        days_row.addStretch(1)

        self.memo_lbl = QLabel(memo if memo else "메모 없음")
        self.memo_lbl.setWordWrap(True)
        self.memo_lbl.setStyleSheet("font-size: 20px; font-weight: 600; margin-top: -1px;")

        left.addLayout(top)
        left.addLayout(days_row)
        left.addWidget(self.memo_lbl)

        root.addLayout(left, 1)
        root.addWidget(self.switch, 0, Qt.AlignVCenter | Qt.AlignRight)
        self.setMinimumHeight(146)
        self.apply_theme_style(theme)

    def _on_toggle_changed(self, checked: bool):
        self.switch.update()

    def _refresh_toggle_style(self, theme: str):
        self.switch.set_theme(theme)

    def apply_theme_style(self, theme: str):
        self._theme = theme
        if theme == "dark":
            self.time_lbl.setStyleSheet("font-size: 46px; font-family: 'Noto Sans KR', 'Pretendard', sans-serif; font-weight: 700; color: #F9FAFB; background-color: transparent; border: none;")
            self.target_lbl.setStyleSheet("font-size: 16px; font-weight: 800; color: #E5E7EB; background-color: transparent; border: none; padding-top: 1px;")
            self.place_lbl.setStyleSheet("font-size: 16px; font-weight: 800; color: #D1D5DB; background-color: transparent; border: none; padding-top: 1px;")
            for day, chip in self.day_chip_labels.items():
                if chip.property("selected"):
                    chip.setStyleSheet("font-size: 16px; font-weight: 800; color: #A5B4FC; background-color: transparent; border: none;")
                else:
                    chip.setStyleSheet("font-size: 16px; font-weight: 700; color: #6B7280; background-color: transparent; border: none;")
            self.memo_lbl.setStyleSheet("font-size: 20px; color: #9CA3AF; background-color: transparent; border: none; margin-top: -1px;")
            self._refresh_toggle_style("dark")
            return
        self.time_lbl.setStyleSheet("font-size: 46px; font-family: 'Noto Sans KR', 'Pretendard', sans-serif; font-weight: 700; color: #111827; background-color: transparent; border: none;")
        self.target_lbl.setStyleSheet("font-size: 16px; font-weight: 800; color: #1F2937; background-color: transparent; border: none; padding-top: 1px;")
        self.place_lbl.setStyleSheet("font-size: 16px; font-weight: 800; color: #374151; background-color: transparent; border: none; padding-top: 1px;")
        for day, chip in self.day_chip_labels.items():
            if chip.property("selected"):
                chip.setStyleSheet("font-size: 16px; font-weight: 800; color: #4F46E5; background-color: transparent; border: none;")
            else:
                chip.setStyleSheet("font-size: 16px; font-weight: 700; color: #9CA3AF; background-color: transparent; border: none;")
        self.memo_lbl.setStyleSheet("font-size: 20px; color: #6B7280; background-color: transparent; border: none; margin-top: -1px;")
        self._refresh_toggle_style("light")


class AlarmPage(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 14, 20, 14)
        layout.setSpacing(8)

        title = QLabel("⏰ 나의 알람 목록")
        title.setStyleSheet("font-size: 22px; font-weight: bold; margin: 10px;")
        layout.addWidget(title)

        self.alarm_list = QListWidget()
        self.alarm_list.setSpacing(12)

        def clear_alarm_selection(event):
            item = self.alarm_list.itemAt(event.pos())
            if not item:
                self.alarm_list.clearSelection()
                self.alarm_list.setCurrentItem(None)
            QListWidget.mousePressEvent(self.alarm_list, event)

        self.alarm_list.mousePressEvent = clear_alarm_selection
        self.alarm_list.itemDoubleClicked.connect(self.handle_double_click)
        layout.addWidget(self.alarm_list)

        btn_layout = QHBoxLayout()
        self.add_btn = QPushButton("+ 새 알람 추가")
        self.add_btn.setMinimumHeight(50)
        self.add_btn.clicked.connect(lambda: self.go_to_add_page(False))

        self.del_btn = QPushButton("선택 삭제")
        self.del_btn.setMinimumHeight(50)
        self.del_btn.clicked.connect(self.handle_delete)

        btn_layout.addWidget(self.add_btn)
        btn_layout.addWidget(self.del_btn)
        layout.addLayout(btn_layout)
        self._apply_theme_style()

    def _apply_theme_style(self):
        theme = getattr(self.main_window, "_theme_mode", "light") if self.main_window is not None else "light"
        if theme == "dark":
            self.alarm_list.setStyleSheet(
                "QListWidget { background-color: #111827; border: none; outline: none; }"
                "QListWidget::item:selected { background-color: #1F2937; border-radius: 10px; color: #F9FAFB; border: none; }"
                "QListWidget::item:hover { background-color: #1A2437; border-radius: 10px; border: none; }"
            )
            self.add_btn.setStyleSheet("QPushButton { background-color: #4F46E5; color: #FFFFFF; font-weight: 800; border-radius: 10px; border: none; } QPushButton:hover { background-color: #4338CA; }")
            self.del_btn.setStyleSheet("QPushButton { background-color: #3F1D1D; color: #FCA5A5; border: 1px solid #7F1D1D; border-radius: 10px; font-weight: 800; } QPushButton:hover { background-color: #5A2121; }")
            return

        self.alarm_list.setStyleSheet(
            "QListWidget { background-color: #F9FAFB; border: none; outline: none; }"
            "QListWidget::item:selected { background-color: #E5E7EB; border-radius: 10px; color: #111827; border: none; }"
            "QListWidget::item:hover { background-color: #F3F4F6; border-radius: 10px; }"
        )
        self.add_btn.setStyleSheet("QPushButton { background-color: #6366F1; color: #FFFFFF; font-weight: 800; border-radius: 10px; border: none; } QPushButton:hover { background-color: #4F46E5; }")
        self.del_btn.setStyleSheet("QPushButton { background-color: #FEE2E2; color: #EF4444; border: 1px solid #FECACA; border-radius: 10px; font-weight: 800; } QPushButton:hover { background-color: #FECACA; }")

    def showEvent(self, event):
        super().showEvent(event)
        self._apply_theme_style()
        self.update_list()

    def handle_double_click(self, item):
        row = self.alarm_list.row(item)
        if row >= 0:
            self.main_window.alarm_mgr.load_data()
            if row < len(self.main_window.alarm_mgr.alarms):
                data = self.main_window.alarm_mgr.alarms[row]
                self.main_window.alarm_add_page.set_mode(True, row, data)
                self.main_window.switch_page(5, manual=True)

    def go_to_add_page(self, _is_edit=False):
        self.main_window.alarm_add_page.set_mode(False)
        self.main_window.switch_page(5, manual=True)

    def update_list(self):
        self.alarm_list.clear()
        self.main_window.alarm_mgr.load_data()

        for i, alarm in enumerate(self.main_window.alarm_mgr.alarms):
            item = QListWidgetItem(self.alarm_list)
            card = AlarmCardWidget(
                time=alarm.get("time", "00:00"),
                target=alarm.get("target", "미지정"),
                place=alarm.get("place", "미지정"),
                days=alarm.get("days", []),
                memo=alarm.get("memo", ""),
                is_active=alarm.get("active", True),
                theme=getattr(self.main_window, "_theme_mode", "light") if self.main_window is not None else "light",
            )
            card.switch.toggled.connect(lambda checked, idx=i: self.toggle_save(idx, checked))
            item.setSizeHint(card.sizeHint())
            self.alarm_list.addItem(item)
            self.alarm_list.setItemWidget(item, card)

    def toggle_save(self, index: int, is_active: bool):
        self.main_window.alarm_mgr.load_data()
        if 0 <= index < len(self.main_window.alarm_mgr.alarms):
            self.main_window.alarm_mgr.alarms[index]["active"] = bool(is_active)
            self.main_window.alarm_mgr.save_data()

    def handle_delete(self):
        row = self.alarm_list.currentRow()
        if row >= 0:
            self.main_window.alarm_mgr.delete_alarm(row)
            self.update_list()


class AlarmAddPage(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self._is_edit = False
        self._edit_index = -1
        self._edit_active = True

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)

        frm = QFrame()
        frm.setProperty("class", "CardFrame")
        frm.setMinimumSize(460, 360)
        frm.setMaximumWidth(780)
        frm.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.MinimumExpanding)
        frm_layout = QVBoxLayout(frm)

        self.title = QLabel("알람 설정")
        self.title.setProperty("class", "TitleText")
        frm_layout.addWidget(self.title)

        form_layout = QFormLayout()
        form_layout.setSpacing(12)
        self.time_edit = QTimeEdit(QTime.currentTime())
        self.time_edit.setStyleSheet("font-size: 20px;")
        self.target_edit = QLineEdit()
        self.place_edit = QLineEdit()
        self.memo_edit = QLineEdit()
        self.day_boxes: dict[str, QCheckBox] = {}

        days_widget = QWidget()
        days_layout = QGridLayout(days_widget)
        days_layout.setContentsMargins(0, 0, 0, 0)
        days_layout.setHorizontalSpacing(8)
        days_layout.setVerticalSpacing(6)
        day_names = ["월", "화", "수", "목", "금", "토", "일"]
        for i, day in enumerate(day_names):
            box = QCheckBox(day)
            self.day_boxes[day] = box
            row = 0 if i < 4 else 1
            col = i if i < 4 else i - 4
            days_layout.addWidget(box, row, col)

        form_layout.addRow("시간:", self.time_edit)
        form_layout.addRow("대상:", self.target_edit)
        form_layout.addRow("장소:", self.place_edit)
        form_layout.addRow("요일 선택:", days_widget)
        form_layout.addRow("메모:", self.memo_edit)
        frm_layout.addLayout(form_layout)

        btn_layout = QHBoxLayout()
        cancel_btn = QPushButton("취소")
        cancel_btn.clicked.connect(lambda: self.main_window.switch_page(4, manual=True))
        save_btn = QPushButton("저장")
        save_btn.setProperty("class", "PrimaryBtn")
        save_btn.clicked.connect(self.handle_save)
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(save_btn)

        frm_layout.addStretch()
        frm_layout.addLayout(btn_layout)
        layout.addWidget(frm)
        self._frame = frm
        self._apply_theme_style()

    def _apply_theme_style(self):
        theme = getattr(self.main_window, "_theme_mode", "light") if self.main_window is not None else "light"
        if theme == "dark":
            self._frame.setStyleSheet(
                "QFrame { background-color: #1F2937; border: none; border-radius: 16px; }"
                "QLabel { color: #F3F4F6; font-size: 15px; font-weight: 700; border: none; background: transparent; }"
                "QLineEdit, QTimeEdit { color: #F3F4F6; background-color: #111827; border: 1px solid #374151; border-radius: 8px; padding: 6px 8px; }"
                "QPushButton { background-color: #374151; color: #F3F4F6; border: none; border-radius: 8px; padding: 8px 12px; font-weight: 700; }"
                "QPushButton:hover { background-color: #4B5563; }"
                "QPushButton.PrimaryBtn { background-color: #2563EB; color: #FFFFFF; border: none; }"
                "QPushButton.PrimaryBtn:hover { background-color: #1D4ED8; }"
                "QCheckBox { color: #E5E7EB; border: none; background: transparent; }"
            )
            for box in self.day_boxes.values():
                box.setStyleSheet("QCheckBox { color: #E5E7EB; }")
            return
        self._frame.setStyleSheet(
            "QFrame { background-color: #FFFFFF; border: none; border-radius: 16px; }"
            "QLabel { color: #111827; font-size: 15px; font-weight: 700; border: none; background: transparent; }"
            "QLineEdit, QTimeEdit { color: #111827; background-color: #FFFFFF; border: 1px solid #D1D5DB; border-radius: 8px; padding: 6px 8px; }"
            "QPushButton { background-color: #E5E7EB; color: #111827; border: none; border-radius: 8px; padding: 8px 12px; font-weight: 700; }"
            "QPushButton:hover { background-color: #D1D5DB; }"
            "QPushButton.PrimaryBtn { background-color: #3B82F6; color: #FFFFFF; border: none; }"
            "QPushButton.PrimaryBtn:hover { background-color: #2563EB; }"
            "QCheckBox { color: #111827; border: none; background: transparent; }"
        )
        for box in self.day_boxes.values():
            box.setStyleSheet("QCheckBox { color: #111827; }")

    def _selected_days(self) -> list[str]:
        return [day for day, box in self.day_boxes.items() if box.isChecked()]

    def _set_selected_days(self, days: list[str]):
        selected = set(days)
        for day, box in self.day_boxes.items():
            box.setChecked(day in selected)

    def showEvent(self, event):
        super().showEvent(event)
        self._apply_theme_style()

    def set_mode(self, is_edit: bool, index: int = -1, data: dict | None = None):
        self._is_edit = is_edit
        self._edit_index = index
        if is_edit:
            self.title.setText("알람 수정")
            data = data or {}
            self._edit_active = bool(data.get("active", True))
            self.time_edit.setTime(QTime.fromString(data.get("time", "00:00"), "HH:mm"))
            self.target_edit.setText(data.get("target", ""))
            self.place_edit.setText(data.get("place", ""))
            self._set_selected_days(data.get("days", []))
            self.memo_edit.setText(data.get("memo", ""))
        else:
            self.title.setText("알람 설정")
            self._edit_active = True
            self.time_edit.setTime(QTime.currentTime())
            self.target_edit.clear()
            self.place_edit.clear()
            self._set_selected_days(["월", "화", "수", "목", "금"])
            self.memo_edit.clear()

    def handle_save(self):
        alarm = {
            "time": self.time_edit.time().toString("HH:mm"),
            "target": self.target_edit.text().strip() or "미지정",
            "place": self.place_edit.text().strip() or "미지정",
            "days": self._selected_days(),
            "memo": self.memo_edit.text().strip(),
            "active": self._edit_active if self._is_edit else True,
        }

        if self._is_edit and self._edit_index >= 0:
            self.main_window.alarm_mgr.update_alarm(self._edit_index, alarm)
        else:
            self.main_window.alarm_mgr.add_alarm(alarm)

        if hasattr(self.main_window, "stacked_widget"):
            page = self.main_window.stacked_widget.widget(4)
            if hasattr(page, "update_list"):
                page.update_list()
        self.main_window.switch_page(4, manual=True)
