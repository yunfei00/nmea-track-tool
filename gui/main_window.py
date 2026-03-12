from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
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

from core.pipeline import TrackResult, build_track_from_file
from core.track_model import TrackPoint
from gui.editing import TrackEditSession, build_window_title
from gui.map_view import TrackMapView
from gui.presentation import SUMMARY_FIELDS, TABLE_COLUMNS, build_summary_rows, track_point_to_row_values

INVALID_ROW_COLOR = QColor(255, 235, 238)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.resize(1200, 720)

        self._session: TrackEditSession | None = None
        self._summary_labels: dict[str, QLabel] = {}
        self._table = QTableWidget(0, len(TABLE_COLUMNS))
        self._map_view = TrackMapView()
        self._open_button = QPushButton("Open NMEA File")
        self._delete_button = QPushButton("Delete Selected Points")
        self._reset_button = QPushButton("Reset to Original Data")
        self._current_file_label = QLabel("No file loaded")
        self._delete_action: QAction | None = None
        self._reset_action: QAction | None = None

        self._build_ui()
        self._update_window_state()

    def _build_ui(self) -> None:
        self._build_actions()

        central_widget = QWidget(self)
        root_layout = QVBoxLayout(central_widget)

        controls_layout = QHBoxLayout()
        controls_layout.addWidget(self._open_button)
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

        self._open_button.clicked.connect(self.open_file_dialog)
        self._delete_button.clicked.connect(self.delete_selected_points)
        self._reset_button.clicked.connect(self.reset_to_original_data)
        self._table.itemSelectionChanged.connect(self._update_window_state)

    def _build_actions(self) -> None:
        open_action = QAction("Open NMEA File", self)
        open_action.triggered.connect(self.open_file_dialog)
        delete_action = QAction("Delete Selected Points", self)
        delete_action.triggered.connect(self.delete_selected_points)
        reset_action = QAction("Reset to Original Data", self)
        reset_action.triggered.connect(self.reset_to_original_data)
        self._delete_action = delete_action
        self._reset_action = reset_action

        file_menu = self.menuBar().addMenu("File")
        file_menu.addAction(open_action)
        file_menu.addAction(delete_action)
        file_menu.addAction(reset_action)

        toolbar = QToolBar("Main", self)
        toolbar.addAction(open_action)
        toolbar.addAction(delete_action)
        toolbar.addAction(reset_action)
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

    def _populate_summary(self, result: TrackResult) -> None:
        summary_values = dict(build_summary_rows(result.summary))
        for label_text, field_name in SUMMARY_FIELDS:
            self._summary_labels[field_name].setText(summary_values[label_text])

    def _populate_table(self, points: list[TrackPoint]) -> None:
        self._table.clearContents()
        self._table.setRowCount(len(points))

        for row_index, point in enumerate(points):
            row_values = track_point_to_row_values(point)
            for column_index, value in enumerate(row_values):
                item = QTableWidgetItem(value)
                if not point.is_valid:
                    item.setBackground(INVALID_ROW_COLOR)
                if column_index == len(row_values) - 1 and point.invalid_reason:
                    item.setToolTip(point.invalid_reason)
                self._table.setItem(row_index, column_index, item)

    def _apply_track_result(self, result: TrackResult) -> None:
        if self._session is not None and self._session.file_path is not None:
            self._current_file_label.setText(str(self._session.file_path))
        self._populate_summary(result)
        self._populate_table(result.points)
        self._map_view.set_track_result(result)
        self._update_window_state()

    def _selected_row_indexes(self) -> list[int]:
        row_indexes = {model_index.row() for model_index in self._table.selectionModel().selectedRows()}
        return sorted(row_indexes)

    def _update_window_state(self) -> None:
        has_session = self._session is not None
        has_selection = bool(self._selected_row_indexes()) if has_session else False
        is_modified = self._session.is_modified if has_session else False

        self.setWindowTitle(
            build_window_title(
                self._session.file_path if has_session else None,
                is_modified,
            )
        )

        self._delete_button.setEnabled(has_selection)
        self._reset_button.setEnabled(has_session and is_modified)
        if self._delete_action is not None:
            self._delete_action.setEnabled(has_selection)
        if self._reset_action is not None:
            self._reset_action.setEnabled(has_session and is_modified)
