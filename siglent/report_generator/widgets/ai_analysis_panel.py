"""
AI Analysis Panel for generating and previewing AI content.

Provides a streamlined interface for enabling AI features and generating
analysis before creating the final report.
"""

from typing import Dict, Optional

import markdown
from PyQt6.QtCore import Qt, QThread, QTimer, pyqtSignal
from PyQt6.QtGui import QCursor, QFont
from PyQt6.QtWidgets import QCheckBox, QFrame, QGroupBox, QHBoxLayout, QLabel, QProgressBar, QPushButton, QTabWidget, QTextBrowser, QTextEdit, QVBoxLayout, QWidget

from siglent.report_generator.llm.analyzer import ReportAnalyzer
from siglent.report_generator.llm.client import LLMClient, LLMConfig
from siglent.report_generator.models.report_data import TestReport

# System monitoring
try:
    import psutil

    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

try:
    import warnings

    # Suppress pynvml deprecation warning (nvidia-ml-py is installed)
    warnings.filterwarnings("ignore", category=FutureWarning, module="pynvml")
    import pynvml

    pynvml.nvmlInit()
    GPU_AVAILABLE = True
except Exception:
    GPU_AVAILABLE = False


class AIAnalysisWorker(QThread):
    """Background worker for generating AI analysis."""

    finished = pyqtSignal(dict)  # Emits dict with results
    progress = pyqtSignal(str)  # Progress messages
    error = pyqtSignal(str)  # Error messages

    def __init__(
        self,
        report: TestReport,
        llm_config: LLMConfig,
        generate_summary: bool,
        generate_findings: bool,
        generate_recommendations: bool,
    ):
        super().__init__()
        self.report = report
        self.llm_config = llm_config
        self.generate_summary = generate_summary
        self.generate_findings = generate_findings
        self.generate_recommendations = generate_recommendations

    def run(self):
        """Run AI analysis in background thread."""
        try:
            # Create analyzer
            client = LLMClient(self.llm_config)
            analyzer = ReportAnalyzer(client)

            results = {
                "executive_summary": None,
                "key_findings": [],
                "recommendations": [],
            }

            # Generate executive summary
            if self.generate_summary:
                self.progress.emit("Generating executive summary...")
                summary = analyzer.generate_executive_summary(self.report)
                if summary:
                    results["executive_summary"] = summary
                else:
                    self.error.emit("Failed to generate executive summary")

            # Generate key findings
            if self.generate_findings:
                self.progress.emit("Generating key findings...")
                findings = analyzer.generate_key_findings(self.report)
                if findings:
                    results["key_findings"] = findings
                else:
                    self.error.emit("Failed to generate key findings")

            # Generate recommendations
            if self.generate_recommendations:
                self.progress.emit("Generating recommendations...")
                recommendations = analyzer.generate_recommendations(self.report)
                if recommendations:
                    results["recommendations"] = recommendations
                else:
                    self.error.emit("Failed to generate recommendations")

            self.progress.emit("AI analysis complete!")
            self.finished.emit(results)

        except Exception as e:
            self.error.emit(f"AI analysis error: {str(e)}")
            # Still emit finished with empty results to restore UI
            self.finished.emit(
                {
                    "executive_summary": None,
                    "key_findings": [],
                    "recommendations": [],
                }
            )


