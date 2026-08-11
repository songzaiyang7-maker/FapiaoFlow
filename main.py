"""FapiaoFlow 应用入口。

运行：
    python main.py
"""

from __future__ import annotations

import sys

from PyQt6.QtWidgets import QApplication

from src.gui.main_window import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("FapiaoFlow")
    app.setOrganizationName("FapiaoFlow")

    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
