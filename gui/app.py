from __future__ import annotations

import os
import subprocess
import sys
import traceback
from pathlib import Path
from typing import Sequence


def main(argv: Sequence[str] | None = None) -> int:
    arguments = list(argv) if argv is not None else sys.argv[1:]
    smoke_test = "--smoke-test" in arguments
    if smoke_test:
        arguments.remove("--smoke-test")

    qt_runtime_error = _qt_runtime_error()
    if qt_runtime_error is not None:
        relaunch_code = _relaunch_with_venv(arguments)
        if relaunch_code is not None:
            return relaunch_code

        _report_startup_error(
            "PySide6 Qt runtime is unavailable in the current interpreter.",
            qt_runtime_error,
        )
        return 1

    try:
        from PySide6.QtWidgets import QApplication
        from gui.main_window import MainWindow

        app = QApplication([sys.argv[0], *arguments])
        window = MainWindow()
        if smoke_test:
            window.close()
            return 0
        window.show()
        return app.exec()
    except Exception as exc:
        _report_startup_error("NMEA Track Tool failed during startup.", exc)
        return 1


def _qt_runtime_error() -> Exception | None:
    try:
        from PySide6.QtWebEngineWidgets import QWebEngineView  # noqa: F401
        from PySide6.QtWidgets import QApplication  # noqa: F401
    except Exception as exc:
        return exc
    return None


def _report_startup_error(message: str, error: Exception) -> None:
    details = "".join(traceback.format_exception(type(error), error, error.__traceback__))
    log_path = _write_startup_log(f"{message}\n\n{details}")
    user_message = (
        f"{message}\n\n"
        f"Details were written to:\n{log_path}\n\n"
        "If running from source, try .venv\\Scripts\\python.exe -m gui.app"
    )
    print(f"Error: {message}\nStartup log: {log_path}", file=sys.stderr)
    _show_windows_error_message(user_message)


def _write_startup_log(content: str) -> Path:
    candidates = []
    if getattr(sys, "frozen", False):
        candidates.append(Path(sys.executable).resolve().with_suffix(".startup.log"))
    candidates.append(Path.cwd() / "nmea-track-tool.startup.log")
    candidates.append(Path(os.environ.get("TEMP", ".")) / "nmea-track-tool.startup.log")

    for path in candidates:
        try:
            path.write_text(content, encoding="utf-8")
            return path
        except OSError:
            continue
    return candidates[-1]


def _show_windows_error_message(message: str) -> None:
    if not sys.platform.startswith("win"):
        return
    try:
        import ctypes

        ctypes.windll.user32.MessageBoxW(None, message, "NMEA Track Tool", 0x10)
    except Exception:
        return


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
