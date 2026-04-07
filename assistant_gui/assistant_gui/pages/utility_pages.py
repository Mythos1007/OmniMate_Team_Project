from __future__ import annotations

import os

from PySide6.QtCore import Qt, QTimer, Signal, QTime, QSize
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QGroupBox,
    QCheckBox,
    QHBoxLayout,
    QPushButton,
    QFrame,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QDialog,
    QFormLayout,
    QLineEdit,
    QTimeEdit,
)

try:
    from assistant_gui.engines.ocr_engine import OcrEngine
    from assistant_gui.engines.gesture_engine import GestureEngine
    from assistant_gui.engines.medication_manager import MedicationManager
except ModuleNotFoundError:
    from engines.ocr_engine import OcrEngine
    from engines.gesture_engine import GestureEngine
    from engines.medication_manager import MedicationManager


class MedicationCardWidget(QWidget):
    status_changed = Signal(bool)

    def __init__(self, time_str: str, name: str, pill: str, is_done: bool, theme: str = "light"):
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(18, 12, 18, 12)
        layout.setSpacing(10)

        info_layout = QVBoxLayout()
        info_layout.setContentsMargins(0, 0, 0, 0)
        info_layout.setSpacing(6)

        self.time_lbl = QLabel(time_str)
        self.time_lbl.setStyleSheet("font-size: 46px; font-family: 'Noto Sans KR', 'Pretendard', sans-serif; font-weight: 700;")

        self.info_lbl = QLabel(f"👤 {name} | 💊 {pill}")
        self.info_lbl.setStyleSheet("font-size: 16px; font-weight: 800;")
        self.info_lbl.setWordWrap(False)

        info_layout.addWidget(self.time_lbl)
        info_layout.addWidget(self.info_lbl)

        self.switch = QPushButton("복용 완료" if is_done else "미복용")
        self.switch.setCheckable(True)
        self.switch.setChecked(bool(is_done))
        self.switch.setMinimumWidth(104)
        self.switch.setFixedHeight(38)
        self.switch.toggled.connect(self._on_toggle_changed)
        self.switch.toggled.connect(self.status_changed.emit)

        layout.addLayout(info_layout, 1)
        layout.addWidget(self.switch, 0, Qt.AlignVCenter | Qt.AlignRight)
        self.setMinimumHeight(108)
        self.apply_theme_style(theme)

    def _on_toggle_changed(self, checked: bool):
        self.switch.setText("복용 완료" if checked else "미복용")
        self._refresh_toggle_style(getattr(self, "_theme", "light"))

    def _refresh_toggle_style(self, theme: str):
        done = self.switch.isChecked()
        if theme == "dark":
            if done:
                self.switch.setStyleSheet("QPushButton { background-color: #10B981; color: #FFFFFF; border: none; border-radius: 12px; font-weight: 800; padding: 6px 10px; }")
            else:
                self.switch.setStyleSheet("QPushButton { background-color: #374151; color: #D1D5DB; border: 1px solid #4B5563; border-radius: 12px; font-weight: 800; padding: 6px 10px; }")
            return
        if done:
            self.switch.setStyleSheet("QPushButton { background-color: #10B981; color: #FFFFFF; border: none; border-radius: 12px; font-weight: 800; padding: 6px 10px; }")
        else:
            self.switch.setStyleSheet("QPushButton { background-color: #E5E7EB; color: #374151; border: 1px solid #D1D5DB; border-radius: 12px; font-weight: 800; padding: 6px 10px; }")

    def apply_theme_style(self, theme: str):
        self._theme = theme
        if theme == "dark":
            self.time_lbl.setStyleSheet("font-size: 46px; font-family: 'Noto Sans KR', 'Pretendard', sans-serif; font-weight: 700; color: #F9FAFB; background-color: transparent; border: none;")
            self.info_lbl.setStyleSheet("font-size: 16px; font-weight: 800; color: #E5E7EB; background-color: transparent; border: none;")
            self._refresh_toggle_style("dark")
            return
        self.time_lbl.setStyleSheet("font-size: 46px; font-family: 'Noto Sans KR', 'Pretendard', sans-serif; font-weight: 700; color: #1E40AF; background-color: transparent; border: none;")
        self.info_lbl.setStyleSheet("font-size: 16px; font-weight: 800; color: #1F2937; background-color: transparent; border: none;")
        self._refresh_toggle_style("light")


