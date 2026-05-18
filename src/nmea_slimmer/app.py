from __future__ import annotations

import os
import sys
import traceback
from pathlib import Path
from typing import TYPE_CHECKING, Sequence

if TYPE_CHECKING:
    from PySide6.QtWidgets import QApplication, QMainWindow


def create_app(arguments: Sequence[str] | None = None) -> "QApplication":
    from PySide6.QtWidgets import QApplication

    app_arguments = [sys.argv[0], *(list(arguments) if arguments is not None else sys.argv[1:])]
    return QApplication.instance() or QApplication(app_arguments)


def main(argv: Sequence[str] | None = None) -> int:
    arguments = list(argv) if argv is not None else sys.argv[1:]
    smoke_test = "--smoke-test" in arguments
    if smoke_test:
        arguments.remove("--smoke-test")
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    try:
        main_window_class = _load_main_window()
        app = create_app(arguments)
        window = main_window_class()
        if smoke_test:
            window.close()
            app.processEvents()
            return 0
        window.show()
        return app.exec()
    except Exception as exc:
        _report_startup_error("NMEA Slimmer failed during startup.", exc)
        return 1


def _load_main_window() -> type["QMainWindow"]:
    try:
        from .main_window import MainWindow
    except ImportError:  # fallback for direct execution: python src/nmea_slimmer/app.py
        if __package__:
            raise
        src_dir = Path(__file__).resolve().parents[1]
        if str(src_dir) not in sys.path:
            sys.path.insert(0, str(src_dir))
        from nmea_slimmer.main_window import MainWindow
    return MainWindow


def _report_startup_error(message: str, error: Exception) -> None:
    details = "".join(traceback.format_exception(type(error), error, error.__traceback__))
    log_path = _write_startup_log(f"{message}\n\n{details}")
    user_message = (
        f"{message}\n\n"
        f"Details were written to:\n{log_path}\n\n"
        "If running from source, try .venv\\Scripts\\python.exe -m nmea_slimmer"
    )
    print(f"Error: {message}\nStartup log: {log_path}", file=sys.stderr)
    _show_windows_error_message(user_message)


def _write_startup_log(content: str) -> Path:
    candidates: list[Path] = []
    if getattr(sys, "frozen", False):
        candidates.append(Path(sys.executable).resolve().with_suffix(".startup.log"))
    candidates.append(Path.cwd() / "nmea-slimmer.startup.log")
    candidates.append(Path(os.environ.get("TEMP", ".")) / "nmea-slimmer.startup.log")

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

        ctypes.windll.user32.MessageBoxW(None, message, "NMEA Slimmer", 0x10)
    except Exception:
        return


if __name__ == "__main__":
    raise SystemExit(main())
