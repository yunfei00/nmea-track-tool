from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cli.generate_track import generate_track_file

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication, QWidget
    from gui.main_window import MainWindow
except Exception as import_error:  # pragma: no cover - environment-dependent skip path
    QApplication = None
    QWidget = object
    MainWindow = None
    _GUI_IMPORT_ERROR = import_error
else:
    _GUI_IMPORT_ERROR = None


class GUITrackGenerationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if _GUI_IMPORT_ERROR is not None:
            raise unittest.SkipTest(f"PySide6 GUI runtime unavailable: {_GUI_IMPORT_ERROR}")
        cls._app = QApplication.instance() or QApplication([])

    def test_main_window_generates_track_and_updates_output_labels(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "generated_track.nmea"
            window = MainWindow(
                generate_track_fn=_mock_generate_track_file,
                map_view_factory=_FakeMapView,
            )
            window._start_lat_edit.setText("39.9042")
            window._start_lon_edit.setText("116.4074")
            window._end_lat_edit.setText("39.9142")
            window._end_lon_edit.setText("116.4274")
            window._generator_output_edit.setText(str(output_path))

            with patch("gui.main_window.QMessageBox.information") as information_mock:
                window.generate_track_from_inputs()

            self.assertTrue(output_path.is_file())
            self.assertEqual(window._generated_output_label.text(), str(output_path))
            self.assertIn("Generated ", window._generation_preview_label.text())
            self.assertEqual(window._current_file_label.text(), str(output_path))
            self.assertIsNotNone(window._session)
            self.assertGreater(len(window._session.current_result.points), 1)
            information_mock.assert_called_once()

    def test_main_window_reports_invalid_coordinate_input(self) -> None:
        window = MainWindow(
            generate_track_fn=_mock_generate_track_file,
            map_view_factory=_FakeMapView,
        )
        window._start_lat_edit.setText("not-a-number")
        window._start_lon_edit.setText("116.4074")
        window._end_lat_edit.setText("39.9142")
        window._end_lon_edit.setText("116.4274")

        with patch("gui.main_window.QMessageBox.critical") as critical_mock:
            window.generate_track_from_inputs()

        critical_mock.assert_called_once()
        self.assertEqual(window._generated_output_label.text(), "No generated file yet")


class _FakeMapView(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.last_result = None

    def set_track_result(
        self,
        result,
        *,
        use_smoothed_coordinates: bool = False,
        color_by_speed: bool = False,
    ) -> None:
        del use_smoothed_coordinates, color_by_speed
        self.last_result = result


def _mock_generate_track_file(
    *,
    start: tuple[float, float],
    end: tuple[float, float],
    output_path: str | Path,
):
    return generate_track_file(
        start=start,
        end=end,
        output_path=output_path,
        routing_mode="mock",
        enable_traffic_lights=False,
    )


if __name__ == "__main__":
    unittest.main()