class MedEditDialog(QDialog):
    def __init__(self, parent=None, data: dict | None = None):
        super().__init__(parent)
        self.setWindowTitle("복약 일정")
        layout = QVBoxLayout(self)

        form = QFormLayout()
        self.time_edit = QTimeEdit(QTime.currentTime())
        self.name_edit = QLineEdit()
        self.pill_edit = QLineEdit()

        if data:
            self.time_edit.setTime(QTime.fromString(data.get("time", "00:00"), "HH:mm"))
            self.name_edit.setText(data.get("name", ""))
            self.pill_edit.setText(data.get("pill", ""))

        form.addRow("시간:", self.time_edit)
        form.addRow("이름:", self.name_edit)
        form.addRow("약:", self.pill_edit)
        layout.addLayout(form)

        btns = QHBoxLayout()
        cancel_btn = QPushButton("취소")
        ok_btn = QPushButton("저장")
        ok_btn.setProperty("class", "PrimaryBtn")
        cancel_btn.clicked.connect(self.reject)
        ok_btn.clicked.connect(self.accept)
        btns.addWidget(cancel_btn)
        btns.addWidget(ok_btn)
        layout.addLayout(btns)
        self._apply_theme_style()

    def _apply_theme_style(self):
        parent = self.parent()
        theme = getattr(parent.main_window, "_theme_mode", "light") if parent is not None and hasattr(parent, "main_window") else "light"
        if theme == "dark":
            self.setStyleSheet(
                "QDialog { background-color: #111827; }"
                "QLabel { color: #F9FAFB; }"
                "QLineEdit, QTimeEdit { background-color: #1F2937; color: #F9FAFB; border: 1px solid #374151; border-radius: 8px; padding: 6px; }"
                "QPushButton { background-color: #374151; color: #F9FAFB; border: 1px solid #4B5563; border-radius: 8px; padding: 6px 12px; }"
                "QPushButton:hover { background-color: #4B5563; }"
                "QPushButton.PrimaryBtn { background-color: #2563EB; color: #FFFFFF; border: none; }"
                "QPushButton.PrimaryBtn:hover { background-color: #1D4ED8; }"
            )
            return
        self.setStyleSheet(
            "QDialog { background-color: #FFFFFF; }"
            "QLabel { color: #111827; }"
            "QLineEdit, QTimeEdit { background-color: #FFFFFF; color: #111827; border: 1px solid #D1D5DB; border-radius: 8px; padding: 6px; }"
            "QPushButton { background-color: #E5E7EB; color: #111827; border: 1px solid #D1D5DB; border-radius: 8px; padding: 6px 12px; }"
            "QPushButton:hover { background-color: #D1D5DB; }"
            "QPushButton.PrimaryBtn { background-color: #3B82F6; color: #FFFFFF; border: none; }"
            "QPushButton.PrimaryBtn:hover { background-color: #2563EB; }"
        )

    def get_data(self) -> dict:
        return {
            "time": self.time_edit.time().toString("HH:mm"),
            "name": self.name_edit.text().strip() or "사용자",
            "pill": self.pill_edit.text().strip() or "약",
        }


