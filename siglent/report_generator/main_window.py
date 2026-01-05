"""
Main window for the Report Generator application.

Provides the main user interface for importing data, configuring reports,
and generating PDF/Markdown output.
"""

import platform
import shutil
import tempfile
import time
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import (
    QApplication,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMainWindow,
    QMenuBar,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QScrollArea,
    QSplitter,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from siglent.report_generator.generators.markdown_generator import MarkdownReportGenerator
from siglent.report_generator.models.app_settings import AppSettings
from siglent.report_generator.models.plot_style import PlotStyle
from siglent.report_generator.models.report_data import TestReport, TestSection, WaveformData
from siglent.report_generator.models.report_options import ReportOptions
from siglent.report_generator.models.template import ReportTemplate
from siglent.report_generator.utils.waveform_loader import WaveformLoader

try:
    from siglent.report_generator.generators.pdf_generator import PDFReportGenerator

    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False

from siglent.report_generator.llm.client import LLMClient, LLMConfig
from siglent.report_generator.widgets.ai_analysis_panel import AIAnalysisPanel
from siglent.report_generator.widgets.chat_sidebar import ChatSidebar
from siglent.report_generator.widgets.llm_settings_dialog import LLMSettingsDialog
from siglent.report_generator.widgets.metadata_panel import MetadataPanel
from siglent.report_generator.widgets.pdf_preview_dialog import PDFPreviewDialog
from siglent.report_generator.widgets.report_options_dialog import ReportOptionsDialog
from siglent.report_generator.widgets.template_manager_dialog import TemplateManagerDialog


class MainWindow(QMainWindow):
    """Main application window."""

    def __init__(self):
        super().__init__()

        self.waveforms: List[WaveformData] = []
        self.current_report: Optional[TestReport] = None
        self.llm_config: Optional[LLMConfig] = None
        self.llm_client: Optional[LLMClient] = None

        # Template and options management
        self.current_options: ReportOptions = ReportOptions()
        self.current_template: Optional[ReportTemplate] = None
        self.app_settings: AppSettings = AppSettings.load()

        # Apply saved settings from previous session
        if self.app_settings.last_options:
            self.current_options = self.app_settings.last_options
        if self.app_settings.last_used_template:
            try:
                self.current_template = ReportTemplate.load_from_library(self.app_settings.last_used_template)
            except Exception:
                # Template may have been deleted, ignore
                pass

        self.setWindowTitle("Siglent Report Generator")
        self.resize(1400, 900)

        self._setup_ui()
        self._setup_menu()

    def _safe_delete_temp_file(self, temp_path: Path, max_retries: int = 10):
        """
        Safely delete temporary file with retry logic for Windows.

        Args:
            temp_path: Path to temporary file
            max_retries: Maximum number of deletion attempts
        """
        for attempt in range(max_retries):
            try:
                temp_path.unlink(missing_ok=True)
                if attempt > 0:
                    print(f"Successfully deleted temp file after {attempt + 1} attempts")
                return  # Success
            except PermissionError:
                if attempt < max_retries - 1:
                    # On Windows, file may still be locked by PDF viewer (especially QWebEngineView)
                    # Wait a bit and retry with exponential backoff
                    delay = 0.2 * (2 ** min(attempt, 4))  # 0.2, 0.4, 0.8, 1.6, 3.2s max
                    time.sleep(delay)
                else:
                    # Last attempt failed, log but don't crash
                    print(f"Warning: Could not delete temp file {temp_path} after {max_retries} attempts")
                    print(f"The file will be cleaned up when you close the application or by system temp cleanup")
            except Exception as e:
                print(f"Warning: Error deleting temp file: {e}")
                break

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

        # Right panel: Tabbed interface for AI Analysis and Chat
        right_panel = QTabWidget()

        # AI Analysis tab
        self.ai_analysis_panel = AIAnalysisPanel()
        self.ai_analysis_panel.llm_settings_requested.connect(self._configure_llm)
        self.ai_analysis_panel.report_build_requested.connect(self._build_report_for_ai)
        right_panel.addTab(self.ai_analysis_panel, "AI Analysis")

        # Chat tab
        self.chat_sidebar = ChatSidebar()
        right_panel.addTab(self.chat_sidebar, "Chat")

        splitter.addWidget(right_panel)

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

        # Template actions
        load_template_action = QAction("&Load Template...", self)
        load_template_action.setShortcut("Ctrl+L")
        load_template_action.triggered.connect(self._load_template)
        file_menu.addAction(load_template_action)

        save_template_action = QAction("&Save as Template...", self)
        save_template_action.setShortcut("Ctrl+S")
        save_template_action.triggered.connect(self._save_template)
        file_menu.addAction(save_template_action)

        manage_templates_action = QAction("&Manage Templates...", self)
        manage_templates_action.triggered.connect(self._manage_templates)
        file_menu.addAction(manage_templates_action)

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
                    self.waveform_list.addItem(f"{waveform.label} - {Path(file_path).name}")

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
        self.ai_analysis_panel.set_llm_config(config)

    def _generate_pdf(self):
        """Generate PDF report with preview workflow."""
        if not self._validate_report_data():
            return

        # Loop to allow going back to options from preview
        while True:
            # Show report options dialog
            plot_style = self.current_template.plot_style if self.current_template else PlotStyle()
            dialog = ReportOptionsDialog(self, self.current_options, plot_style)

            if not dialog.exec():
                return  # User cancelled

            # Get options from dialog
            self.current_options = dialog.get_options()
            plot_style = dialog.get_plot_style()

            # Generate PDF to temporary location
            temp_pdf_fd, temp_pdf_path = tempfile.mkstemp(suffix=".pdf")
            import os

            os.close(temp_pdf_fd)  # Close the file descriptor
            temp_pdf_path = Path(temp_pdf_path)

            try:
                # Build report with options
                report = self._build_report()

                # Apply report options (filter sections)
                if not self.current_options.include_executive_summary:
                    report.executive_summary = None
                if not self.current_options.include_key_findings:
                    report.key_findings = []
                if not self.current_options.include_recommendations:
                    report.recommendations = []

                # Generate PDF to temp location
                from reportlab.lib.pagesizes import A4, letter

                page_size = A4 if self.current_options.page_size == "a4" else letter

                print(f"\n=== PDF Generation Debug ===")
                print(f"Temp PDF path: {temp_pdf_path}")
                print(f"Report title: {report.metadata.title}")
                print(f"Sections: {len(report.sections)}")
                print(f"Waveforms: {sum(len(s.waveforms) for s in report.sections)}")
                print(f"Page size: {self.current_options.page_size}")

                # Create progress dialog with proper range
                progress = QProgressDialog("Starting PDF generation...", None, 0, 100, self)
                progress.setWindowModality(Qt.WindowModality.WindowModal)
                progress.setMinimumDuration(0)  # Show immediately
                progress.setAutoClose(True)
                progress.setAutoReset(False)
                progress.show()
                QApplication.processEvents()  # Force show

                # Progress callback to update the dialog
                def update_progress(percent: int, message: str):
                    progress.setValue(percent)
                    if message:
                        progress.setLabelText(f"Generating PDF... {percent}%\n{message}")
                    else:
                        progress.setLabelText(f"Generating PDF... {percent}%")
                    QApplication.processEvents()  # Keep UI responsive

                generator = PDFReportGenerator(
                    page_size=page_size,
                    include_plots=self.current_options.include_waveform_plots,
                    plot_width=self.current_options.plot_width_inches,
                    plot_height=self.current_options.plot_height_inches,
                    plot_style=plot_style,
                    report_options=self.current_options,
                    progress_callback=update_progress,
                )

                print(f"Calling generator.generate()...")
                success = generator.generate(report, temp_pdf_path)
                print(f"Generation success: {success}")

                progress.close()

                if not success:
                    QMessageBox.warning(self, "Generation Failed", "Failed to generate PDF report.")
                    self._safe_delete_temp_file(temp_pdf_path)
                    return

                # Verify PDF was actually created and has content
                if not temp_pdf_path.exists():
                    print(f"ERROR: PDF file does not exist after generation!")
                    QMessageBox.critical(self, "Generation Failed", f"PDF file was not created.\n\nExpected location: {temp_pdf_path}")
                    self._safe_delete_temp_file(temp_pdf_path)
                    return

                file_size = temp_pdf_path.stat().st_size
                print(f"PDF file size: {file_size} bytes")

                if file_size == 0:
                    QMessageBox.critical(self, "Generation Failed", f"PDF file is empty (0 bytes).\n\nCheck that waveforms are loaded and report data is valid.")
                    self._safe_delete_temp_file(temp_pdf_path)
                    return

                # Check PDF header
                try:
                    with open(temp_pdf_path, "rb") as f:
                        header = f.read(10)
                        print(f"PDF header: {header}")
                except Exception as e:
                    print(f"ERROR reading PDF: {e}")

                print(f"=== End Debug ===\n")

                # Show preview dialog
                preview_dialog = PDFPreviewDialog(temp_pdf_path, self)

                # Connect signals
                preview_dialog.save_pdf_requested.connect(lambda path: self._save_final_pdf(temp_pdf_path, path))
                preview_dialog.save_markdown_requested.connect(lambda path: self._save_as_markdown(report, path, plot_style))

                result = preview_dialog.exec()

                # Process any pending events to ensure cleanup
                QApplication.processEvents()

                # Check if user wants to edit options (go back to options dialog)
                if preview_dialog._edit_options_clicked:
                    self._safe_delete_temp_file(temp_pdf_path)
                    continue  # Loop back to show options dialog again

                # Otherwise, we're done
                self._safe_delete_temp_file(temp_pdf_path)
                break

            except Exception as e:
                self._safe_delete_temp_file(temp_pdf_path)
                import traceback

                error_details = traceback.format_exc()
                print(f"PDF Generation Error:\n{error_details}")
                QMessageBox.critical(
                    self,
                    "Generation Error",
                    f"Error generating PDF:\n{str(e)}\n\nCheck console for full traceback.",
                )
                return

    def _save_final_pdf(self, temp_pdf_path: Path, target_path: Path):
        """
        Copy temporary PDF to final location.

        Args:
            temp_pdf_path: Path to temporary PDF file
            target_path: User-selected destination path
        """
        try:
            shutil.copy2(temp_pdf_path, target_path)
            QMessageBox.information(
                self,
                "PDF Saved",
                f"PDF report saved to:\n{target_path}",
            )
            self.statusBar().showMessage(f"PDF report saved: {target_path}")
        except Exception as e:
            QMessageBox.critical(
                self,
                "Save Error",
                f"Failed to save PDF:\n{str(e)}",
            )

    def _save_as_markdown(self, report: TestReport, target_path: Path, plot_style: PlotStyle):
        """
        Generate and save markdown version of the report.

        Args:
            report: The test report to generate
            target_path: User-selected destination path
            plot_style: Plot styling configuration
        """
        try:
            generator = MarkdownReportGenerator(
                include_plots=self.current_options.include_waveform_plots,
                plot_style=plot_style,
            )
            success = generator.generate(report, target_path)

            if success:
                QMessageBox.information(
                    self,
                    "Markdown Saved",
                    f"Markdown report saved to:\n{target_path}",
                )
                self.statusBar().showMessage(f"Markdown report saved: {target_path}")
            else:
                QMessageBox.warning(self, "Generation Failed", "Failed to generate Markdown report.")

        except Exception as e:
            QMessageBox.critical(
                self,
                "Generation Error",
                f"Error generating Markdown:\n{str(e)}",
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

    def _build_report_for_ai(self):
        """Build report for AI analysis and trigger generation."""
        try:
            # Build the report
            report = self._build_report()

            # Set it on the AI panel
            self.ai_analysis_panel.set_report(report)

            # Continue with generation using the newly built report
            QTimer.singleShot(100, self.ai_analysis_panel._continue_generation)

        except Exception as e:
            QMessageBox.warning(self, "Cannot Build Report", f"Failed to build report from current data:\n{str(e)}\n\n" "Please ensure you have imported waveforms and filled in metadata.")

    def _build_report(self) -> TestReport:
        """Build a test report from current data."""
        metadata = self.metadata_panel.get_metadata()

        # Debug: Print test type being used
        print(f"[DEBUG _build_report] Building report with test type: {metadata.test_type}")

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

        # Add AI-generated content if available
        if self.ai_analysis_panel.has_generated_content():
            ai_content = self.ai_analysis_panel.get_generated_content()

            if ai_content.get("executive_summary"):
                report.executive_summary = ai_content["executive_summary"]
                report.ai_generated_summary = True

            if ai_content.get("key_findings"):
                report.key_findings = ai_content["key_findings"]

            if ai_content.get("recommendations"):
                report.recommendations = ai_content["recommendations"]

        # Update chat sidebar and AI panel with report
        self.current_report = report
        self.chat_sidebar.set_report(report)
        self.ai_analysis_panel.set_report(report)

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
            "<li>Customizable report templates</li>"
            "</ul>"
            "<p>Part of the <b>Siglent Oscilloscope Control</b> project.</p>",
        )

    def _load_template(self):
        """Open template manager to load a template."""
        dialog = TemplateManagerDialog(self)
        dialog.template_selected.connect(self._on_template_loaded)
        dialog.exec()

    def _on_template_loaded(self, template: ReportTemplate):
        """
        Apply loaded template to current session.

        Args:
            template: Template to apply
        """
        self.current_template = template

        # Apply template defaults to metadata panel
        if template.default_test_type:
            # Set test type in combo box
            index = self.metadata_panel.test_type_combo.findData(template.default_test_type)
            if index >= 0:
                self.metadata_panel.test_type_combo.setCurrentIndex(index)
        if template.default_company_name:
            self.metadata_panel.company_name_edit.setText(template.default_company_name)
        if template.default_technician:
            self.metadata_panel.technician_edit.setText(template.default_technician)
        if template.default_temperature:
            self.metadata_panel.temperature_edit.setText(template.default_temperature)
        if template.default_humidity:
            self.metadata_panel.humidity_edit.setText(template.default_humidity)
        if template.default_location:
            self.metadata_panel.location_edit.setText(template.default_location)

        # Update current options from template
        self.current_options.include_executive_summary = template.include_executive_summary
        self.current_options.include_key_findings = template.include_key_findings
        self.current_options.include_recommendations = template.include_recommendations
        self.current_options.include_waveform_plots = template.include_waveform_plots
        self.current_options.include_fft_analysis = template.include_fft_analysis

        self.current_options.auto_generate_summary = template.auto_generate_summary
        self.current_options.auto_generate_findings = template.auto_generate_findings
        self.current_options.auto_generate_recommendations = template.auto_generate_recommendations

        self.current_options.page_size = template.page_size
        self.current_options.plot_width_inches = template.plot_width_inches
        self.current_options.plot_height_inches = template.plot_height_inches
        self.current_options.plot_dpi = template.plot_dpi

        self.statusBar().showMessage(f"Loaded template: {template.name}")

    def _save_template(self):
        """Save current configuration as a template."""
        from PyQt6.QtWidgets import QInputDialog

        # Get template name
        name, ok = QInputDialog.getText(
            self,
            "Save Template",
            "Enter template name:",
        )

        if not ok or not name.strip():
            return

        # Get template description
        description, ok = QInputDialog.getText(
            self,
            "Save Template",
            "Enter template description (optional):",
        )

        if not ok:
            return

        try:
            # Get metadata
            metadata = self.metadata_panel.get_metadata()

            # Create template from current state
            template = ReportTemplate(
                name=name.strip(),
                description=description.strip() if description else None,
                include_executive_summary=self.current_options.include_executive_summary,
                include_key_findings=self.current_options.include_key_findings,
                include_recommendations=self.current_options.include_recommendations,
                include_waveform_plots=self.current_options.include_waveform_plots,
                include_fft_analysis=self.current_options.include_fft_analysis,
                auto_generate_summary=self.current_options.auto_generate_summary,
                auto_generate_findings=self.current_options.auto_generate_findings,
                auto_generate_recommendations=self.current_options.auto_generate_recommendations,
                page_size=self.current_options.page_size,
                plot_width_inches=self.current_options.plot_width_inches,
                plot_height_inches=self.current_options.plot_height_inches,
                plot_dpi=self.current_options.plot_dpi,
                plot_style=self.current_template.plot_style if self.current_template else PlotStyle(),
                default_test_type=metadata.test_type,
                default_company_name=metadata.company_name,
                default_technician=metadata.technician,
                default_temperature=metadata.temperature,
                default_humidity=metadata.humidity,
                default_location=metadata.location,
            )

            if self.llm_config:
                template.llm_endpoint = self.llm_config.endpoint
                template.llm_model = self.llm_config.model

            # Save to library
            template.save_to_library()

            QMessageBox.information(
                self,
                "Template Saved",
                f"Template '{name}' saved successfully!",
            )

        except Exception as e:
            QMessageBox.critical(
                self,
                "Error Saving Template",
                f"Failed to save template:\n{str(e)}",
            )

    def _manage_templates(self):
        """Open template management dialog."""
        dialog = TemplateManagerDialog(self)
        dialog.template_selected.connect(self._on_template_loaded)
        dialog.exec()

    def closeEvent(self, event):
        """
        Handle window close event - save settings.

        Args:
            event: Close event
        """
        # Save app settings
        self.app_settings.last_options = self.current_options
        if self.current_template:
            self.app_settings.last_used_template = self.current_template.name
        self.app_settings.save()

        event.accept()
