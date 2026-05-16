from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cli.generate_track import generate_track_file
from geo.geocoder import GeocodingError
from gui.generator_home import MapViewport, load_saved_map_view

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtCore import Signal
    from PySide6.QtWidgets import QApplication, QWidget
    from gui.main_window import MainWindow
except Exception as import_error:  # pragma: no cover - environment-dependent skip path
    QApplication = None
    Signal = None
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

    def test_main_window_reports_invalid_coordinate_input_on_generate(self) -> None:
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

    def test_main_window_map_click_sets_start_then_exits_pick_mode(self) -> None:
        window = MainWindow(
            generate_track_fn=_mock_generate_track_file,
            map_view_factory=_FakeMapView,
        )

        window.toggle_pick_start_mode(True)
        window._handle_map_click(39.9042, 116.4074)

        self.assertEqual(window._start_lat_edit.text(), "39.904200")
        self.assertEqual(window._start_lon_edit.text(), "116.407400")
        self.assertFalse(window._pick_start_button.isChecked())
        self.assertEqual(window._map_view.last_pick_mode, None)
        self.assertEqual(window._map_view.last_picked_start, (39.9042, 116.4074))
        self.assertEqual(
            window._resolution_feedback_label.text(),
            "Selected start from map -> (39.90, 116.41)",
        )

    def test_main_window_applies_saved_startup_map_view(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            state_path = Path(temp_dir) / "map_home.json"
            saved_view = MapViewport(latitude=31.2304, longitude=121.4737, zoom=12)
            state_path.write_text('{"lat":31.2304,"lon":121.4737,"zoom":12}', encoding="utf-8")

            window = MainWindow(
                generate_track_fn=_mock_generate_track_file,
                map_view_factory=_FakeMapView,
                map_state_path=state_path,
                default_map_view=MapViewport(latitude=39.9042, longitude=116.4074, zoom=11),
            )

        self.assertEqual(window._map_view.last_home_view, saved_view)

    def test_main_window_refresh_generator_markers_syncs_field_edits_to_map(self) -> None:
        window = MainWindow(
            generate_track_fn=_mock_generate_track_file,
            map_view_factory=_FakeMapView,
        )
        window._start_lat_edit.setText("39.9042")
        window._start_lon_edit.setText("116.4074")
        window._end_lat_edit.setText("39.9142")
        window._end_lon_edit.setText("116.4274")

        window.refresh_generator_markers()

        self.assertEqual(window._map_view.last_picked_start, (39.9042, 116.4074))
        self.assertEqual(window._map_view.last_picked_end, (39.9142, 116.4274))

    def test_main_window_coordinate_edit_updates_location_input_and_feedback(self) -> None:
        window = MainWindow(
            generate_track_fn=_mock_generate_track_file,
            map_view_factory=_FakeMapView,
        )
        window._start_lat_edit.setText("39.9042")
        window._start_lon_edit.setText("116.4074")

        window._handle_start_coordinate_editing_finished()

        self.assertEqual(window._start_location_edit.text(), "39.904200,116.407400")
        self.assertEqual(window._map_view.last_picked_start, (39.9042, 116.4074))
        self.assertEqual(window._map_view.last_home_view, MapViewport(39.9042, 116.4074, 14))
        self.assertEqual(
            window._resolution_feedback_label.text(),
            "Resolved coordinates -> (39.90, 116.41)",
        )

    def test_main_window_coordinate_edit_error_updates_feedback_without_map_change(self) -> None:
        window = MainWindow(
            generate_track_fn=_mock_generate_track_file,
            map_view_factory=_FakeMapView,
        )
        window._start_lat_edit.setText("not-a-number")
        window._start_lon_edit.setText("116.4074")

        window._handle_start_coordinate_editing_finished()

        self.assertIn("Start input error", window._resolution_feedback_label.text())
        self.assertIsNone(window._map_view.last_picked_start)

    def test_main_window_persists_map_viewport_changes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            state_path = Path(temp_dir) / "map_home.json"
            window = MainWindow(
                generate_track_fn=_mock_generate_track_file,
                map_view_factory=_FakeMapView,
                map_state_path=state_path,
            )

            window._map_view.viewportChanged.emit(22.5431, 114.0579, 10)

            self.assertEqual(
                load_saved_map_view(state_path),
                MapViewport(latitude=22.5431, longitude=114.0579, zoom=10),
            )

    def test_main_window_auto_resolves_address_on_return_pressed(self) -> None:
        geocoder = _FakeGeocoder({"tiananmen": (39.9087, 116.3975)})
        window = MainWindow(
            generate_track_fn=_mock_generate_track_file,
            map_view_factory=_FakeMapView,
            geocoder=geocoder,
        )
        window._start_location_edit.setText("Tiananmen")

        window._start_location_edit.returnPressed.emit()

        self.assertEqual(window._start_lat_edit.text(), "39.908700")
        self.assertEqual(window._start_lon_edit.text(), "116.397500")
        self.assertEqual(window._map_view.last_picked_start, (39.9087, 116.3975))
        self.assertEqual(window._map_view.last_home_view, MapViewport(39.9087, 116.3975, 14))
        self.assertEqual(
            window._resolution_feedback_label.text(),
            "Resolved: Tiananmen -> (39.91, 116.40)",
        )
        self.assertEqual(geocoder.calls, ["Tiananmen"])

    def test_main_window_auto_resolves_address_on_editing_finished(self) -> None:
        geocoder = _FakeGeocoder({"beijing south railway station": (39.8652, 116.3789)})
        window = MainWindow(
            generate_track_fn=_mock_generate_track_file,
            map_view_factory=_FakeMapView,
            geocoder=geocoder,
        )
        window._end_location_edit.setText("Beijing South Railway Station")

        window._end_location_edit.editingFinished.emit()

        self.assertEqual(window._end_lat_edit.text(), "39.865200")
        self.assertEqual(window._end_lon_edit.text(), "116.378900")
        self.assertEqual(window._map_view.last_picked_end, (39.8652, 116.3789))
        self.assertEqual(
            window._resolution_feedback_label.text(),
            "Resolved: Beijing South Railway Station -> (39.87, 116.38)",
        )

    def test_main_window_resolves_xian_to_valid_coordinate_fields(self) -> None:
        geocoder = _FakeGeocoder({"\u897f\u5b89": (34.261004, 108.9423363)})
        window = MainWindow(
            generate_track_fn=_mock_generate_track_file,
            map_view_factory=_FakeMapView,
            geocoder=geocoder,
        )
        window._start_location_edit.setText("\u897f\u5b89")

        window.resolve_start_input()

        self.assertTrue(30.0 <= float(window._start_lat_edit.text()) <= 40.0)
        self.assertTrue(100.0 <= float(window._start_lon_edit.text()) <= 120.0)
        self.assertEqual(
            window._resolution_feedback_label.text(),
            "Resolved: \u897f\u5b89 -> (34.26, 108.94)",
        )

    def test_main_window_reports_address_lookup_failure_inline(self) -> None:
        window = MainWindow(
            generate_track_fn=_mock_generate_track_file,
            map_view_factory=_FakeMapView,
            geocoder=_FakeGeocoder({}, failing_queries={"Unknown Place"}),
        )
        window._start_location_edit.setText("Unknown Place")

        window.resolve_start_input()

        self.assertEqual(window._start_lat_edit.text(), "")
        self.assertEqual(window._start_lon_edit.text(), "")
        self.assertEqual(
            window._resolution_feedback_label.text(),
            'Start input error: No location results found for "Unknown Place".',
        )
        self.assertIsNone(window._map_view.last_picked_start)

    def test_main_window_rejects_invalid_geocoder_coordinates_inline(self) -> None:
        window = MainWindow(
            generate_track_fn=_mock_generate_track_file,
            map_view_factory=_FakeMapView,
            geocoder=_FakeGeocoder({"\u897f\u5b89": (1004, 2336)}),
        )
        window._start_location_edit.setText("\u897f\u5b89")

        window.resolve_start_input()

        self.assertEqual(window._start_lat_edit.text(), "")
        self.assertEqual(window._start_lon_edit.text(), "")
        self.assertEqual(
            window._resolution_feedback_label.text(),
            "Start input error: Latitude must be in [-90.0, 90.0].",
        )
        self.assertIsNone(window._map_view.last_picked_start)

    def test_main_window_can_generate_from_address_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "generated_track.nmea"
            geocoder = _FakeGeocoder(
                {
                    "tiananmen": (39.9087, 116.3975),
                    "beijing south railway station": (39.8652, 116.3789),
                }
            )
            window = MainWindow(
                generate_track_fn=_mock_generate_track_file,
                map_view_factory=_FakeMapView,
                geocoder=geocoder,
            )
            window._start_location_edit.setText("Tiananmen")
            window._end_location_edit.setText("Beijing South Railway Station")
            window._generator_output_edit.setText(str(output_path))

            with patch("gui.main_window.QMessageBox.information"):
                window.generate_track_from_inputs()

            self.assertTrue(output_path.is_file())
            self.assertEqual(window._start_lat_edit.text(), "39.908700")
            self.assertEqual(window._end_lon_edit.text(), "116.378900")


if Signal is not None:
    class _FakeMapView(QWidget):
        mapClicked = Signal(float, float)
        viewportChanged = Signal(float, float, int)

        def __init__(self) -> None:
            super().__init__()
            self.last_result = None
            self.last_pick_mode = None
            self.last_picked_start = None
            self.last_picked_end = None
            self.last_home_view = None

        def set_track_result(
            self,
            result,
            *,
            use_smoothed_coordinates: bool = False,
            color_by_speed: bool = False,
        ) -> None:
            del use_smoothed_coordinates, color_by_speed
            self.last_result = result

        def set_picked_points(
            self,
            *,
            start=None,
            end=None,
        ) -> None:
            self.last_picked_start = start
            self.last_picked_end = end

        def set_pick_mode(self, mode) -> None:
            self.last_pick_mode = mode

        def set_home_view(self, view) -> None:
            self.last_home_view = view
else:
    class _FakeMapView(QWidget):
        def __init__(self) -> None:
            self.last_result = None
            self.last_pick_mode = None
            self.last_picked_start = None
            self.last_picked_end = None
            self.last_home_view = None

        def set_track_result(
            self,
            result,
            *,
            use_smoothed_coordinates: bool = False,
            color_by_speed: bool = False,
        ) -> None:
            del use_smoothed_coordinates, color_by_speed
            self.last_result = result

        def set_picked_points(
            self,
            *,
            start=None,
            end=None,
        ) -> None:
            self.last_picked_start = start
            self.last_picked_end = end

        def set_pick_mode(self, mode) -> None:
            self.last_pick_mode = mode

        def set_home_view(self, view) -> None:
            self.last_home_view = view


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


class _FakeGeocoder:
    def __init__(
        self,
        results: dict[str, tuple[float, float]],
        *,
        failing_queries: set[str] | None = None,
    ) -> None:
        self._results = results
        self._failing_queries = {query.casefold() for query in (failing_queries or set())}
        self.calls: list[str] = []

    def geocode(self, query: str) -> tuple[float, float]:
        self.calls.append(query)
        normalized_query = query.casefold()
        if normalized_query in self._failing_queries:
            raise GeocodingError(f'No location results found for "{query}".')
        return self._results[normalized_query]


if __name__ == "__main__":
    unittest.main()