class MedicationPage(QWidget):
    def __init__(self, main_window=None):
        super().__init__()
        self.main_window = main_window
        med_path = os.path.join(os.path.dirname(__file__), "..", "medications.json")
        self.med_mgr = MedicationManager(filename=os.path.abspath(med_path))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 25, 40, 25)
        layout.setSpacing(15)

        self.status_bar = QLabel()
        self.status_bar.setAlignment(Qt.AlignCenter)
        self.status_bar.setMinimumHeight(65)
        layout.addWidget(self.status_bar)

        self.med_list = QListWidget()
        self.med_list.setSpacing(10)

        def clear_med_selection(event):
            item = self.med_list.itemAt(event.pos())
            if not item:
                self.med_list.clearSelection()
                self.med_list.setCurrentItem(None)
            QListWidget.mousePressEvent(self.med_list, event)

        self.med_list.mousePressEvent = clear_med_selection
        self.med_list.itemDoubleClicked.connect(self.handle_edit)
        layout.addWidget(self.med_list)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)

        self.add_btn = QPushButton("+ 신규 복약 등록")
        self.add_btn.setMinimumHeight(55)
        self.add_btn.clicked.connect(self.handle_add)

        self.del_btn = QPushButton("일정 삭제")
        self.del_btn.setMinimumHeight(55)
        self.del_btn.clicked.connect(self.handle_delete)

        btn_layout.addWidget(self.add_btn)
        btn_layout.addWidget(self.del_btn)
        layout.addLayout(btn_layout)

        self.status_timer = QTimer(self)
        self.status_timer.timeout.connect(self.update_status_logic)
        self.status_timer.start(2000)

        self._apply_theme_style()
        self.update_list()

    def _apply_theme_style(self):
        theme = getattr(self.main_window, "_theme_mode", "light") if self.main_window is not None else "light"
        if theme == "dark":
            self.med_list.setStyleSheet(
                "QListWidget { background-color: transparent; border: none; outline: none; }"
                "QListWidget::item { background-color: #1F2937; border-radius: 15px; margin-bottom: 4px; padding: 5px; }"
                "QListWidget::item:hover { background-color: #243447; }"
                "QListWidget::item:selected { background-color: #2B3F59; border: 1px solid #4B6FAE; color: #F9FAFB; }"
            )
            self.add_btn.setStyleSheet(
                "QPushButton { background-color: #4F46E5; color: #FFFFFF; font-weight: 800; border-radius: 12px; font-size: 15px; border: none; }"
                "QPushButton:hover { background-color: #4338CA; }"
            )
            self.del_btn.setStyleSheet(
                "QPushButton { background-color: #3F1D1D; color: #FCA5A5; border: 1px solid #7F1D1D; font-weight: 800; border-radius: 12px; font-size: 15px; }"
                "QPushButton:hover { background-color: #5A2121; }"
            )
            return

        self.med_list.setStyleSheet(
            "QListWidget { background-color: transparent; border: none; outline: none; }"
            "QListWidget::item { background-color: #F3F4F6; border-radius: 15px; margin-bottom: 5px; padding: 5px; }"
            "QListWidget::item:hover { background-color: #E5E7EB; }"
            "QListWidget::item:selected { background-color: #D1D5DB; border: 1px solid #9CA3AF; color: #111827; }"
        )
        self.add_btn.setStyleSheet(
            "QPushButton { background-color: #6366F1; color: white; font-weight: 800; border-radius: 12px; font-size: 15px; border: none; }"
            "QPushButton:hover { background-color: #4F46E5; }"
        )
        self.del_btn.setStyleSheet(
            "QPushButton { background-color: white; color: #EF4444; border: 1px solid #FECACA; font-weight: 800; border-radius: 12px; font-size: 15px; }"
            "QPushButton:hover { background-color: #FEF2F2; }"
        )

    def update_status_logic(self):
        current_time = QTime.currentTime().toString("HH:mm")
        all_done = True
        current_alarm = None

        if not self.med_mgr.meds:
            self.set_status_ui("pending", "등록된 복약 일정이 없습니다.")
            return

        for med in self.med_mgr.meds:
            is_done = bool(med.get("active"))
            if not is_done:
                all_done = False
                if med.get("time") == current_time:
                    current_alarm = med

        if current_alarm:
            msg = f"🚨 [알람] {current_alarm.get('name', '사용자')}님, {current_alarm.get('pill', '약')} 복용 시간입니다!"
            self.set_status_ui("alarm", msg)
        elif all_done:
            self.set_status_ui("done", "✅ 오늘의 모든 복약 일정을 완료했습니다!")
        else:
            self.set_status_ui("pending", "⏳ 복약 미완료 (일정이 남아있습니다)")

    def set_status_ui(self, state, text):
        self.status_bar.setText(text)
        theme = getattr(self.main_window, "_theme_mode", "light") if self.main_window is not None else "light"
        if state == "alarm":
            style = "background-color: #7F1D1D; color: #FECACA; border: 2px solid #B91C1C;" if theme == "dark" else "background-color: #FEE2E2; color: #B91C1C; border: 2px solid #FCA5A5;"
        elif state == "done":
            style = "background-color: #064E3B; color: #D1FAE5; border: 2px solid #10B981;" if theme == "dark" else "background-color: #DCFCE7; color: #166534; border: 2px solid #86EFAC;"
        else:
            style = "background-color: #1F2937; color: #D1D5DB; border: 1px solid #374151;" if theme == "dark" else "background-color: #F3F4F6; color: #4B5563; border: 1px solid #D1D5DB;"
        self.status_bar.setStyleSheet(f"padding: 15px; border-radius: 15px; font-weight: 800; font-size: 17px; {style}")

    def showEvent(self, event):
        super().showEvent(event)
        self._apply_theme_style()
        self.update_list()

    def update_list(self):
        self.med_list.clear()
        self.med_mgr.load_data()
        for i, med in enumerate(self.med_mgr.meds):
            item = QListWidgetItem(self.med_list)
            card = MedicationCardWidget(
                med.get("time", "00:00"),
                med.get("name", "사용자"),
                med.get("pill", "약"),
                bool(med.get("active", False)),
                theme=getattr(self.main_window, "_theme_mode", "light") if self.main_window is not None else "light",
            )
            card.status_changed.connect(lambda checked, idx=i: self.toggle_save(idx, checked))
            item.setSizeHint(card.sizeHint().expandedTo(QSize(0, 118)))
            self.med_list.addItem(item)
            self.med_list.setItemWidget(item, card)
        self.update_status_logic()

    def toggle_save(self, index, is_done):
        if 0 <= index < len(self.med_mgr.meds):
            self.med_mgr.meds[index]["active"] = bool(is_done)
            self.med_mgr.save_data()
            self.update_status_logic()

    def handle_add(self):
        dialog = MedEditDialog(self)
        if dialog.exec():
            data = dialog.get_data()
            self.med_mgr.add_med(data["time"], data["name"], data["pill"])
            self.update_list()

    def handle_edit(self, item):
        index = self.med_list.row(item)
        old_data = self.med_mgr.meds[index]
        dialog = MedEditDialog(self, old_data)
        if dialog.exec():
            new_data = dialog.get_data()
            self.med_mgr.update_med(index, new_data["time"], new_data["name"], new_data["pill"])
            self.update_list()

    def handle_delete(self):
        row = self.med_list.currentRow()
        if row >= 0:
            reply = QMessageBox.question(
                self,
                "삭제 확인",
                "이 일정을 삭제하시겠습니까?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if reply == QMessageBox.Yes:
                self.med_mgr.delete_med(row)
                self.update_list()
        else:
            QMessageBox.warning(self, "알림", "삭제할 항목을 선택해주세요.")


class MailPage(QWidget):
    def __init__(self, main_window=None):
        super().__init__()
        self.main_window = main_window
        self.engine = None
        self._last_frame_pixmap: QPixmap | None = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 20, 40, 20)

        self.cam_label = QLabel("카메라 준비 중...")
        self.cam_label.setAlignment(Qt.AlignCenter)
        self.cam_label.setStyleSheet("background-color: #1F2937; border-radius: 16px; border: 4px solid #3B82F6; color: white;")
        self.cam_label.setMinimumSize(320, 240)

        self.ocr_result_lbl = QLabel("수취인을 스캔해 주세요.")
        self.ocr_result_lbl.setStyleSheet("color: #10B981; font-size: 20px; font-weight: bold; background-color: #F3F4F6; padding: 10px; border-radius: 8px;")
        self.ocr_result_lbl.setAlignment(Qt.AlignCenter)

        layout.addWidget(self.cam_label, alignment=Qt.AlignCenter)
        layout.addWidget(self.ocr_result_lbl)

        btn_lay = QHBoxLayout()
        self.yes_btn = QPushButton("확인")
        self.yes_btn.setProperty("class", "PrimaryBtn")
        self.no_btn = QPushButton("취소")
        self.no_btn.clicked.connect(self.cancel_target)
        self.yes_btn.clicked.connect(self.confirm_target)
        btn_lay.addWidget(self.no_btn)
        btn_lay.addWidget(self.yes_btn)
        layout.addLayout(btn_lay)
        self._resize_camera_view()

    def _resize_camera_view(self):
        # Keep a 4:3 preview area that grows/shrinks with the page size.
        rect = self.contentsRect()
        avail_w = max(320, rect.width() - 40)
        avail_h = max(240, rect.height() - 220)

        target_w = min(avail_w, int(avail_h * 4 / 3))
        target_h = int(target_w * 3 / 4)

        if target_h > avail_h:
            target_h = avail_h
            target_w = int(target_h * 4 / 3)

        self.cam_label.setFixedSize(target_w, target_h)

    def _apply_scaled_frame(self):
        if self._last_frame_pixmap is None:
            return
        scaled = self._last_frame_pixmap.scaled(
            self.cam_label.size(),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation,
        )
        self.cam_label.setPixmap(scaled)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._resize_camera_view()
        self._apply_scaled_frame()

    def showEvent(self, event):
        super().showEvent(event)
        self._resize_camera_view()
        self.reset_ui()
        if self.engine is not None:
            self.engine.stop()
            self.engine = None
        try:
            self.engine = OcrEngine(self.update_frame)
            self.engine.start()
        except Exception as exc:
            self.ocr_result_lbl.setText(f"카메라 시작 실패: {exc}")

    def hideEvent(self, event):
        if self.engine is not None:
            self.engine.stop()
            self.engine = None
        super().hideEvent(event)

    def reset_ui(self):
        self.ocr_result_lbl.setText("우편 인식 기능 준비 중...")
        self.yes_btn.setEnabled(True)
        self.no_btn.setEnabled(True)
        self._last_frame_pixmap = None
        self.cam_label.clear()
        self.cam_label.setText("카메라와 OCR 모델을 준비 중...")

    def update_frame(self, cv_img, mode, target):
        if cv_img is not None:
            h, w, ch = cv_img.shape
            q_img = QImage(cv_img.data, w, h, ch * w, QImage.Format_BGR888)
            self._last_frame_pixmap = QPixmap.fromImage(q_img)
            self._apply_scaled_frame()

        if mode == "INITIALIZING":
            self.ocr_result_lbl.setText(target)
            return
        if mode == "ERROR":
            self.ocr_result_lbl.setText(f"카메라 시작 실패: {target}")
            return
        if mode == "SCANNING":
            self.ocr_result_lbl.setText("부서를 스캔하는 중...")
        elif mode == "CONFIRMING":
            self.ocr_result_lbl.setText(f"인식됨: [{target}]님에게 배송할까요?")

    def confirm_target(self):
        if self.engine and self.engine.current_mode == "CONFIRMING":
            target = self.engine.temp_target
            self.ocr_result_lbl.setText(f"{target}(으)로 배송을 시작합니다.")
            self.yes_btn.setEnabled(False)
            self.no_btn.setEnabled(False)
            if self.main_window is not None:
                if hasattr(self.main_window, "home_page"):
                    self.main_window.home_page.st_main.setText(f"{target} 배송 중")
                    self.main_window.home_page.st_sub.setText(f"현재 {target}(으)로 이동하고 있습니다.")
                if self.engine is not None:
                    self.engine.stop()
                    self.engine = None
                QTimer.singleShot(1500, lambda: self.main_window.switch_page(1))
                QTimer.singleShot(5000, lambda: self.arrive_at_destination(target))

    def cancel_target(self):
        if self.engine is not None:
            self.engine.stop()
            self.engine = None
        self.ocr_result_lbl.setText("우편 전달을 취소하고 홈으로 돌아갑니다.")
        if self.main_window is not None:
            self.main_window.switch_page(1, manual=True)

    def arrive_at_destination(self, target: str):
        if self.main_window is not None and hasattr(self.main_window, "home_page"):
            self.main_window.home_page.st_main.setText(f"{target} 배송 완료")
            self.main_window.home_page.st_sub.setText(f"{target}에 우편 배달을 완료했습니다.")
            if hasattr(self.main_window, "gesture_page"):
                self.main_window.gesture_page.set_target(target)
                self.main_window.switch_page(12)