class AIAnalysisPanel(QWidget):
    """Panel for AI analysis generation and preview."""

    analysis_generated = pyqtSignal(dict)  # Emits generated AI content
    llm_settings_requested = pyqtSignal()  # Emits when user clicks status to configure LLM
    report_build_requested = pyqtSignal()  # Emits when AI needs a report built

    def __init__(self, parent=None):
        """
        Initialize AI analysis panel.

        Args:
            parent: Parent widget
        """
        super().__init__(parent)

        self.current_report = None
        self.llm_config = None
        self.connection_state = None  # None = not tested, True = connected, False = failed
        self.generated_content = {
            "executive_summary": None,
            "key_findings": [],
            "recommendations": [],
        }
        self.worker = None
        self.errors_occurred = False  # Track if errors occurred during generation

        self._setup_ui()

    def _setup_ui(self):
        """Set up the user interface."""
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)

        # AI Settings Group
        settings_group = QGroupBox("AI Analysis Settings")
        settings_layout = QVBoxLayout()

        # Master enable checkbox
        self.enable_ai_checkbox = QCheckBox("Enable AI Features")
        self.enable_ai_checkbox.setChecked(False)
        self.enable_ai_checkbox.stateChanged.connect(self._on_enable_changed)
        font = QFont()
        font.setBold(True)
        self.enable_ai_checkbox.setFont(font)
        settings_layout.addWidget(self.enable_ai_checkbox)

        # Individual feature checkboxes
        self.summary_checkbox = QCheckBox("Executive Summary")
        self.summary_checkbox.setChecked(True)
        self.summary_checkbox.setEnabled(False)
        settings_layout.addWidget(self.summary_checkbox)

        self.findings_checkbox = QCheckBox("Key Findings")
        self.findings_checkbox.setChecked(True)
        self.findings_checkbox.setEnabled(False)
        settings_layout.addWidget(self.findings_checkbox)

        self.recommendations_checkbox = QCheckBox("Recommendations")
        self.recommendations_checkbox.setChecked(True)
        self.recommendations_checkbox.setEnabled(False)
        settings_layout.addWidget(self.recommendations_checkbox)

        # Generate button
        generate_layout = QHBoxLayout()
        self.generate_button = QPushButton("Generate AI Analysis")
        self.generate_button.setEnabled(False)
        self.generate_button.clicked.connect(self._generate_analysis)
        generate_layout.addWidget(self.generate_button)

        self.clear_button = QPushButton("Clear")
        self.clear_button.setEnabled(False)
        self.clear_button.clicked.connect(self._clear_results)
        generate_layout.addWidget(self.clear_button)

        settings_layout.addLayout(generate_layout)

        # Status label (clickable)
        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)
        self.status_label.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.status_label.setStyleSheet("QLabel { padding: 5px; }")
        self.status_label.mousePressEvent = lambda event: self.llm_settings_requested.emit()
        settings_layout.addWidget(self.status_label)

        # Set initial status
        self._update_status_display()

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(0)  # Indeterminate
        settings_layout.addWidget(self.progress_bar)

        # System monitor (CPU/GPU usage during generation)
        self.monitor_frame = QFrame()
        self.monitor_frame.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Sunken)
        self.monitor_frame.setVisible(False)
        monitor_layout = QHBoxLayout()
        monitor_layout.setContentsMargins(8, 4, 8, 4)

        self.cpu_label = QLabel("CPU: --")
        self.cpu_label.setStyleSheet("font-family: monospace; color: #2196F3;")
        monitor_layout.addWidget(self.cpu_label)

        self.gpu_label = QLabel("GPU: --")
        self.gpu_label.setStyleSheet("font-family: monospace; color: #4CAF50;")
        monitor_layout.addWidget(self.gpu_label)

        monitor_layout.addStretch()

        self.monitor_frame.setLayout(monitor_layout)
        settings_layout.addWidget(self.monitor_frame)

        # Timer for updating system stats
        self.monitor_timer = QTimer()
        self.monitor_timer.timeout.connect(self._update_system_stats)
        self.monitor_timer.setInterval(500)  # Update every 500ms

        settings_group.setLayout(settings_layout)
        layout.addWidget(settings_group)

        # Preview area with tabs
        preview_group = QGroupBox("AI Analysis Preview")
        preview_layout = QVBoxLayout()

        self.preview_tabs = QTabWidget()

        # Executive Summary tab (with markdown rendering)
        self.summary_preview = QTextBrowser()
        self.summary_preview.setOpenExternalLinks(False)
        self.summary_preview.setPlaceholderText("Executive summary will appear here after generation...")
        self.preview_tabs.addTab(self.summary_preview, "Summary")

        # Key Findings tab (with markdown rendering)
        self.findings_preview = QTextBrowser()
        self.findings_preview.setOpenExternalLinks(False)
        self.findings_preview.setPlaceholderText("Key findings will appear here after generation...")
        self.preview_tabs.addTab(self.findings_preview, "Findings")

        # Recommendations tab (with markdown rendering)
        self.recommendations_preview = QTextBrowser()
        self.recommendations_preview.setOpenExternalLinks(False)
        self.recommendations_preview.setPlaceholderText("Recommendations will appear here after generation...")
        self.preview_tabs.addTab(self.recommendations_preview, "Recommendations")

        preview_layout.addWidget(self.preview_tabs)
        preview_group.setLayout(preview_layout)
        layout.addWidget(preview_group)

        self.setLayout(layout)

    def _markdown_to_html(self, text: str) -> str:
        """
        Convert markdown text to HTML.

        Args:
            text: Markdown text

        Returns:
            HTML string
        """
        if not text:
            return ""

        # Convert markdown to HTML
        html = markdown.markdown(text, extensions=["nl2br", "tables", "fenced_code"])

        # Wrap in styled div
        styled_html = f"""
        <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                    font-size: 11pt; line-height: 1.6; color: #333;">
            {html}
        </div>
        """

        return styled_html

    def _update_system_stats(self):
        """Update CPU and GPU usage stats."""
        # Update CPU usage
        if PSUTIL_AVAILABLE:
            try:
                cpu_percent = psutil.cpu_percent(interval=0)
                cpu_count = psutil.cpu_count()
                self.cpu_label.setText(f"CPU: {cpu_percent:5.1f}% ({cpu_count} cores)")
            except Exception as e:
                self.cpu_label.setText("CPU: Error")
        else:
            self.cpu_label.setText("CPU: N/A")

        # Update GPU usage
        if GPU_AVAILABLE:
            try:
                # Get first GPU (index 0)
                handle = pynvml.nvmlDeviceGetHandleByIndex(0)

                # Get utilization rates
                util = pynvml.nvmlDeviceGetUtilizationRates(handle)
                gpu_util = util.gpu
                mem_util = util.memory

                # Get temperature
                try:
                    temp = pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU)
                    temp_str = f" | {temp}°C"
                except:
                    temp_str = ""

                # Get memory info for more accurate memory percentage
                try:
                    mem_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
                    mem_used_gb = mem_info.used / 1024**3
                    mem_total_gb = mem_info.total / 1024**3
                    mem_str = f" | Mem: {mem_util:5.1f}% ({mem_used_gb:.1f}/{mem_total_gb:.1f} GB)"
                except:
                    mem_str = f" | Mem: {mem_util:5.1f}%"

                self.gpu_label.setText(f"GPU: {gpu_util:5.1f}%{mem_str}{temp_str}")

            except pynvml.NVMLError_GpuIsLost:
                self.gpu_label.setText("GPU: Lost/Reset")
            except pynvml.NVMLError_NotSupported:
                self.gpu_label.setText("GPU: Not Supported")
            except Exception as e:
                self.gpu_label.setText(f"GPU: Error - {str(e)[:20]}")
        else:
            self.gpu_label.setText("GPU: N/A")

    def _on_enable_changed(self, state):
        """Handle master enable checkbox change."""
        enabled = state == Qt.CheckState.Checked.value
        self.summary_checkbox.setEnabled(enabled)
        self.findings_checkbox.setEnabled(enabled)
        self.recommendations_checkbox.setEnabled(enabled)
        self._update_generate_button_state()

    def _update_generate_button_state(self):
        """Update generate button enabled state."""
        # Only require AI enabled and LLM configured
        # Report will be built automatically if needed
        can_generate = self.enable_ai_checkbox.isChecked() and self.llm_config is not None
        self.generate_button.setEnabled(can_generate)

    def set_report(self, report: TestReport):
        """
        Set the report to analyze.

        Args:
            report: Test report to analyze
        """
        self.current_report = report
        self._update_generate_button_state()

    def _update_status_display(self):
        """Update the connection status display with colored dot."""
        if not self.llm_config:
            # Red dot - not configured
            status_html = '<span style="color: red; font-size: 16px;">●</span> <b>Not Connected</b> - Click to configure LLM'
            self.status_label.setText(status_html)
            self.status_label.setToolTip("Click to open LLM Settings")
        else:
            # Determine status color based on connection state
            if self.connection_state is None:
                # Yellow dot - not tested
                color = "orange"
                status_text = "Not Tested"
            elif self.connection_state:
                # Green dot - connected
                color = "green"
                status_text = "Connected"
            else:
                # Red dot - failed
                color = "red"
                status_text = "Failed"

            # Format endpoint for display
            endpoint_display = self.llm_config.endpoint
            if "://" in endpoint_display:
                # Remove http:// or https://
                endpoint_display = endpoint_display.split("://", 1)[1]

            status_html = f'<span style="color: {color}; font-size: 16px;">●</span> ' f"<b>{status_text}</b> - {self.llm_config.model} @ {endpoint_display}"
            self.status_label.setText(status_html)
            self.status_label.setToolTip("Click to change LLM Settings")

    def set_llm_config(self, config: Optional[LLMConfig]):
        """
        Set LLM configuration.

        Args:
            config: LLM configuration
        """
        self.llm_config = config
        self.connection_state = None  # Reset connection state when config changes
        self._update_generate_button_state()
        self._update_status_display()

    def _generate_analysis(self, force_rebuild: bool = True):
        """
        Generate AI analysis.

        Args:
            force_rebuild: If True, always rebuild report from current data
        """
        if not self.llm_config:
            self.status_label.setText("Error: No LLM configuration")
            return

        # ALWAYS rebuild the report to ensure we have the latest metadata
        # (especially test type, which may have changed)
        if force_rebuild or not self.current_report:
            self.status_label.setText("Building report from current data...")
            self.report_build_requested.emit()
            # The report will be set via set_report() after it's built
            # Then _continue_generation() will be called
            return

        # Continue with generation using current report
        self._continue_generation()

    def _continue_generation(self):
        """Continue analysis generation after report is ready."""
        # Check if at least one option is selected
        if not any(
            [
                self.summary_checkbox.isChecked(),
                self.findings_checkbox.isChecked(),
                self.recommendations_checkbox.isChecked(),
            ]
        ):
            self.status_label.setText("Please select at least one AI feature to generate")
            return

        # Disable controls during generation
        self.generate_button.setEnabled(False)
        self.enable_ai_checkbox.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.status_label.setText("Generating AI analysis...")

        # Start system monitoring
        self.monitor_frame.setVisible(True)
        self._update_system_stats()  # Initial update
        self.monitor_timer.start()

        # Reset error flag
        self.errors_occurred = False

        # Create and start worker thread
        self.worker = AIAnalysisWorker(
            self.current_report,
            self.llm_config,
            self.summary_checkbox.isChecked(),
            self.findings_checkbox.isChecked(),
            self.recommendations_checkbox.isChecked(),
        )

        self.worker.progress.connect(self._on_progress)
        self.worker.error.connect(self._on_error)
        self.worker.finished.connect(self._on_analysis_complete)
        self.worker.start()

    def _on_progress(self, message: str):
        """Handle progress update."""
        self.status_label.setText(message)

    def _on_error(self, error_message: str):
        """Handle error."""
        # Track that errors occurred
        self.errors_occurred = True
        print(f"AI Analysis Error: {error_message}")

    def _on_analysis_complete(self, results: Dict):
        """
        Handle analysis completion.

        Args:
            results: Dictionary with generated content
        """
        # Store results
        self.generated_content = results

        # Update connection state based on whether errors occurred
        if self.errors_occurred:
            # Errors occurred during generation
            self.connection_state = False
        else:
            # No errors - successful connection and generation
            self.connection_state = True

        # Update preview tabs with markdown rendering
        if results.get("executive_summary"):
            html = self._markdown_to_html(results["executive_summary"])
            self.summary_preview.setHtml(html)

        if results.get("key_findings"):
            # Convert findings list to markdown
            findings_md = "\n".join(f"- {finding}" for finding in results["key_findings"])
            html = self._markdown_to_html(findings_md)
            self.findings_preview.setHtml(html)

        if results.get("recommendations"):
            # Convert recommendations list to markdown
            recommendations_md = "\n".join(f"- {rec}" for rec in results["recommendations"])
            html = self._markdown_to_html(recommendations_md)
            self.recommendations_preview.setHtml(html)

        # Stop system monitoring
        self.monitor_timer.stop()
        self.monitor_frame.setVisible(False)

        # Re-enable controls
        self.generate_button.setEnabled(True)
        self.enable_ai_checkbox.setEnabled(True)
        self.clear_button.setEnabled(True)
        self.progress_bar.setVisible(False)
        self._update_status_display()

        # Emit signal
        self.analysis_generated.emit(results)

    def _clear_results(self):
        """Clear generated results."""
        self.generated_content = {
            "executive_summary": None,
            "key_findings": [],
            "recommendations": [],
        }
        self.summary_preview.clear()
        self.findings_preview.clear()
        self.recommendations_preview.clear()
        self.clear_button.setEnabled(False)
        self._update_status_display()

    def get_generated_content(self) -> Dict:
        """
        Get generated AI content.

        Returns:
            Dictionary with generated content
        """
        return self.generated_content

    def is_ai_enabled(self) -> bool:
        """Check if AI features are enabled."""
        return self.enable_ai_checkbox.isChecked()

    def has_generated_content(self) -> bool:
        """Check if AI content has been generated."""
        return self.generated_content.get("executive_summary") is not None or len(self.generated_content.get("key_findings", [])) > 0 or len(self.generated_content.get("recommendations", [])) > 0
