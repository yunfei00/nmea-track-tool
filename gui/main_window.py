from __future__ import annotations

from pathlib import Path
from typing import Callable

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QColor, QKeySequence
from PySide6.QtWidgets import (
    QAbstractItemView,
    QGridLayout,
    QCheckBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from cli.generate_track import generate_track_file
from core.pipeline import TrackResult, build_track_from_file
from core.smoothing import DEFAULT_SMOOTHING_WINDOW
from core.track_model import TrackPoint
from gui.editing import TrackEditSession, build_window_title
from gui.exporting import export_cleaned_nmea, export_points_csv, export_summary_json
from gui.map_view import TrackMapView
from gui.presentation import SUMMARY_FIELDS, TABLE_COLUMNS, build_summary_rows, track_point_to_row_values

INVALID_ROW_COLOR = QColor(255, 235, 238)
ANOMALY_ROW_COLOR = QColor(255, 205, 210)
INVALID_ANOMALY_ROW_COLOR = QColor(239, 154, 154)
GenerateTrackFn = Callable[..., object]
MapViewFactory = Callable[[], QWidget]


class MainWindow(QMainWindow):
    def __init__(
        self,
        *,
        generate_track_fn: GenerateTrackFn = generate_track_file,
        map_view_factory: MapViewFactory | None = None,
    ) -> None:
        super().__init__()
        self.resize(1200, 720)

        self._session: TrackEditSession | None = None
        self._summary_labels: dict[str, QLabel] = {}
        self._table = QTableWidget(0, len(TABLE_COLUMNS))
        self._map_view = (
            map_view_factory()
            if map_view_factory is not None
            else TrackMapView()
        )
        self._generate_track_fn = generate_track_fn
        self._start_lat_edit = QLineEdit()
        self._start_lon_edit = QLineEdit()
        self._end_lat_edit = QLineEdit()
        self._end_lon_edit = QLineEdit()
        self._generator_output_edit = QLineEdit(str(self._default_generated_output_path()))
        self._pick_start_button = QPushButton("Pick Start")
        self._pick_end_button = QPushButton("Pick End")
        self._browse_generator_output_button = QPushButton("Browse")
        self._generate_button = QPushButton("Generate Track")
        self._generated_output_label = QLabel("No generated file yet")
        self._generation_preview_label = QLabel("No generated preview yet")
        self._active_pick_mode: str | None = None
        self._open_button = QPushButton("Open NMEA File")
        self._undo_button = QPushButton("Undo")
        self._redo_button = QPushButton("Redo")
        self._apply_smoothing_button = QPushButton("Apply Smoothing")
        self._smoothed_view_toggle = QCheckBox("Show Smoothed View")
        self._color_by_speed_toggle = QCheckBox("Color by Speed")
        self._detect_anomalies_button = QPushButton("Detect Anomalies")
        self._remove_anomalies_button = QPushButton("Remove All Anomalies")
        self._delete_button = QPushButton("Delete Selected Points")
        self._reset_button = QPushButton("Reset to Original Data")
        self._current_file_label = QLabel("No file loaded")
        self._color_by_speed_enabled = False
        self._undo_action: QAction | None = None
        self._redo_action: QAction | None = None
        self._apply_smoothing_action: QAction | None = None
        self._detect_anomalies_action: QAction | None = None
        self._remove_anomalies_action: QAction | None = None
        self._delete_action: QAction | None = None
        self._reset_action: QAction | None = None
        self._export_nmea_action: QAction | None = None
        self._export_csv_action: QAction | None = None
        self._export_json_action: QAction | None = None

        self._build_ui()
        self._update_window_state()

    def _build_ui(self) -> None:
        self._build_actions()

        central_widget = QWidget(self)
        root_layout = QVBoxLayout(central_widget)

        generator_group = QGroupBox("Track Generator")
        generator_layout = QGridLayout(generator_group)
        self._pick_start_button.setCheckable(True)
        self._pick_end_button.setCheckable(True)
        generator_layout.addWidget(QLabel("Start Lat"), 0, 0)
        generator_layout.addWidget(self._start_lat_edit, 0, 1)
        generator_layout.addWidget(QLabel("Start Lon"), 0, 2)
        generator_layout.addWidget(self._start_lon_edit, 0, 3)
        generator_layout.addWidget(self._pick_start_button, 0, 4)
        generator_layout.addWidget(QLabel("End Lat"), 1, 0)
        generator_layout.addWidget(self._end_lat_edit, 1, 1)
        generator_layout.addWidget(QLabel("End Lon"), 1, 2)
        generator_layout.addWidget(self._end_lon_edit, 1, 3)
        generator_layout.addWidget(self._pick_end_button, 1, 4)
        generator_layout.addWidget(QLabel("Output File"), 2, 0)
        generator_layout.addWidget(self._generator_output_edit, 2, 1, 1, 3)
        generator_layout.addWidget(self._browse_generator_output_button, 2, 4)
        generator_layout.addWidget(self._generate_button, 0, 5, 3, 1)
        generator_layout.addWidget(QLabel("Last Output"), 3, 0)
        generator_layout.addWidget(self._generated_output_label, 3, 1, 1, 5)
        generator_layout.addWidget(QLabel("Preview"), 4, 0)
        generator_layout.addWidget(self._generation_preview_label, 4, 1, 1, 5)
        root_layout.addWidget(generator_group)

        controls_layout = QHBoxLayout()
        controls_layout.addWidget(self._open_button)
        controls_layout.addWidget(self._undo_button)
        controls_layout.addWidget(self._redo_button)
        controls_layout.addWidget(self._apply_smoothing_button)
        controls_layout.addWidget(self._smoothed_view_toggle)
        controls_layout.addWidget(self._color_by_speed_toggle)
        controls_layout.addWidget(self._detect_anomalies_button)
        controls_layout.addWidget(self._remove_anomalies_button)
        controls_layout.addWidget(self._delete_button)
        controls_layout.addWidget(self._reset_button)
        controls_layout.addWidget(self._current_file_label, stretch=1)
        root_layout.addLayout(controls_layout)

        summary_group = QGroupBox("Summary")
        summary_layout = QFormLayout(summary_group)
        for label_text, field_name in SUMMARY_FIELDS:
            value_label = QLabel("-")
            summary_layout.addRow(label_text, value_label)
            self._summary_labels[field_name] = value_label
        root_layout.addWidget(summary_group)

        self._table.setHorizontalHeaderLabels([header for header, _ in TABLE_COLUMNS])
        self._table.setAlternatingRowColors(True)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._table.verticalHeader().setVisible(False)

        content_splitter = QSplitter(Qt.Orientation.Horizontal)
        content_splitter.addWidget(self._map_view)
        content_splitter.addWidget(self._table)
        content_splitter.setStretchFactor(0, 3)
        content_splitter.setStretchFactor(1, 4)
        root_layout.addWidget(content_splitter, stretch=1)

        self.setCentralWidget(central_widget)
        self.statusBar().showMessage("Ready")

        self._browse_generator_output_button.clicked.connect(self.browse_generator_output_path)
        self._generate_button.clicked.connect(self.generate_track_from_inputs)
        self._pick_start_button.clicked.connect(self.toggle_pick_start_mode)
        self._pick_end_button.clicked.connect(self.toggle_pick_end_mode)
        self._start_lat_edit.editingFinished.connect(self.refresh_generator_markers)
        self._start_lon_edit.editingFinished.connect(self.refresh_generator_markers)
        self._end_lat_edit.editingFinished.connect(self.refresh_generator_markers)
        self._end_lon_edit.editingFinished.connect(self.refresh_generator_markers)
        self._open_button.clicked.connect(self.open_file_dialog)
        self._undo_button.clicked.connect(self.undo_last_edit)
        self._redo_button.clicked.connect(self.redo_last_edit)
        self._apply_smoothing_button.clicked.connect(self.apply_smoothing)
        self._smoothed_view_toggle.toggled.connect(self.set_smoothed_view_enabled)
        self._color_by_speed_toggle.toggled.connect(self.set_color_by_speed_enabled)
        self._detect_anomalies_button.clicked.connect(self.detect_anomalies)
        self._remove_anomalies_button.clicked.connect(self.remove_all_anomalies)
        self._delete_button.clicked.connect(self.delete_selected_points)
        self._reset_button.clicked.connect(self.reset_to_original_data)
        self._table.itemSelectionChanged.connect(self._update_window_state)
        if hasattr(self._map_view, "mapClicked"):
            self._map_view.mapClicked.connect(self._handle_map_click)

    def browse_generator_output_path(self) -> None:
        suggested_path = Path(self._generator_output_edit.text().strip() or self._default_generated_output_path())
        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Select Generated NMEA Output",
            str(suggested_path),
            "NMEA Files (*.nmea);;All Files (*)",
        )
        if filename:
            self._generator_output_edit.setText(filename)

    def generate_track_from_inputs(self) -> None:
        try:
            start = (
                self._parse_coordinate_value(self._start_lat_edit.text(), "Start latitude", -90.0, 90.0),
                self._parse_coordinate_value(self._start_lon_edit.text(), "Start longitude", -180.0, 180.0),
            )
            end = (
                self._parse_coordinate_value(self._end_lat_edit.text(), "End latitude", -90.0, 90.0),
                self._parse_coordinate_value(self._end_lon_edit.text(), "End longitude", -180.0, 180.0),
            )
            output_path = Path(
                self._generator_output_edit.text().strip()
                or self._default_generated_output_path()
            )
            result = self._generate_track_fn(
                start=start,
                end=end,
                output_path=output_path,
            )
        except Exception as exc:
            QMessageBox.critical(self, "Generate Failed", f"Could not generate track:\n{exc}")
            self.statusBar().showMessage("Track generation failed")
            return

        output_path = Path(output_path)
        self._generator_output_edit.setText(str(output_path))
        self._generated_output_label.setText(str(output_path))
        self._generation_preview_label.setText(
            "Generated "
            f"{len(result.track_points)} points, "
            f"{len(result.traffic_light_stop_segments)} traffic-light stops"
        )
        self.load_file(output_path)
        QMessageBox.information(
            self,
            "Track Generated",
            f"Track generated successfully.\nOutput file:\n{output_path}",
        )
        self.statusBar().showMessage(f"Generated track to {output_path}")

    def toggle_pick_start_mode(self, checked: bool) -> None:
        self._set_pick_mode("start" if checked else None)

    def toggle_pick_end_mode(self, checked: bool) -> None:
        self._set_pick_mode("end" if checked else None)

    def refresh_generator_markers(self) -> None:
        start = self._try_parse_coordinate_pair(
            self._start_lat_edit.text(),
            self._start_lon_edit.text(),
        )
        end = self._try_parse_coordinate_pair(
            self._end_lat_edit.text(),
            self._end_lon_edit.text(),
        )
        self._sync_map_picker_state(start=start, end=end)

    def _handle_map_click(self, latitude: float, longitude: float) -> None:
        if self._active_pick_mode == "start":
            self._start_lat_edit.setText(f"{latitude:.6f}")
            self._start_lon_edit.setText(f"{longitude:.6f}")
            self.refresh_generator_markers()
            self._set_pick_mode(None)
            self.statusBar().showMessage("Start point selected from map")
            return

        if self._active_pick_mode == "end":
            self._end_lat_edit.setText(f"{latitude:.6f}")
            self._end_lon_edit.setText(f"{longitude:.6f}")
            self.refresh_generator_markers()
            self._set_pick_mode(None)
            self.statusBar().showMessage("End point selected from map")

    def _set_pick_mode(self, mode: str | None) -> None:
        self._active_pick_mode = mode
        self._pick_start_button.blockSignals(True)
        self._pick_end_button.blockSignals(True)
        self._pick_start_button.setChecked(mode == "start")
        self._pick_end_button.setChecked(mode == "end")
        self._pick_start_button.blockSignals(False)
        self._pick_end_button.blockSignals(False)

        self._sync_map_picker_state()
        if mode == "start":
            self.statusBar().showMessage("Pick Start active: click the map to choose coordinates")
        elif mode == "end":
            self.statusBar().showMessage("Pick End active: click the map to choose coordinates")

    def _sync_map_picker_state(
        self,
        *,
        start: tuple[float, float] | None = None,
        end: tuple[float, float] | None = None,
    ) -> None:
        if start is None:
            start = self._try_parse_coordinate_pair(
                self._start_lat_edit.text(),
                self._start_lon_edit.text(),
            )
        if end is None:
            end = self._try_parse_coordinate_pair(
                self._end_lat_edit.text(),
                self._end_lon_edit.text(),
            )

        if hasattr(self._map_view, "set_picked_points"):
            self._map_view.set_picked_points(start=start, end=end)
        if hasattr(self._map_view, "set_pick_mode"):
            self._map_view.set_pick_mode(self._active_pick_mode)

    def _build_actions(self) -> None:
        open_action = QAction("Open NMEA File", self)
        open_action.triggered.connect(self.open_file_dialog)
        undo_action = QAction("Undo", self)
        undo_action.setShortcut(QKeySequence("Ctrl+Z"))
        undo_action.triggered.connect(self.undo_last_edit)
        redo_action = QAction("Redo", self)
        redo_action.setShortcut(QKeySequence("Ctrl+Y"))
        redo_action.triggered.connect(self.redo_last_edit)
        apply_smoothing_action = QAction("Apply Smoothing", self)
        apply_smoothing_action.triggered.connect(self.apply_smoothing)
        detect_anomalies_action = QAction("Detect Anomalies", self)
        detect_anomalies_action.triggered.connect(self.detect_anomalies)
        remove_anomalies_action = QAction("Remove All Anomalies", self)
        remove_anomalies_action.triggered.connect(self.remove_all_anomalies)
        delete_action = QAction("Delete Selected Points", self)
        delete_action.triggered.connect(self.delete_selected_points)
        reset_action = QAction("Reset to Original Data", self)
        reset_action.triggered.connect(self.reset_to_original_data)
        export_nmea_action = QAction("Export Cleaned NMEA", self)
        export_nmea_action.triggered.connect(self.export_cleaned_nmea_file)
        export_csv_action = QAction("Export Points CSV", self)
        export_csv_action.triggered.connect(self.export_points_csv_file)
        export_json_action = QAction("Export Summary JSON", self)
        export_json_action.triggered.connect(self.export_summary_json_file)
        self._undo_action = undo_action
        self._redo_action = redo_action
        self._apply_smoothing_action = apply_smoothing_action
        self._detect_anomalies_action = detect_anomalies_action
        self._remove_anomalies_action = remove_anomalies_action
        self._delete_action = delete_action
        self._reset_action = reset_action
        self._export_nmea_action = export_nmea_action
        self._export_csv_action = export_csv_action
        self._export_json_action = export_json_action

        file_menu = self.menuBar().addMenu("File")
        file_menu.addAction(open_action)
        file_menu.addAction(undo_action)
        file_menu.addAction(redo_action)
        file_menu.addAction(apply_smoothing_action)
        file_menu.addAction(detect_anomalies_action)
        file_menu.addAction(remove_anomalies_action)
        file_menu.addAction(delete_action)
        file_menu.addAction(reset_action)
        file_menu.addSeparator()
        file_menu.addAction(export_nmea_action)
        file_menu.addAction(export_csv_action)
        file_menu.addAction(export_json_action)

        toolbar = QToolBar("Main", self)
        toolbar.addAction(open_action)
        toolbar.addAction(undo_action)
        toolbar.addAction(redo_action)
        toolbar.addAction(apply_smoothing_action)
        toolbar.addAction(detect_anomalies_action)
        toolbar.addAction(remove_anomalies_action)
        toolbar.addAction(delete_action)
        toolbar.addAction(reset_action)
        toolbar.addSeparator()
        toolbar.addAction(export_nmea_action)
        toolbar.addAction(export_csv_action)
        toolbar.addAction(export_json_action)
        self.addToolBar(toolbar)

    def open_file_dialog(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Open NMEA File",
            "",
            "NMEA Files (*.nmea *.txt *.log);;All Files (*)",
        )
        if filename:
            self.load_file(filename)

    def load_file(self, path: str | Path) -> None:
        input_path = Path(path)
        try:
            result = build_track_from_file(input_path)
        except Exception as exc:
            QMessageBox.critical(self, "Open Failed", f"Could not open file:\n{exc}")
            self.statusBar().showMessage("Failed to load file")
            return

        self._session = TrackEditSession.from_track_result(result, file_path=input_path)
        self._apply_track_result(result)
        self.statusBar().showMessage(f"Loaded {input_path}")

    def undo_last_edit(self) -> None:
        if self._session is None or not self._session.can_undo:
            self.statusBar().showMessage("Nothing to undo")
            return

        result = self._session.undo()
        self._apply_track_result(result)
        self.statusBar().showMessage("Undid last edit")

    def redo_last_edit(self) -> None:
        if self._session is None or not self._session.can_redo:
            self.statusBar().showMessage("Nothing to redo")
            return

        result = self._session.redo()
        self._apply_track_result(result)
        self.statusBar().showMessage("Redid last edit")

    def apply_smoothing(self) -> None:
        if self._session is None:
            return

        result = self._session.apply_smoothing(DEFAULT_SMOOTHING_WINDOW)
        self._apply_track_result(result)
        self.statusBar().showMessage(
            f"Applied smoothing with moving average window {DEFAULT_SMOOTHING_WINDOW}"
        )

    def set_smoothed_view_enabled(self, enabled: bool) -> None:
        if self._session is None or self._session.current_result is None:
            return

        self._session.set_use_smoothed_view(enabled)
        self._apply_track_result(self._session.current_result)
        if self._session.use_smoothed_view:
            self.statusBar().showMessage("Showing smoothed coordinates")
            return

        self.statusBar().showMessage("Showing raw coordinates")

    def set_color_by_speed_enabled(self, enabled: bool) -> None:
        self._color_by_speed_enabled = bool(enabled)

        if self._session is None or self._session.current_result is None:
            return

        self._apply_track_result(self._session.current_result)
        if self._color_by_speed_enabled:
            self.statusBar().showMessage("Color by speed enabled")
            return

        self.statusBar().showMessage("Color by speed disabled")

    def detect_anomalies(self) -> None:
        if self._session is None:
            return

        result = self._session.detect_anomalies()
        anomaly_count = len(self._session.anomaly_row_indexes())
        self._apply_track_result(result)
        if anomaly_count:
            self.statusBar().showMessage(f"Detected anomalies in {anomaly_count} point(s)")
            return

        self.statusBar().showMessage("No anomalies detected")

    def remove_all_anomalies(self) -> None:
        if self._session is None:
            return

        anomaly_count = len(self._session.anomaly_row_indexes())
        if not anomaly_count:
            self.statusBar().showMessage("No anomaly points to remove")
            return

        result = self._session.remove_all_anomalies()
        self._apply_track_result(result)
        self.statusBar().showMessage(f"Removed {anomaly_count} anomaly point(s)")

    def delete_selected_points(self) -> None:
        if self._session is None:
            return

        selected_rows = self._selected_row_indexes()
        if not selected_rows:
            self.statusBar().showMessage("No rows selected to delete")
            return

        result = self._session.delete_rows(selected_rows)
        self._apply_track_result(result)
        self.statusBar().showMessage(f"Deleted {len(selected_rows)} point(s)")

    def reset_to_original_data(self) -> None:
        if self._session is None:
            return

        result = self._session.reset()
        self._apply_track_result(result)
        self.statusBar().showMessage("Reset to original data")

    def export_cleaned_nmea_file(self) -> None:
        if self._session is None or self._session.current_result is None:
            return

        output_path = self._get_export_path(
            "Export Cleaned NMEA",
            ".nmea",
            "NMEA Files (*.nmea);;All Files (*)",
        )
        if output_path is None:
            return

        try:
            line_count = export_cleaned_nmea(self._session.current_result, output_path)
        except Exception as exc:
            QMessageBox.critical(self, "Export Failed", f"Could not export cleaned NMEA:\n{exc}")
            self.statusBar().showMessage("Failed to export cleaned NMEA")
            return

        self.statusBar().showMessage(
            f"Exported cleaned NMEA to {output_path} ({line_count} sentence lines)"
        )

    def export_points_csv_file(self) -> None:
        if self._session is None or self._session.current_result is None:
            return

        output_path = self._get_export_path(
            "Export Points CSV",
            ".csv",
            "CSV Files (*.csv);;All Files (*)",
        )
        if output_path is None:
            return

        try:
            export_points_csv(self._session.current_result, output_path)
        except Exception as exc:
            QMessageBox.critical(self, "Export Failed", f"Could not export points CSV:\n{exc}")
            self.statusBar().showMessage("Failed to export points CSV")
            return

        self.statusBar().showMessage(f"Exported points CSV to {output_path}")

    def export_summary_json_file(self) -> None:
        if self._session is None or self._session.current_result is None:
            return

        output_path = self._get_export_path(
            "Export Summary JSON",
            ".json",
            "JSON Files (*.json);;All Files (*)",
        )
        if output_path is None:
            return

        try:
            export_summary_json(self._session.current_result, output_path)
        except Exception as exc:
            QMessageBox.critical(self, "Export Failed", f"Could not export summary JSON:\n{exc}")
            self.statusBar().showMessage("Failed to export summary JSON")
            return

        self.statusBar().showMessage(f"Exported summary JSON to {output_path}")

    def _populate_summary(self, result: TrackResult) -> None:
        summary_values = dict(build_summary_rows(result.summary))
        for label_text, field_name in SUMMARY_FIELDS:
            self._summary_labels[field_name].setText(summary_values[label_text])

    def _populate_table(self, points: list[TrackPoint]) -> None:
        self._table.clearContents()
        self._table.setRowCount(len(points))
        use_smoothed_coordinates = (
            self._session.use_smoothed_view
            if self._session is not None
            else False
        )

        for row_index, point in enumerate(points):
            row_values = track_point_to_row_values(
                point,
                use_smoothed_coordinates=use_smoothed_coordinates,
            )
            row_color = self._row_background_color(point)
            row_tooltip = self._row_tooltip(point)
            for column_index, value in enumerate(row_values):
                item = QTableWidgetItem(value)
                if row_color is not None:
                    item.setBackground(row_color)
                if row_tooltip:
                    item.setToolTip(row_tooltip)
                self._table.setItem(row_index, column_index, item)

    def _apply_track_result(self, result: TrackResult) -> None:
        if self._session is not None and self._session.file_path is not None:
            self._current_file_label.setText(str(self._session.file_path))
        self._populate_summary(result)
        self._populate_table(result.points)
        self._map_view.set_track_result(
            result,
            use_smoothed_coordinates=(
                self._session.use_smoothed_view
                if self._session is not None
                else False
            ),
            color_by_speed=self._color_by_speed_enabled,
        )
        self._sync_map_picker_state()
        self._update_window_state()

    def _selected_row_indexes(self) -> list[int]:
        row_indexes = {model_index.row() for model_index in self._table.selectionModel().selectedRows()}
        return sorted(row_indexes)

    def _get_export_path(
        self,
        dialog_title: str,
        default_suffix: str,
        file_filter: str,
    ) -> Path | None:
        suggested_path = self._suggest_export_path(default_suffix)
        filename, _ = QFileDialog.getSaveFileName(
            self,
            dialog_title,
            str(suggested_path),
            file_filter,
        )
        if not filename:
            return None
        return Path(filename)

    def _suggest_export_path(self, suffix: str) -> Path:
        if self._session is None or self._session.file_path is None:
            return Path(f"track_export{suffix}")

        input_path = self._session.file_path
        return input_path.with_name(f"{input_path.stem}_cleaned{suffix}")

    def _row_background_color(self, point: TrackPoint) -> QColor | None:
        has_anomalies = bool(point.anomaly_flags)
        if has_anomalies and not point.is_valid:
            return INVALID_ANOMALY_ROW_COLOR
        if has_anomalies:
            return ANOMALY_ROW_COLOR
        if not point.is_valid:
            return INVALID_ROW_COLOR
        return None

    def _row_tooltip(self, point: TrackPoint) -> str:
        tooltip_lines: list[str] = []
        if point.invalid_reason:
            tooltip_lines.append(f"Invalid: {point.invalid_reason}")
        if point.anomaly_flags:
            tooltip_lines.append(f"Anomalies: {'; '.join(point.anomaly_flags)}")
        return "\n".join(tooltip_lines)

    def _update_window_state(self) -> None:
        has_session = self._session is not None
        has_selection = bool(self._selected_row_indexes()) if has_session else False
        is_modified = self._session.is_modified if has_session else False
        has_result = has_session and self._session.current_result is not None
        can_undo = self._session.can_undo if has_session else False
        can_redo = self._session.can_redo if has_session else False
        has_smoothed_points = self._session.has_smoothed_points if has_session else False
        has_anomaly_points = (
            bool(self._session.anomaly_row_indexes())
            if has_session and self._session.current_result is not None
            else False
        )

        self.setWindowTitle(
            build_window_title(
                self._session.file_path if has_session else None,
                is_modified,
            )
        )

        self._undo_button.setEnabled(can_undo)
        self._redo_button.setEnabled(can_redo)
        self._apply_smoothing_button.setEnabled(has_result)
        self._smoothed_view_toggle.setEnabled(has_smoothed_points)
        self._smoothed_view_toggle.blockSignals(True)
        self._smoothed_view_toggle.setChecked(
            self._session.use_smoothed_view if has_session else False
        )
        self._smoothed_view_toggle.blockSignals(False)
        self._color_by_speed_toggle.setEnabled(has_result)
        self._color_by_speed_toggle.blockSignals(True)
        self._color_by_speed_toggle.setChecked(self._color_by_speed_enabled)
        self._color_by_speed_toggle.blockSignals(False)
        self._detect_anomalies_button.setEnabled(has_result)
        self._remove_anomalies_button.setEnabled(has_anomaly_points)
        self._delete_button.setEnabled(has_selection)
        self._reset_button.setEnabled(has_session and is_modified)
        if self._undo_action is not None:
            self._undo_action.setEnabled(can_undo)
        if self._redo_action is not None:
            self._redo_action.setEnabled(can_redo)
        if self._apply_smoothing_action is not None:
            self._apply_smoothing_action.setEnabled(has_result)
        if self._detect_anomalies_action is not None:
            self._detect_anomalies_action.setEnabled(has_result)
        if self._remove_anomalies_action is not None:
            self._remove_anomalies_action.setEnabled(has_anomaly_points)
        if self._delete_action is not None:
            self._delete_action.setEnabled(has_selection)
        if self._reset_action is not None:
            self._reset_action.setEnabled(has_session and is_modified)
        if self._export_nmea_action is not None:
            self._export_nmea_action.setEnabled(has_result)
        if self._export_csv_action is not None:
            self._export_csv_action.setEnabled(has_result)
        if self._export_json_action is not None:
            self._export_json_action.setEnabled(has_result)
        picker_supported = hasattr(self._map_view, "set_pick_mode")
        self._pick_start_button.setEnabled(picker_supported)
        self._pick_end_button.setEnabled(picker_supported)

    def _default_generated_output_path(self) -> Path:
        return Path.cwd() / "output" / "generated_track.nmea"

    def _parse_coordinate_value(
        self,
        value: str,
        label: str,
        minimum: float,
        maximum: float,
    ) -> float:
        text = value.strip()
        if not text:
            raise ValueError(f"{label} is required.")

        try:
            parsed = float(text)
        except ValueError as exc:
            raise ValueError(f"{label} must be a valid number.") from exc

        if not minimum <= parsed <= maximum:
            raise ValueError(f"{label} must be in [{minimum}, {maximum}].")

        return parsed

    def _try_parse_coordinate_pair(
        self,
        latitude_text: str,
        longitude_text: str,
    ) -> tuple[float, float] | None:
        try:
            latitude = self._parse_coordinate_value(latitude_text, "Latitude", -90.0, 90.0)
            longitude = self._parse_coordinate_value(longitude_text, "Longitude", -180.0, 180.0)
        except ValueError:
            return None

        return latitude, longitude
