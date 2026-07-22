"""Dialog for building comparison/batch reports from saved capture files.

ComparisonRunTableModel is deliberately Qt-free so validation and run
assembly are unit-testable headless; the QDialog is a thin shell around it.
"""

import logging
import tempfile
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from scpi_control.report_generator.analysis.comparison_analyzer import ComparisonAnalysisError, ComparisonAnalyzer
from scpi_control.report_generator.comparison_report_builder import build_comparison_report
from scpi_control.report_generator.models.comparison import MODE_BATCH, MODE_COMPARISON, Run, RunMetadata, RunSet
from scpi_control.report_generator.models.report_data import ReportMetadata
from scpi_control.report_generator.models.template import ReportTemplate

logger = logging.getLogger(__name__)

try:  # Qt only needed for the dialog, not the model
    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import (
        QAbstractItemView,
        QApplication,
        QCheckBox,
        QComboBox,
        QDialog,
        QFileDialog,
        QGroupBox,
        QHBoxLayout,
        QHeaderView,
        QLabel,
        QLineEdit,
        QMessageBox,
        QProgressDialog,
        QPushButton,
        QRadioButton,
        QTableWidget,
        QTableWidgetItem,
        QVBoxLayout,
    )

    QT_AVAILABLE = True
except ImportError:  # pragma: no cover - exercised only when PyQt6 is absent
    QT_AVAILABLE = False


class ComparisonRunTableModel:
    """Backing store for the dialog's run table."""

    def __init__(self):
        self._runs: List[Run] = []

    def add_run(self, label: str, files: List[Path], dut_id: Optional[str] = None) -> None:
        self._runs.append(Run(label=label, files=list(files), metadata=RunMetadata(dut_id=dut_id)))

    def remove_run(self, index: int) -> None:
        del self._runs[index]

    def runs(self) -> List[Run]:
        return list(self._runs)

    def validate(self) -> List[str]:
        errors: List[str] = []
        if len(self._runs) < 2:
            errors.append("Add at least 2 runs")
        labels = [r.label.strip() for r in self._runs]
        if any(not label for label in labels):
            errors.append("Every run needs a non-empty label")
        if len(set(labels)) != len(labels):
            errors.append("Run labels must be unique")
        for run in self._runs:
            if not run.files:
                errors.append(f"Run '{run.label}' has no files")
        return errors

    def to_runset(self, mode: str, baseline_index: int = 0, criteria_set=None) -> RunSet:
        return RunSet(runs=self.runs(), mode=mode, baseline_index=baseline_index, criteria_set=criteria_set)


