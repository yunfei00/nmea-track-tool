from __future__ import annotations

from datetime import timezone
from pathlib import Path

from PySide6.QtCore import QDateTime, Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDateTimeEdit,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QProgressBar,
    QPlainTextEdit,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from .slim_engine import SlimOptions, slim_file


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("NMEA 精简工具")
        self.resize(900, 700)
        c = QWidget(self)
        self.setCentralWidget(c)
        root = QVBoxLayout(c)

        self.input_edit = QLineEdit()
        self.output_edit = QLineEdit()
        self.log = QPlainTextEdit(); self.log.setReadOnly(True)
        self.progress = QProgressBar(); self.progress.setRange(0, 100)
        self.stats = QLabel("尚未处理")

        grid = QGridLayout()
        grid.addWidget(QLabel("输入文件"), 0, 0); grid.addWidget(self.input_edit, 0, 1)
        in_btn = QPushButton("选择输入"); in_btn.clicked.connect(self.choose_input); grid.addWidget(in_btn, 0, 2)
        grid.addWidget(QLabel("输出文件"), 1, 0); grid.addWidget(self.output_edit, 1, 1)
        out_btn = QPushButton("选择输出"); out_btn.clicked.connect(self.choose_output); grid.addWidget(out_btn, 1, 2)
        root.addLayout(grid)

        box = QGroupBox("精简选项")
        b = QGridLayout(box)
        self.keep_gga = QCheckBox("保留 GGA"); self.keep_gga.setChecked(True)
        self.keep_rmc = QCheckBox("保留 RMC"); self.keep_rmc.setChecked(True)
        self.keep_gsa = QCheckBox("保留 GSA"); self.keep_gsa.setChecked(True)
        self.keep_gsv = QCheckBox("保留 GSV"); self.keep_gsv.setChecked(True)
        self.drop_vtg = QCheckBox("删除 VTG"); self.drop_vtg.setChecked(True)
        self.drop_gns = QCheckBox("删除 GNS"); self.drop_gns.setChecked(True)
        self.drop_dtm = QCheckBox("删除 DTM"); self.drop_dtm.setChecked(True)
        self.drop_unknown = QCheckBox("删除未知语句"); self.drop_unknown.setChecked(True)
        self.to_gp = QCheckBox("转换 talker 为 GP")
        self.gsv_spin = QSpinBox(); self.gsv_spin.setRange(0, 3600); self.gsv_spin.setValue(0)
        b.addWidget(self.keep_gga,0,0); b.addWidget(self.keep_rmc,0,1); b.addWidget(self.keep_gsa,1,0); b.addWidget(self.keep_gsv,1,1)
        b.addWidget(self.drop_vtg,2,0); b.addWidget(self.drop_gns,2,1); b.addWidget(self.drop_dtm,3,0); b.addWidget(self.drop_unknown,3,1)
        b.addWidget(self.to_gp,4,0); b.addWidget(QLabel("GSV降频秒数"),4,1); b.addWidget(self.gsv_spin,4,2)
        root.addWidget(box)

        time_box = QGroupBox("时间调整")
        time_layout = QGridLayout(time_box)
        self.enable_start_datetime = QCheckBox("设置输出轨迹起始时间")
        self.start_datetime = QDateTimeEdit(QDateTime.currentDateTimeUtc())
        self.start_datetime.setDisplayFormat("yyyy-MM-dd HH:mm:ss")
        self.start_datetime.setTimeSpec(Qt.TimeSpec.UTC)
        self.start_datetime.setEnabled(False)
        self.enable_start_datetime.toggled.connect(self.start_datetime.setEnabled)
        time_layout.addWidget(self.enable_start_datetime, 0, 0)
        time_layout.addWidget(QLabel("起始时间（UTC）"), 1, 0)
        time_layout.addWidget(self.start_datetime, 1, 1)
        root.addWidget(time_box)

        row = QHBoxLayout()
        preview = QPushButton("预览统计"); preview.clicked.connect(lambda: self.run(preview_only=True))
        start = QPushButton("开始精简"); start.clicked.connect(lambda: self.run(preview_only=False))
        row.addWidget(preview); row.addWidget(start); root.addLayout(row)
        root.addWidget(self.progress); root.addWidget(self.log); root.addWidget(self.stats)

    def choose_input(self):
        p, _ = QFileDialog.getOpenFileName(self, "选择输入", "", "Text (*.nmea *.txt *.log *.csv);;All (*)")
        if p:
            self.input_edit.setText(p)
            default = str(Path(p).with_name(Path(p).stem + "_slim.nmea"))
            if not self.output_edit.text():
                self.output_edit.setText(default)

    def choose_output(self):
        p, _ = QFileDialog.getSaveFileName(self, "选择输出", self.output_edit.text() or "output_slim.nmea", "NMEA (*.nmea);;All (*)")
        if p:
            self.output_edit.setText(p)

    def _options(self) -> SlimOptions:
        start_datetime_utc = None
        if self.enable_start_datetime.isChecked():
            start_datetime_utc = self.start_datetime.dateTime().toUTC().toPython().astimezone(timezone.utc)
        return SlimOptions(
            keep_gga=self.keep_gga.isChecked(),
            keep_rmc=self.keep_rmc.isChecked(),
            keep_gsa=self.keep_gsa.isChecked(),
            keep_gsv=self.keep_gsv.isChecked(),
            drop_vtg=self.drop_vtg.isChecked(),
            drop_gns=self.drop_gns.isChecked(),
            drop_dtm=self.drop_dtm.isChecked(),
            drop_unknown=self.drop_unknown.isChecked(),
            convert_talker_to_gp=self.to_gp.isChecked(),
            gsv_interval_sec=self.gsv_spin.value(),
            start_datetime_utc=start_datetime_utc,
        )

    def run(self, preview_only: bool):
        input_path = self.input_edit.text().strip()
        output_path = self.output_edit.text().strip()
        if not input_path:
            self.log.appendPlainText("请选择输入文件")
            return
        if not output_path:
            output_path = str(Path(input_path).with_name(Path(input_path).stem + "_slim.nmea"))
            self.output_edit.setText(output_path)
        self.progress.setValue(20)
        temp_out = output_path if not preview_only else str(Path(output_path).with_suffix(".preview.nmea"))
        try:
            stats = slim_file(input_path, temp_out, self._options())
        except ValueError as exc:
            self.log.appendPlainText(str(exc))
            self.progress.setValue(0)
            return
        if self.enable_start_datetime.isChecked():
            value = self.start_datetime.dateTime().toUTC().toString("yyyy-MM-ddTHH:mm:ss'Z'")
            self.log.appendPlainText(f"已将输出轨迹起始时间设置为：{value}")
        if preview_only:
            Path(temp_out).unlink(missing_ok=True)
        self.progress.setValue(100)
        ratio = (1 - (stats.output_size / stats.input_size)) * 100 if stats.input_size else 0
        self.stats.setText(
            f"物理行:{stats.physical_lines} 提取语句:{stats.extracted_sentences} 粘连拆分:{stats.concatenated_sentence_lines} "
            f"无校验和:{stats.no_checksum_sentences} 原始:{stats.total_lines} 保留:{stats.kept_lines} 删除:{stats.dropped_lines} "
            f"未知删除:{stats.unknown_sentences} 非NMEA:{stats.non_nmea_lines} 输出:{output_path} 压缩:{ratio:.1f}%"
        )
        if stats.concatenated_sentence_lines > 0:
            self.log.appendPlainText(
                f"检测到一行多个 NMEA，已自动拆分处理（拆分数量: {stats.concatenated_sentence_lines}）"
            )
        self.log.appendPlainText("完成" if not preview_only else "预览完成")
