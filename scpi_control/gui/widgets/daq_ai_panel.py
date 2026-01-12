"""AI Analysis panel for DAQ/Data Logger.

This module provides a widget for LLM-powered analysis of DAQ data,
including trend analysis, threshold suggestions, and session summaries.
"""

import logging
from typing import Callable, Dict, List, Optional

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

logger = logging.getLogger(__name__)


class AnalysisWorker(QThread):
    """Background worker for LLM analysis operations."""

    result_ready = pyqtSignal(str)  # analysis result
    error_occurred = pyqtSignal(str)  # error message

    def __init__(
        self,
        analysis_func: Callable,
        *args,
        parent=None,
        **kwargs,
    ):
        """Initialize analysis worker.

        Args:
            analysis_func: Function to call for analysis
            *args: Positional arguments for the function
            parent: Parent QObject
            **kwargs: Keyword arguments for the function
        """
        super().__init__(parent)
        self.analysis_func = analysis_func
        self.args = args
        self.kwargs = kwargs

    def run(self):
        """Execute the analysis."""
        try:
            result = self.analysis_func(*self.args, **self.kwargs)
            if result:
                self.result_ready.emit(result)
            else:
                self.error_occurred.emit("Analysis returned no results")
        except Exception as e:
            logger.error(f"Analysis error: {e}", exc_info=True)
            self.error_occurred.emit(str(e))


