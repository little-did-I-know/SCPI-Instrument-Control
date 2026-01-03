"""
Main window for the Report Generator application.

Provides the main user interface for importing data, configuring reports,
and generating PDF/Markdown output.
"""

from PyQt6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QSplitter,
    QPushButton,
    QLabel,
    QListWidget,
    QGroupBox,
    QFileDialog,
    QMessageBox,
    QMenuBar,
    QScrollArea,
    QProgressDialog,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction
from pathlib import Path
from typing import List, Optional
from datetime import datetime

from siglent.report_generator.models.report_data import (
    TestReport,
    TestSection,
    WaveformData,
)
from siglent.report_generator.models.template import ReportTemplate
from siglent.report_generator.utils.waveform_loader import WaveformLoader
from siglent.report_generator.generators.markdown_generator import MarkdownReportGenerator

try:
    from siglent.report_generator.generators.pdf_generator import PDFReportGenerator
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False

from siglent.report_generator.llm.client import LLMClient, LLMConfig
from siglent.report_generator.widgets.metadata_panel import MetadataPanel
from siglent.report_generator.widgets.llm_settings_dialog import LLMSettingsDialog
from siglent.report_generator.widgets.chat_sidebar import ChatSidebar


class MainWindow(QMainWindow):
    """Main application window."""

    def __init__(self):
        super().__init__()

        self.waveforms: List[WaveformData] = []
        self.current_report: Optional[TestReport] = None
        self.llm_config: Optional[LLMConfig] = None
        self.llm_client: Optional[LLMClient] = None

        self.setWindowTitle("Siglent Report Generator")
        self.resize(1400, 900)

        self._setup_ui()
        self._setup_menu()

    def _setup_ui(self):
        """Set up the user interface."""
        # Central widget with splitter
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QHBoxLayout()

        # Main content splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left panel: Data import and configuration
        left_panel = self._create_left_panel()
        splitter.addWidget(left_panel)

        # Right panel: Chat sidebar
        self.chat_sidebar = ChatSidebar()
        splitter.addWidget(self.chat_sidebar)

        # Set initial sizes (70% left, 30% right)
        splitter.setSizes([1000, 400])

        main_layout.addWidget(splitter)
        central_widget.setLayout(main_layout)

        # Status bar
        self.statusBar().showMessage("Ready")

    def _create_left_panel(self) -> QWidget:
        """Create the left panel with data import and configuration."""
        panel = QWidget()
        layout = QVBoxLayout()

        # Data import section
        import_group = QGroupBox("Data Import")
        import_layout = QVBoxLayout()

        # Waveform list
        self.waveform_list = QListWidget()
        import_layout.addWidget(QLabel("Imported Waveforms:"))
        import_layout.addWidget(self.waveform_list)

        # Import buttons
        btn_layout = QHBoxLayout()

        import_waveform_btn = QPushButton("Import Waveforms...")
        import_waveform_btn.clicked.connect(self._import_waveforms)
        btn_layout.addWidget(import_waveform_btn)

        import_image_btn = QPushButton("Import Images...")
        import_image_btn.clicked.connect(self._import_images)
        btn_layout.addWidget(import_image_btn)

        clear_btn = QPushButton("Clear All")
        clear_btn.clicked.connect(self._clear_data)
        btn_layout.addWidget(clear_btn)

        import_layout.addLayout(btn_layout)
        import_group.setLayout(import_layout)
        layout.addWidget(import_group)

        # Metadata section (scrollable)
        metadata_scroll = QScrollArea()
        metadata_scroll.setWidgetResizable(True)
        metadata_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.metadata_panel = MetadataPanel()
        metadata_scroll.setWidget(self.metadata_panel)

        layout.addWidget(QLabel("Report Metadata:"))
        layout.addWidget(metadata_scroll)

        # Report generation buttons
        generate_layout = QHBoxLayout()

        self.generate_pdf_btn = QPushButton("Generate PDF Report")
        self.generate_pdf_btn.clicked.connect(self._generate_pdf)
        self.generate_pdf_btn.setEnabled(PDF_AVAILABLE)
        if not PDF_AVAILABLE:
            self.generate_pdf_btn.setToolTip("reportlab package not installed")
        generate_layout.addWidget(self.generate_pdf_btn)

        self.generate_md_btn = QPushButton("Generate Markdown Report")
        self.generate_md_btn.clicked.connect(self._generate_markdown)
        generate_layout.addWidget(self.generate_md_btn)

        layout.addLayout(generate_layout)

        panel.setLayout(layout)
        return panel

    def _setup_menu(self):
        """Set up the menu bar."""
        menubar = self.menuBar()

        # File menu
        file_menu = menubar.addMenu("&File")

        new_action = QAction("&New Report", self)
        new_action.setShortcut("Ctrl+N")
        new_action.triggered.connect(self._new_report)
        file_menu.addAction(new_action)

        file_menu.addSeparator()

        exit_action = QAction("E&xit", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # Settings menu
        settings_menu = menubar.addMenu("&Settings")

        llm_action = QAction("&LLM Configuration...", self)
        llm_action.triggered.connect(self._configure_llm)
        settings_menu.addAction(llm_action)

        # Help menu
        help_menu = menubar.addMenu("&Help")

        about_action = QAction("&About", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

    def _import_waveforms(self):
        """Import waveform files."""
        file_paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Import Waveforms",
            "",
            "Waveform Files (*.npz *.csv *.mat *.h5 *.hdf5);;All Files (*)",
        )

        if not file_paths:
            return

        try:
            for file_path in file_paths:
                waveforms = WaveformLoader.load(Path(file_path))
                self.waveforms.extend(waveforms)

                # Add to list
                for waveform in waveforms:
                    self.waveform_list.addItem(
                        f"{waveform.label} - {Path(file_path).name}"
                    )

            self.statusBar().showMessage(f"Imported {len(file_paths)} waveform file(s)")

        except Exception as e:
            QMessageBox.critical(
                self,
                "Import Error",
                f"Failed to import waveforms:\n{str(e)}",
            )

    def _import_images(self):
        """Import image files."""
        file_paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Import Images",
            "",
            "Images (*.png *.jpg *.jpeg *.bmp);;All Files (*)",
        )

        if file_paths:
            # TODO: Store images for inclusion in report
            self.statusBar().showMessage(f"Imported {len(file_paths)} image(s)")

    def _clear_data(self):
        """Clear all imported data."""
        reply = QMessageBox.question(
            self,
            "Clear Data",
            "Clear all imported waveforms and data?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            self.waveforms.clear()
            self.waveform_list.clear()
            self.statusBar().showMessage("Data cleared")

    def _configure_llm(self):
        """Open LLM configuration dialog."""
        dialog = LLMSettingsDialog(self.llm_config, self)
        dialog.settings_saved.connect(self._on_llm_configured)

        if dialog.exec():
            self.statusBar().showMessage("LLM configuration saved")

    def _on_llm_configured(self, config: LLMConfig):
        """Handle LLM configuration update."""
        self.llm_config = config
        self.llm_client = LLMClient(config)
        self.chat_sidebar.set_llm_client(self.llm_client)

    def _generate_pdf(self):
        """Generate PDF report."""
        if not self._validate_report_data():
            return

        # Get save location
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save PDF Report",
            f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
            "PDF Files (*.pdf)",
        )

        if not file_path:
            return

        try:
            # Build report
            report = self._build_report()

            # Generate PDF
            progress = QProgressDialog("Generating PDF report...", None, 0, 0, self)
            progress.setWindowModality(Qt.WindowModality.WindowModal)
            progress.show()

            generator = PDFReportGenerator()
            success = generator.generate(report, Path(file_path))

            progress.close()

            if success:
                QMessageBox.information(
                    self,
                    "Report Generated",
                    f"PDF report saved to:\n{file_path}",
                )
                self.statusBar().showMessage(f"PDF report saved: {file_path}")
            else:
                QMessageBox.warning(
                    self,
                    "Generation Failed",
                    "Failed to generate PDF report.",
                )

        except Exception as e:
            QMessageBox.critical(
                self,
                "Generation Error",
                f"Error generating PDF:\n{str(e)}",
            )

    def _generate_markdown(self):
        """Generate Markdown report."""
        if not self._validate_report_data():
            return

        # Get save location
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Markdown Report",
            f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md",
            "Markdown Files (*.md)",
        )

        if not file_path:
            return

        try:
            # Build report
            report = self._build_report()

            # Generate Markdown
            progress = QProgressDialog("Generating Markdown report...", None, 0, 0, self)
            progress.setWindowModality(Qt.WindowModality.WindowModal)
            progress.show()

            generator = MarkdownReportGenerator()
            success = generator.generate(report, Path(file_path))

            progress.close()

            if success:
                QMessageBox.information(
                    self,
                    "Report Generated",
                    f"Markdown report saved to:\n{file_path}",
                )
                self.statusBar().showMessage(f"Markdown report saved: {file_path}")
            else:
                QMessageBox.warning(
                    self,
                    "Generation Failed",
                    "Failed to generate Markdown report.",
                )

        except Exception as e:
            QMessageBox.critical(
                self,
                "Generation Error",
                f"Error generating Markdown:\n{str(e)}",
            )

    def _build_report(self) -> TestReport:
        """Build a test report from current data."""
        metadata = self.metadata_panel.get_metadata()

        report = TestReport(metadata=metadata)

        # Create waveform section
        if self.waveforms:
            section = TestSection(
                title="Waveform Captures",
                content="Captured waveforms and analysis.",
                waveforms=self.waveforms,
                order=1,
            )
            report.add_section(section)

        # Update chat sidebar with report
        self.current_report = report
        self.chat_sidebar.set_report(report)

        return report

    def _validate_report_data(self) -> bool:
        """Validate that we have minimum data for a report."""
        metadata = self.metadata_panel.get_metadata()

        if not metadata.title:
            QMessageBox.warning(
                self,
                "Missing Information",
                "Please enter a report title.",
            )
            return False

        if not metadata.technician:
            QMessageBox.warning(
                self,
                "Missing Information",
                "Please enter technician name.",
            )
            return False

        if not self.waveforms:
            reply = QMessageBox.question(
                self,
                "No Waveforms",
                "No waveforms imported. Continue anyway?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.No:
                return False

        return True

    def _new_report(self):
        """Start a new report."""
        reply = QMessageBox.question(
            self,
            "New Report",
            "Clear current data and start a new report?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            self._clear_data()
            self.metadata_panel.clear_form()
            self.chat_sidebar._clear_chat()
            self.statusBar().showMessage("New report started")

    def _show_about(self):
        """Show about dialog."""
        QMessageBox.about(
            self,
            "About Siglent Report Generator",
            "<h2>Siglent Report Generator</h2>"
            "<p>Generate professional test reports from oscilloscope data.</p>"
            "<p><b>Features:</b></p>"
            "<ul>"
            "<li>Import waveforms from NPZ, CSV, MAT, HDF5 files</li>"
            "<li>Generate PDF and Markdown reports</li>"
            "<li>AI-powered analysis with local LLM support</li>"
            "<li>Interactive chat for data insights</li>"
            "</ul>"
            "<p>Part of the <b>Siglent Oscilloscope Control</b> project.</p>",
        )
