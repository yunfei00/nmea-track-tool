from __future__ import annotations

from pathlib import Path

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
    QTableWidget,
    QTableWidgetItem,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from core.pipeline import TrackResult, build_track_from_file
from core.track_model import TrackPoint
from gui.presentation import SUMMARY_FIELDS, TABLE_COLUMNS, build_summary_rows, track_point_to_row_values

INVALID_ROW_COLOR = QColor(255, 235, 238)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("NMEA Track Viewer")
        self.resize(1200, 720)

        self._summary_labels: dict[str, QLabel] = {}
        self._table = QTableWidget(0, len(TABLE_COLUMNS))
        self._open_button = QPushButton("Open NMEA File")
        self._current_file_label = QLabel("No file loaded")

        self._build_ui()

    def _build_ui(self) -> None:
        self._build_actions()

        central_widget = QWidget(self)
        root_layout = QVBoxLayout(central_widget)

        controls_layout = QHBoxLayout()
        controls_layout.addWidget(self._open_button)
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
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._table.verticalHeader().setVisible(False)
        root_layout.addWidget(self._table, stretch=1)

        self.setCentralWidget(central_widget)
        self.statusBar().showMessage("Ready")

        self._open_button.clicked.connect(self.open_file_dialog)

    def _build_actions(self) -> None:
        open_action = QAction("Open NMEA File", self)
        open_action.triggered.connect(self.open_file_dialog)

        file_menu = self.menuBar().addMenu("File")
        file_menu.addAction(open_action)

        toolbar = QToolBar("Main", self)
        toolbar.addAction(open_action)
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

        self._current_file_label.setText(str(input_path))
        self._populate_summary(result)
        self._populate_table(result.points)
        self.statusBar().showMessage(f"Loaded {input_path}")

    def _populate_summary(self, result: TrackResult) -> None:
        summary_values = dict(build_summary_rows(result.summary))
        for label_text, field_name in SUMMARY_FIELDS:
            self._summary_labels[field_name].setText(summary_values[label_text])

    def _populate_table(self, points: list[TrackPoint]) -> None:
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
