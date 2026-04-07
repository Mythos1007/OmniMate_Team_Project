from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication, QMainWindow

from .face_test_panel import FaceTestPanel


def main() -> None:
    app = QApplication(sys.argv)
    window = QMainWindow()
    window.setWindowTitle("Face Test Demo")
    window.resize(980, 860)
    window.setCentralWidget(FaceTestPanel())
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