class DAQAIPanel(QWidget):
    """AI Analysis panel for DAQ data.

    Provides buttons for trend analysis, threshold suggestions,
    and session summaries, plus a chat interface for questions.
    """

    analysis_started = pyqtSignal()
    analysis_complete = pyqtSignal(str)

    def __init__(self, parent=None):
        """Initialize the AI panel.

        Args:
            parent: Parent widget
        """
        super().__init__(parent)
        self.analyzer = None
        self.data_provider: Optional[Callable[[], List[Dict]]] = None
        self.channels_provider: Optional[Callable[[], List[int]]] = None
        self.configs_provider: Optional[Callable[[], Dict[int, Dict]]] = None
        self.worker: Optional[AnalysisWorker] = None

        self._setup_ui()

    def _setup_ui(self):
        """Set up the user interface."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(8)

        # Provider selector
        provider_layout = QHBoxLayout()

        provider_label = QLabel("AI Provider:")
        provider_layout.addWidget(provider_label)

        self.provider_combo = QComboBox()
        self.provider_combo.addItems(["Ollama (Local)", "OpenAI", "Anthropic"])
        self.provider_combo.currentIndexChanged.connect(self._on_provider_changed)
        provider_layout.addWidget(self.provider_combo)

        self.model_combo = QComboBox()
        self.model_combo.addItems(["llama3.2", "llama3.1", "mistral", "codellama"])
        self.model_combo.setEditable(True)
        provider_layout.addWidget(self.model_combo)

        self.connect_btn = QPushButton("Connect")
        self.connect_btn.clicked.connect(self._on_connect_clicked)
        provider_layout.addWidget(self.connect_btn)

        layout.addLayout(provider_layout)

        # Analysis buttons
        button_layout = QHBoxLayout()

        self.trend_btn = QPushButton("Analyze Trends")
        self.trend_btn.setToolTip("Detect trends and patterns in the data")
        self.trend_btn.clicked.connect(self._on_analyze_trends)
        self.trend_btn.setEnabled(False)
        button_layout.addWidget(self.trend_btn)

        self.threshold_btn = QPushButton("Suggest Thresholds")
        self.threshold_btn.setToolTip("Suggest alarm thresholds based on data")
        self.threshold_btn.clicked.connect(self._on_suggest_thresholds)
        self.threshold_btn.setEnabled(False)
        button_layout.addWidget(self.threshold_btn)

        self.summary_btn = QPushButton("Generate Summary")
        self.summary_btn.setToolTip("Generate a session summary report")
        self.summary_btn.clicked.connect(self._on_generate_summary)
        self.summary_btn.setEnabled(False)
        button_layout.addWidget(self.summary_btn)

        layout.addLayout(button_layout)

        # Response area
        self.response_text = QTextEdit()
        self.response_text.setReadOnly(True)
        self.response_text.setPlaceholderText("AI analysis results will appear here...\n\n" "Connect to an AI provider and collect some data to get started.")
        self.response_text.setStyleSheet(
            """
            QTextEdit {
                background-color: #1e1e1e;
                color: #d4d4d4;
                border: 1px solid #404040;
                border-radius: 4px;
                font-family: monospace;
                font-size: 11px;
            }
        """
        )
        layout.addWidget(self.response_text, stretch=1)

        # Chat input
        chat_layout = QHBoxLayout()

        self.chat_input = QLineEdit()
        self.chat_input.setPlaceholderText("Ask a question about your data...")
        self.chat_input.returnPressed.connect(self._on_send_question)
        self.chat_input.setEnabled(False)
        chat_layout.addWidget(self.chat_input)

        self.send_btn = QPushButton("Send")
        self.send_btn.clicked.connect(self._on_send_question)
        self.send_btn.setEnabled(False)
        chat_layout.addWidget(self.send_btn)

        layout.addLayout(chat_layout)

        # Status label
        self.status_label = QLabel("Not connected to AI provider")
        self.status_label.setStyleSheet("color: #888888; font-size: 10px;")
        layout.addWidget(self.status_label)

    def _on_provider_changed(self, index: int):
        """Handle provider selection change."""
        if index == 0:  # Ollama
            self.model_combo.clear()
            self.model_combo.addItems(["llama3.2", "llama3.1", "mistral", "codellama", "phi3"])
        elif index == 1:  # OpenAI
            self.model_combo.clear()
            self.model_combo.addItems(["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-3.5-turbo"])
        elif index == 2:  # Anthropic
            self.model_combo.clear()
            self.model_combo.addItems(["claude-3-5-sonnet-latest", "claude-3-5-haiku-latest"])

    def _on_connect_clicked(self):
        """Handle connect button click."""
        try:
            from scpi_control.report_generator.llm import create_daq_analyzer

            provider_map = {0: "ollama", 1: "openai", 2: "anthropic"}
            provider = provider_map.get(self.provider_combo.currentIndex(), "ollama")
            model = self.model_combo.currentText()

            self.status_label.setText(f"Connecting to {provider} ({model})...")

            self.analyzer = create_daq_analyzer(provider=provider, model=model)

            # Enable buttons
            self._set_buttons_enabled(True)

            self.status_label.setText(f"Connected: {provider} - {model}")
            self.connect_btn.setText("Reconnect")

            logger.info(f"Connected to LLM provider: {provider} ({model})")

        except Exception as e:
            self.status_label.setText(f"Connection failed: {str(e)}")
            QMessageBox.warning(
                self,
                "Connection Failed",
                f"Failed to connect to AI provider:\n{str(e)}\n\n" "For Ollama, ensure the server is running:\n" "  ollama serve",
            )
            logger.error(f"LLM connection failed: {e}")

    def _set_buttons_enabled(self, enabled: bool):
        """Enable or disable analysis buttons."""
        self.trend_btn.setEnabled(enabled)
        self.threshold_btn.setEnabled(enabled)
        self.summary_btn.setEnabled(enabled)
        self.chat_input.setEnabled(enabled)
        self.send_btn.setEnabled(enabled)

    def set_data_providers(
        self,
        data_provider: Callable[[], List[Dict]],
        channels_provider: Callable[[], List[int]],
        configs_provider: Optional[Callable[[], Dict[int, Dict]]] = None,
    ):
        """Set the data provider functions.

        Args:
            data_provider: Function that returns the data buffer
            channels_provider: Function that returns active channels
            configs_provider: Function that returns channel configs
        """
        self.data_provider = data_provider
        self.channels_provider = channels_provider
        self.configs_provider = configs_provider

    def _get_data(self) -> tuple:
        """Get current data from providers."""
        data = self.data_provider() if self.data_provider else []
        channels = self.channels_provider() if self.channels_provider else []
        configs = self.configs_provider() if self.configs_provider else {}
        return data, channels, configs

    def _on_analyze_trends(self):
        """Handle analyze trends button click."""
        if not self.analyzer:
            return

        data, channels, configs = self._get_data()
        if not data:
            QMessageBox.information(
                self,
                "No Data",
                "No data available for analysis. Start a logging session first.",
            )
            return

        self._run_analysis(
            "Analyzing trends...",
            self.analyzer.analyze_trends,
            data,
            channels,
            configs,
        )

    def _on_suggest_thresholds(self):
        """Handle suggest thresholds button click."""
        if not self.analyzer:
            return

        data, channels, configs = self._get_data()
        if not data or not channels:
            QMessageBox.information(
                self,
                "No Data",
                "No data available for analysis. Start a logging session first.",
            )
            return

        # For now, analyze first channel. Could add channel selector.
        channel = channels[0]
        channel_config = configs.get(channel, {})

        self._run_analysis(
            f"Suggesting thresholds for CH{channel}...",
            lambda: self.analyzer.suggest_thresholds(data, channel, channel_config),
        )

    def _on_generate_summary(self):
        """Handle generate summary button click."""
        if not self.analyzer:
            return

        data, channels, configs = self._get_data()
        if not data:
            QMessageBox.information(
                self,
                "No Data",
                "No data available for analysis. Start a logging session first.",
            )
            return

        # Build session metadata
        metadata = {}
        if data:
            metadata["duration"] = data[-1]["timestamp"] - data[0]["timestamp"]

        self._run_analysis(
            "Generating session summary...",
            self.analyzer.generate_session_summary,
            data,
            channels,
            configs,
            metadata,
        )

    def _on_send_question(self):
        """Handle send question button click."""
        if not self.analyzer:
            return

        question = self.chat_input.text().strip()
        if not question:
            return

        data, channels, configs = self._get_data()

        self.chat_input.clear()
        self.response_text.append(f"\n**You:** {question}\n")

        self._run_analysis(
            "Thinking...",
            self.analyzer.answer_question,
            data,
            channels,
            question,
            configs,
        )

    def _run_analysis(self, status_msg: str, func: Callable, *args, **kwargs):
        """Run an analysis in a background thread.

        Args:
            status_msg: Status message to show
            func: Analysis function to call
            *args: Positional arguments
            **kwargs: Keyword arguments
        """
        self._set_buttons_enabled(False)
        self.status_label.setText(status_msg)
        self.analysis_started.emit()

        self.worker = AnalysisWorker(func, *args, parent=self, **kwargs)
        self.worker.result_ready.connect(self._on_analysis_result)
        self.worker.error_occurred.connect(self._on_analysis_error)
        self.worker.finished.connect(self._on_analysis_finished)
        self.worker.start()

    def _on_analysis_result(self, result: str):
        """Handle analysis result."""
        # Format threshold suggestions specially
        if isinstance(result, dict) and "raw_response" in result:
            result = result["raw_response"]

        self.response_text.setText(result)
        self.status_label.setText("Analysis complete")
        self.analysis_complete.emit(result)

    def _on_analysis_error(self, error: str):
        """Handle analysis error."""
        self.response_text.setText(f"**Error:** {error}")
        self.status_label.setText("Analysis failed")
        logger.error(f"Analysis error: {error}")

    def _on_analysis_finished(self):
        """Handle worker thread finished."""
        self._set_buttons_enabled(True)
        self.worker = None

    def clear_response(self):
        """Clear the response area."""
        self.response_text.clear()