if QT_AVAILABLE:

    class ComparisonReportDialog(QDialog):
        """Assemble a RunSet from saved capture files and generate a comparison/batch report."""

        # Same filter string as MainWindow._import_waveforms (main_window.py:277)
        WAVEFORM_FILE_FILTER = "Waveform Files (*.npz *.csv *.mat *.h5 *.hdf5);;All Files (*)"

        def __init__(self, parent=None):
            super().__init__(parent)
            self.parent_window = parent
            self.model = ComparisonRunTableModel()

            self.setWindowTitle("Comparison / Batch Report")
            self.setModal(True)
            self.resize(800, 600)

            self._setup_ui()
            self._refresh_table()
            self._refresh_baseline_combo()

        def _setup_ui(self):
            layout = QVBoxLayout()

            # Run table
            table_group = QGroupBox("Runs")
            table_layout = QVBoxLayout()

            self.run_table = QTableWidget(0, 4)
            self.run_table.setHorizontalHeaderLabels(["Label", "DUT ID", "Files", "Remove"])
            self.run_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
            self.run_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
            table_layout.addWidget(self.run_table)

            add_run_btn = QPushButton("Add Run...")
            add_run_btn.clicked.connect(self._add_run)
            table_layout.addWidget(add_run_btn)

            table_group.setLayout(table_layout)
            layout.addWidget(table_group)

            # Mode selection
            mode_group = QGroupBox("Mode")
            mode_layout = QHBoxLayout()
            self.comparison_radio = QRadioButton("Comparison")
            self.comparison_radio.setChecked(True)
            self.comparison_radio.toggled.connect(self._on_mode_changed)
            self.batch_radio = QRadioButton("Batch")
            mode_layout.addWidget(self.comparison_radio)
            mode_layout.addWidget(self.batch_radio)
            mode_group.setLayout(mode_layout)
            layout.addWidget(mode_group)

            # Baseline selection (comparison mode only)
            baseline_layout = QHBoxLayout()
            self.baseline_label = QLabel("Baseline run:")
            baseline_layout.addWidget(self.baseline_label)
            self.baseline_combo = QComboBox()
            baseline_layout.addWidget(self.baseline_combo)
            layout.addLayout(baseline_layout)

            # Template selection
            template_layout = QHBoxLayout()
            template_layout.addWidget(QLabel("Template:"))
            self.template_combo = QComboBox()
            self.template_combo.addItem("(none)")
            for name in ReportTemplate.list_templates():
                self.template_combo.addItem(name)
            self.template_combo.currentIndexChanged.connect(self._on_template_selected)
            template_layout.addWidget(self.template_combo)
            layout.addLayout(template_layout)

            # Report metadata
            metadata_layout = QHBoxLayout()
            metadata_layout.addWidget(QLabel("Title:"))
            self.title_edit = QLineEdit("Comparison Report")
            metadata_layout.addWidget(self.title_edit)
            metadata_layout.addWidget(QLabel("Technician:"))
            self.technician_edit = QLineEdit()
            metadata_layout.addWidget(self.technician_edit)
            layout.addLayout(metadata_layout)

            # Options
            options_layout = QHBoxLayout()
            self.include_appendix_check = QCheckBox("Include raw-data appendix")
            self.include_appendix_check.setChecked(True)
            options_layout.addWidget(self.include_appendix_check)
            self.include_signoff_check = QCheckBox("Include sign-off block")
            self.include_signoff_check.setChecked(True)
            options_layout.addWidget(self.include_signoff_check)
            layout.addLayout(options_layout)

            # Generate buttons
            generate_layout = QHBoxLayout()
            self.generate_pdf_btn = QPushButton("Generate PDF")
            self.generate_pdf_btn.clicked.connect(self._generate_pdf)
            generate_layout.addWidget(self.generate_pdf_btn)

            self.generate_md_btn = QPushButton("Generate Markdown")
            self.generate_md_btn.clicked.connect(self._generate_markdown)
            generate_layout.addWidget(self.generate_md_btn)

            close_btn = QPushButton("Close")
            close_btn.clicked.connect(self.reject)
            generate_layout.addWidget(close_btn)

            layout.addLayout(generate_layout)

            self.setLayout(layout)
            self._on_mode_changed()

        def _on_mode_changed(self):
            is_comparison = self.comparison_radio.isChecked()
            self.baseline_label.setVisible(is_comparison)
            self.baseline_combo.setVisible(is_comparison)

        def _on_template_selected(self):
            name = self.template_combo.currentText()
            if name == "(none)":
                return
            try:
                template = ReportTemplate.load_from_library(name)
            except Exception as e:
                QMessageBox.warning(self, "Template Error", f"Failed to load template '{name}':\n{str(e)}")
                return
            self.include_appendix_check.setChecked(template.include_raw_data_appendix)
            self.include_signoff_check.setChecked(template.include_signoff)

        def _add_run(self):
            file_paths, _ = QFileDialog.getOpenFileNames(
                self,
                "Add Run Files",
                "",
                self.WAVEFORM_FILE_FILTER,
            )
            if not file_paths:
                return

            label = f"Run {len(self.model.runs()) + 1}"
            self.model.add_run(label, [Path(p) for p in file_paths])
            self._refresh_table()
            self._refresh_baseline_combo()

        def _remove_run(self, index: int):
            self.model.remove_run(index)
            self._refresh_table()
            self._refresh_baseline_combo()

        def _refresh_table(self):
            runs = self.model.runs()
            self.run_table.setRowCount(len(runs))
            for row, run in enumerate(runs):
                label_item = QTableWidgetItem(run.label)
                self.run_table.setItem(row, 0, label_item)

                dut_item = QTableWidgetItem(run.metadata.dut_id or "")
                self.run_table.setItem(row, 1, dut_item)

                files_item = QTableWidgetItem(str(len(run.files)))
                files_item.setFlags(files_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.run_table.setItem(row, 2, files_item)

                remove_btn = QPushButton("Remove")
                remove_btn.clicked.connect(lambda _checked=False, i=row: self._remove_run(i))
                self.run_table.setCellWidget(row, 3, remove_btn)

            self._sync_model_from_table()

        def _sync_model_from_table(self):
            """Pull edited labels/DUT IDs from the table back into the model."""
            runs = self.model.runs()
            for row, run in enumerate(runs):
                label_item = self.run_table.item(row, 0)
                dut_item = self.run_table.item(row, 1)
                if label_item is not None:
                    run.label = label_item.text()
                if dut_item is not None:
                    run.metadata.dut_id = dut_item.text() or None

        def _refresh_baseline_combo(self):
            self._sync_model_from_table()
            current = self.baseline_combo.currentIndex()
            self.baseline_combo.blockSignals(True)
            self.baseline_combo.clear()
            for run in self.model.runs():
                self.baseline_combo.addItem(run.label)
            if 0 <= current < self.baseline_combo.count():
                self.baseline_combo.setCurrentIndex(current)
            self.baseline_combo.blockSignals(False)

        def _build_runset(self) -> Optional[RunSet]:
            self._sync_model_from_table()
            errors = self.model.validate()
            if errors:
                QMessageBox.warning(self, "Cannot Generate Report", "\n".join(errors))
                return None

            mode = MODE_COMPARISON if self.comparison_radio.isChecked() else MODE_BATCH
            baseline_index = max(self.baseline_combo.currentIndex(), 0)
            return self.model.to_runset(mode, baseline_index=baseline_index)

        def _selected_template(self) -> Optional[ReportTemplate]:
            name = self.template_combo.currentText()
            if name == "(none)":
                return None
            try:
                return ReportTemplate.load_from_library(name)
            except Exception:
                return None

        def _build_report(self):
            """Validate, analyze, and build a TestReport, or None on error (dialog shown)."""
            runset = self._build_runset()
            if runset is None:
                return None

            try:
                result = ComparisonAnalyzer.analyze(runset)
            except ComparisonAnalysisError as e:
                QMessageBox.critical(self, "Analysis Error", str(e))
                return None

            template = self._selected_template()
            metadata = ReportMetadata(
                title=self.title_edit.text() or "Comparison Report",
                technician=self.technician_edit.text(),
                test_date=datetime.now(),
            )
            report = build_comparison_report(
                result,
                metadata,
                template,
                include_appendix=self.include_appendix_check.isChecked(),
                include_signoff=self.include_signoff_check.isChecked(),
            )
            return report

        def _generate_pdf(self):
            if self.parent_window is None:
                QMessageBox.warning(self, "Cannot Generate", "No parent window available to save the report.")
                return

            report = self._build_report()
            if report is None:
                return

            try:
                from reportlab.lib.pagesizes import A4, letter

                from scpi_control.report_generator.generators.pdf_generator import PDFReportGenerator
            except ImportError:
                QMessageBox.warning(self, "PDF Unavailable", "reportlab package not installed.")
                return

            page_size = A4 if self.parent_window.current_options.page_size == "a4" else letter

            temp_pdf_fd, temp_pdf_path = tempfile.mkstemp(suffix=".pdf")
            import os

            os.close(temp_pdf_fd)
            temp_pdf_path = Path(temp_pdf_path)

            progress = QProgressDialog("Generating PDF report...", None, 0, 100, self)
            progress.setWindowModality(Qt.WindowModality.WindowModal)
            progress.setMinimumDuration(0)
            progress.setAutoClose(True)
            progress.setAutoReset(False)
            progress.show()
            QApplication.processEvents()

            def update_progress(percent: int, message: str):
                progress.setValue(percent)
                progress.setLabelText(f"Generating PDF... {percent}%\n{message}" if message else f"Generating PDF... {percent}%")
                QApplication.processEvents()

            try:
                generator = PDFReportGenerator(
                    page_size=page_size,
                    report_options=self.parent_window.current_options,
                    progress_callback=update_progress,
                )
                success = generator.generate(report, temp_pdf_path)
                progress.close()

                if not success or not temp_pdf_path.exists() or temp_pdf_path.stat().st_size == 0:
                    QMessageBox.warning(self, "Generation Failed", "Failed to generate PDF report.")
                    self.parent_window._safe_delete_temp_file(temp_pdf_path)
                    return

                target_path, _ = QFileDialog.getSaveFileName(
                    self,
                    "Save PDF Report",
                    f"comparison_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
                    "PDF Files (*.pdf)",
                )
                if target_path:
                    self.parent_window._save_final_pdf(temp_pdf_path, Path(target_path))
                self.parent_window._safe_delete_temp_file(temp_pdf_path)

            except Exception as e:
                progress.close()
                self.parent_window._safe_delete_temp_file(temp_pdf_path)
                logger.exception("Comparison PDF generation error")
                QMessageBox.critical(self, "Generation Error", f"Error generating PDF:\n{str(e)}")

        def _generate_markdown(self):
            if self.parent_window is None:
                QMessageBox.warning(self, "Cannot Generate", "No parent window available to save the report.")
                return

            report = self._build_report()
            if report is None:
                return

            target_path, _ = QFileDialog.getSaveFileName(
                self,
                "Save Markdown Report",
                f"comparison_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md",
                "Markdown Files (*.md)",
            )
            if not target_path:
                return

            from scpi_control.report_generator.models.plot_style import PlotStyle

            self.parent_window._save_as_markdown(report, Path(target_path), PlotStyle())