class GesturePage(QWidget):
    request_return_signal = Signal()

    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self.engine = None
        self.is_returning = False
        self.target = ""
        self._last_frame_pixmap: QPixmap | None = None
        self._last_main_size = None
        self._camera_size_initialized = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 30, 40, 30)
        layout.setSpacing(18)
        layout.setAlignment(Qt.AlignCenter)

        card = QFrame()
        card.setProperty("class", "CardFrame")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(36, 36, 36, 36)
        card_layout.setSpacing(16)

        icon_lbl = QLabel("🙌")
        icon_lbl.setAlignment(Qt.AlignCenter)
        icon_lbl.setStyleSheet("font-size: 72px;")

        self.title_lbl = QLabel("도착 완료! OK 사인을 보여주세요")
        self.title_lbl.setAlignment(Qt.AlignCenter)
        self.title_lbl.setProperty("class", "TitleText")

        self.target_lbl = QLabel("수취 확인을 기다리는 중입니다.")
        self.target_lbl.setAlignment(Qt.AlignCenter)
        self.target_lbl.setStyleSheet("font-size: 24px; font-weight: bold;")

        self.cam_label = QLabel("카메라 준비 중...")
        self.cam_label.setAlignment(Qt.AlignCenter)
        self.cam_label.setMinimumSize(320, 240)
        self.cam_label.setStyleSheet("background-color: #1F2937; border-radius: 16px; border: 4px solid #10B981; color: white;")

        detail_lbl = QLabel("손으로 OK 사인을 보여주면 복귀를 시작합니다.")
        detail_lbl.setAlignment(Qt.AlignCenter)
        detail_lbl.setProperty("class", "SubText")

        self.manual_ok_btn = QPushButton("수동 확인 (OK)")
        self.manual_ok_btn.setProperty("class", "PrimaryBtn")
        self.manual_ok_btn.setFixedHeight(44)
        self.manual_ok_btn.clicked.connect(self.start_return_process)
        self.manual_ok_btn.hide()

        card_layout.addWidget(icon_lbl)
        card_layout.addWidget(self.title_lbl)
        card_layout.addWidget(self.target_lbl)
        card_layout.addWidget(self.cam_label, alignment=Qt.AlignCenter)
        card_layout.addWidget(detail_lbl)
        card_layout.addWidget(self.manual_ok_btn)

        layout.addWidget(card, alignment=Qt.AlignCenter)
        self.request_return_signal.connect(self.start_return_process)

    def _resize_camera_view(self, *, force: bool = False):
        main_size = self.main_window.size() if self.main_window is not None else None
        if main_size is None:
            return
        if not force and main_size is not None and self._last_main_size == main_size:
            return

        self._last_main_size = main_size

        # Use main-window dimensions directly to avoid step-by-step growth during page layout.
        base_w = max(800, main_size.width())
        base_h = max(480, main_size.height())
        avail_w = max(420, min(base_w - 300, int(base_w * 0.62)))
        avail_h = max(315, min(base_h - 280, int(base_h * 0.50)))

        target_w = min(avail_w, int(avail_h * 4 / 3))
        target_h = int(target_w * 3 / 4)

        if target_h > avail_h:
            target_h = avail_h
            target_w = int(target_h * 4 / 3)

        self.cam_label.setFixedSize(target_w, target_h)
        self._camera_size_initialized = True

    def _apply_scaled_frame(self):
        if self._last_frame_pixmap is None:
            return
        scaled = self._last_frame_pixmap.scaled(
            self.cam_label.size(),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation,
        )
        self.cam_label.setPixmap(scaled)

    def _show_camera_after_layout(self):
        if not self.isVisible() or self.is_returning:
            return
        self._resize_camera_view(force=True)
        self.cam_label.show()
        self._apply_scaled_frame()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._resize_camera_view()
        self._apply_scaled_frame()

    def set_target(self, target: str):
        self.target = target
        self.target_lbl.setText(f"{target} 배송이 완료되었습니다. OK 사인을 기다리는 중입니다.")

    def showEvent(self, event):
        super().showEvent(event)
        # Resize only when needed; avoids visible "grow" effect while entering this page.
        self._resize_camera_view(force=not self._camera_size_initialized)
        self.is_returning = False
        self.title_lbl.setText("도착 완료! OK 사인을 보여주세요")
        self.cam_label.hide()
        self.manual_ok_btn.hide()
        self._last_frame_pixmap = None
        QTimer.singleShot(16, self._show_camera_after_layout)
        if self.engine is not None:
            self.engine.stop()
            self.engine = None
        try:
            self.engine = GestureEngine(self.update_ui)
            self.cam_label.setText(f"카메라 연결됨: {self.engine.source_name}")
            if not self.engine.has_gesture_support:
                self.manual_ok_btn.show()
            self.engine.start()
        except Exception as exc:
            self.cam_label.setText("카메라 연결 실패")
            self.target_lbl.setText(f"카메라 시작 실패: {exc}")
            self.manual_ok_btn.show()

    def hideEvent(self, event):
        if self.engine is not None:
            self.engine.stop()
            self.engine = None
        super().hideEvent(event)

    def update_ui(self, cv_img, gesture_text):
        if self.is_returning or cv_img is None:
            return

        h, w, ch = cv_img.shape
        q_img = QImage(cv_img.data, w, h, ch * w, QImage.Format_BGR888)
        self._last_frame_pixmap = QPixmap.fromImage(q_img)
        self._apply_scaled_frame()
        self.target_lbl.setText(f"{self.target} 배송 완료\n인식 결과: {gesture_text}")

        if "OK" in gesture_text:
            if self.engine is not None:
                self.engine.stop()
                self.engine = None
            self.request_return_signal.emit()

    def start_return_process(self):
        self.is_returning = True
        self.cam_label.hide()
        self.title_lbl.setText("복귀 프로세스 시작")
        self.target_lbl.setText("로봇이 대기 위치로 복귀하고 있습니다.\n잠시만 기다려 주세요.")
        QTimer.singleShot(5000, self.go_to_main_and_finish)

    def go_to_main_and_finish(self):
        if self.main_window is not None and hasattr(self.main_window, "home_page"):
            self.main_window.switch_page(1)
            self.main_window.home_page.st_main.setText("복귀 완료")
            self.main_window.home_page.st_sub.setText("대기 위치로 복귀했습니다.")
            QTimer.singleShot(3000, self._set_idle_status)

    def _set_idle_status(self):
        if self.main_window is not None and hasattr(self.main_window, "home_page"):
            self.main_window.home_page.st_main.setText("대기 중...")
            self.main_window.home_page.st_sub.setText("명령을 기다리고 있습니다.")
