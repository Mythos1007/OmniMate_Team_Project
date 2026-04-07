GLOBAL_STYLE = """
    QMainWindow { background-color: #F5F7FA; }
    QLabel, QCheckBox, QListWidget, QLineEdit, QTimeEdit, QDateEdit { color: #111827; }
    QGroupBox { color: #111827; background-color: #FFFFFF; border: 1px solid #E5E7EB; border-radius: 8px; padding: 12px; margin-top: 12px; }
    QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 3px; }
    QComboBox { color: #111827; background-color: #FFFFFF; border: 1px solid #D1D5DB; border-radius: 4px; padding: 4px 8px; }
    QComboBox QAbstractItemView { color: #111827; background-color: #FFFFFF; selection-background-color: #3B82F6; selection-color: #FFFFFF; border: 1px solid #D1D5DB; }
    QSpinBox { color: #111827; background-color: #FFFFFF; border: 1px solid #D1D5DB; border-radius: 4px; padding: 2px 4px; }
    QListWidget::item:selected { background-color: #DBEAFE; color: #1E3A8A; }
    QMessageBox { background-color: #F8FAFC; }
    QMessageBox QLabel { color: #0F172A; font-size: 14px; }
    QMessageBox QPushButton {
        background-color: #E5E7EB;
        color: #111827;
        border: 1px solid #D1D5DB;
        border-radius: 8px;
        padding: 6px 12px;
        min-width: 70px;
        font-size: 13px;
        font-weight: 700;
    }
    QMessageBox QPushButton:hover { background-color: #D1D5DB; }
    QDialog { background-color: #F8FAFC; }
    QDialog QLabel { color: #111827; }
    QDialog QLineEdit, QDialog QTimeEdit, QDialog QDateEdit, QDialog QComboBox, QDialog QTextEdit {
        color: #111827;
        background-color: #FFFFFF;
        border: 1px solid #D1D5DB;
        border-radius: 8px;
        padding: 6px 8px;
    }
    QDialog QPushButton {
        background-color: #E5E7EB;
        color: #111827;
        border: 1px solid #D1D5DB;
        border-radius: 8px;
        padding: 6px 12px;
        font-size: 13px;
        font-weight: 700;
    }
    QDialog QPushButton:hover { background-color: #D1D5DB; }
    QCheckBox::indicator {
        width: 18px;
        height: 18px;
        background-color: #FFFFFF;
        border: 1px solid #9CA3AF;
        border-radius: 4px;
    }
    QCheckBox::indicator:checked {
        background-color: #2563EB;
        border: 1px solid #1D4ED8;
    }
    QCheckBox::indicator:unchecked {
        background-color: #FFFFFF;
    }
    QCheckBox::indicator:disabled {
        background-color: #E5E7EB;
        border: 1px solid #D1D5DB;
    }
    QCalendarWidget QWidget { alternate-background-color: #EEF2F7; }
    QCalendarWidget QToolButton {
        color: #111827;
        background-color: #EEF2F7;
        border: 1px solid #D7DEE7;
        border-radius: 6px;
        padding: 4px 8px;
    }
    QCalendarWidget QMenu {
        color: #111827;
        background-color: #F3F5F8;
    }
    QCalendarWidget QSpinBox {
        color: #111827;
        background-color: #EEF2F7;
        border: 1px solid #D7DEE7;
        selection-background-color: #2563EB;
        selection-color: #FFFFFF;
    }
    QCalendarWidget QAbstractItemView {
        color: #111827;
        background-color: #F3F5F8;
        selection-background-color: #2563EB;
        selection-color: #FFFFFF;
        alternate-background-color: #E9EEF5;
    }
    #hdr_frame { background-color: #FFFFFF; border-bottom: 1px solid #E4E7EB; }
    #hdr_voiceState_Lbl { font-size: 16px; font-weight: bold; color: #10B981; }
    .CardFrame {
        background-color: #FFFFFF;
        border-radius: 16px;
        border: 1px solid #E4E7EB;
    }
    .TitleText { font-size: 20px; font-weight: bold; color: #111827; }
    .SubText { font-size: 14px; color: #6B7280; }
    .StatusText { font-size: 24px; font-weight: bold; color: #3B82F6; }
    #face_label { font-size: 80px; font-weight: bold; color: #3B82F6; }
    #face_hint { font-size: 16px; color: #9CA3AF; }
    QPushButton {
        background-color: #FFFFFF;
        border: 1px solid #D1D5DB;
        border-radius: 8px;
        padding: 10px;
        font-size: 14px;
        color: #374151;
        font-weight: bold;
    }
    QPushButton:hover { background-color: #F3F4F6; }
    QPushButton.PrimaryBtn { background-color: #3B82F6; color: white; border: none; }
    QPushButton.PrimaryBtn:hover { background-color: #2563EB; }
    QPushButton.StopBtn { background-color: #EF4444; color: white; border: none; }
    QPushButton.ActionBtn { font-size: 16px; padding: 15px; }

    #weather_card_btn { background-color: #FFFFFF; border: 2px solid #3B82F6; border-radius: 16px; }
    #weather_card_btn:hover { background-color: #F0F7FF; }
"""

