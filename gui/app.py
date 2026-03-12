from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Sequence


def main(argv: Sequence[str] | None = None) -> int:
    arguments = list(argv) if argv is not None else sys.argv[1:]

    if not _qt_runtime_available():
        relaunch_code = _relaunch_with_venv(arguments)
        if relaunch_code is not None:
            return relaunch_code

        print(
            "Error: PySide6 Qt runtime is unavailable in the current interpreter. "
            "Try .venv\\Scripts\\python.exe -m gui.app",
            file=sys.stderr,
        )
        return 1

    from PySide6.QtWidgets import QApplication
    from gui.main_window import MainWindow

    app = QApplication([sys.argv[0], *arguments])
    window = MainWindow()
    window.show()
    return app.exec()


def _qt_runtime_available() -> bool:
    try:
        from PySide6.QtWebEngineWidgets import QWebEngineView  # noqa: F401
        from PySide6.QtWidgets import QApplication  # noqa: F401
    except Exception:
        return False
    return True


def _relaunch_with_venv(arguments: list[str]) -> int | None:
    if os.environ.get("NMEA_TRACK_GUI_RELAUNCHED") == "1":
        return None

    repo_root = Path(__file__).resolve().parents[1]
    venv_python = repo_root / ".venv" / "Scripts" / "python.exe"
    if not venv_python.is_file():
        return None

    current_python = Path(sys.executable).resolve()
    if current_python == venv_python.resolve():
        return None

    environment = os.environ.copy()
    environment["NMEA_TRACK_GUI_RELAUNCHED"] = "1"
    completed = subprocess.run(
        [str(venv_python), "-m", "gui.app", *arguments],
        check=False,
        env=environment,
    )
    return completed.returncode


if __name__ == "__main__":
    sys.exit(main())
