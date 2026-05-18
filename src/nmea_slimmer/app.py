from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

try:
    from .main_window import MainWindow
except ImportError:  # fallback for direct execution: python src/nmea_slimmer/app.py
    from main_window import MainWindow  # type: ignore


def create_app() -> QApplication:
    return QApplication(sys.argv)


def main() -> int:
    app = create_app()
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