DARK_STYLE = """
    QMainWindow { background-color: #111827; }
    QWidget { color: #F3F4F6; }
    QLabel, QCheckBox, QListWidget, QLineEdit, QTimeEdit, QDateEdit { color: #F3F4F6; }
    QGroupBox { color: #F3F4F6; background-color: #1F2937; border: 1px solid #374151; border-radius: 8px; padding: 12px; margin-top: 12px; }
    QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 3px; }
    QComboBox { color: #F3F4F6; background-color: #1F2937; border: 1px solid #374151; border-radius: 4px; padding: 4px 8px; }
    QComboBox QAbstractItemView { color: #F3F4F6; background-color: #1F2937; selection-background-color: #3B82F6; selection-color: #FFFFFF; border: 1px solid #374151; }
    QSpinBox { color: #F3F4F6; background-color: #1F2937; border: 1px solid #374151; border-radius: 4px; padding: 2px 4px; }
    QListWidget::item:selected { background-color: #1D4ED8; color: #FFFFFF; }
    QMessageBox { background-color: #0B1220; }
    QMessageBox QLabel { color: #E5E7EB; font-size: 14px; }
    QMessageBox QPushButton {
        background-color: #374151;
        color: #F3F4F6;
        border: 1px solid #4B5563;
        border-radius: 8px;
        padding: 6px 12px;
        min-width: 70px;
        font-size: 13px;
        font-weight: 700;
    }
    QMessageBox QPushButton:hover { background-color: #4B5563; }
    QDialog { background-color: #0B1220; }
    QDialog QLabel { color: #E5E7EB; }
    QDialog QLineEdit, QDialog QTimeEdit, QDialog QDateEdit, QDialog QComboBox, QDialog QTextEdit {
        color: #F3F4F6;
        background-color: #1F2937;
        border: 1px solid #374151;
        border-radius: 8px;
        padding: 6px 8px;
    }
    QDialog QPushButton {
        background-color: #374151;
        color: #F3F4F6;
        border: 1px solid #4B5563;
        border-radius: 8px;
        padding: 6px 12px;
        font-size: 13px;
        font-weight: 700;
    }
    QDialog QPushButton:hover { background-color: #4B5563; }
    QCheckBox::indicator {
        width: 18px;
        height: 18px;
        background-color: #374151;
        border: 1px solid #6B7280;
        border-radius: 4px;
    }
    QCheckBox::indicator:checked {
        background-color: #3B82F6;
        border: 1px solid #2563EB;
    }
    QCalendarWidget QWidget { alternate-background-color: #111827; }
    QCalendarWidget QToolButton {
        color: #F3F4F6;
        background-color: #1F2937;
        border: 1px solid #374151;
        border-radius: 6px;
        padding: 4px 8px;
    }
    QCalendarWidget QMenu {
        color: #F3F4F6;
        background-color: #1F2937;
    }
    QCalendarWidget QSpinBox {
        color: #F3F4F6;
        background-color: #1F2937;
        selection-background-color: #3B82F6;
        selection-color: #FFFFFF;
    }
    QCalendarWidget QAbstractItemView {
        color: #F3F4F6;
        background-color: #1F2937;
        selection-background-color: #3B82F6;
        selection-color: #FFFFFF;
        alternate-background-color: #111827;
    }
    #hdr_frame { background-color: #1F2937; border-bottom: 1px solid #374151; }
    #hdr_voiceState_Lbl { font-size: 16px; font-weight: bold; color: #34D399; }
    .CardFrame {
        background-color: #1F2937;
        border-radius: 16px;
        border: 1px solid #374151;
    }
    .TitleText { font-size: 20px; font-weight: bold; color: #F9FAFB; }
    .SubText { font-size: 14px; color: #D1D5DB; }
    .StatusText { font-size: 24px; font-weight: bold; color: #60A5FA; }
    QPushButton {
        background-color: #374151;
        border: 1px solid #4B5563;
        border-radius: 8px;
        padding: 10px;
        font-size: 14px;
        color: #F3F4F6;
        font-weight: bold;
    }
    QPushButton:hover { background-color: #4B5563; }
    QPushButton.PrimaryBtn { background-color: #2563EB; color: white; border: none; }
    QPushButton.PrimaryBtn:hover { background-color: #1D4ED8; }
    QPushButton.StopBtn { background-color: #EF4444; color: white; border: none; }
    QPushButton.ActionBtn { font-size: 16px; padding: 15px; }

    #weather_card_btn { background-color: #1F2937; border: 2px solid #3B82F6; border-radius: 16px; }
    #weather_card_btn:hover { background-color: #111827; }
"""

THEME_STYLES = {
    "light": GLOBAL_STYLE,
    "dark": DARK_STYLE,
}


def themed_text_panel_style(theme: str, *, font_size: int = 16) -> str:
    """Return a consistent text panel style for input/log widgets by theme."""
    if str(theme) == "dark":
        return (
            "background-color: #1F2937; color: #F3F4F6; border: 1px solid #374151;"
            f" border-radius: 10px; font-family: monospace; font-size: {int(font_size)}px; padding: 10px;"
        )
    return (
        "background-color: #FFFFFF; color: #0F172A; border: 1px solid #CBD5E1;"
        f" border-radius: 10px; font-family: monospace; font-size: {int(font_size)}px; padding: 10px;"
    )
