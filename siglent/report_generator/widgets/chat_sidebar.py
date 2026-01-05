"""
AI chat sidebar for asking questions about test data.

Provides an interactive chat interface where users can ask questions
about their waveform data and measurements, getting AI-powered answers.
"""

from typing import Optional

from PyQt6.QtCore import Qt, QThread
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtCore import pyqtSignal as Signal
from PyQt6.QtGui import QTextCursor
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QLineEdit, QPushButton, QScrollArea, QTextEdit, QVBoxLayout, QWidget

from siglent.report_generator.llm.analyzer import ReportAnalyzer
from siglent.report_generator.llm.client import LLMClient
from siglent.report_generator.models.report_data import TestReport


class ChatWorker(QThread):
    """Worker thread for LLM chat requests."""

    response_ready = Signal(str)
    error_occurred = Signal(str)

    def __init__(self, analyzer: ReportAnalyzer, report: TestReport, question: str):
        super().__init__()
        self.analyzer = analyzer
        self.report = report
        self.question = question

    def run(self):
        """Run the chat request."""
        try:
            answer = self.analyzer.answer_question(self.report, self.question)
            if answer:
                self.response_ready.emit(answer)
            else:
                self.error_occurred.emit("Failed to get response from LLM")
        except Exception as e:
            self.error_occurred.emit(str(e))


class ChatSidebar(QWidget):
    """Collapsible sidebar for AI chat."""

    def __init__(self, parent=None):
        """
        Initialize chat sidebar.

        Args:
            parent: Parent widget
        """
        super().__init__(parent)

        self.llm_client: Optional[LLMClient] = None
        self.analyzer: Optional[ReportAnalyzer] = None
        self.current_report: Optional[TestReport] = None
        self.chat_worker: Optional[ChatWorker] = None

        self._setup_ui()

    def _setup_ui(self):
        """Set up the user interface."""
        layout = QVBoxLayout()
        layout.setContentsMargins(5, 5, 5, 5)

        # Header
        header = QLabel("AI Assistant")
        header.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(header)

        # Status label
        self.status_label = QLabel("No LLM configured")
        self.status_label.setStyleSheet("color: gray; font-style: italic;")
        layout.addWidget(self.status_label)

        # Chat history
        self.chat_display = QTextEdit()
        self.chat_display.setReadOnly(True)
        self.chat_display.setPlaceholderText(
            "Ask questions about your test data...\n\n"
            "Examples:\n"
            "- What do these measurements tell us?\n"
            "- Why did the frequency measurement fail?\n"
            "- Is the signal quality good?\n"
            "- What should I check next?"
        )
        layout.addWidget(self.chat_display)

        # Input area
        input_layout = QHBoxLayout()

        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("Type your question...")
        self.input_field.returnPressed.connect(self._send_message)
        input_layout.addWidget(self.input_field)

        self.send_btn = QPushButton("Send")
        self.send_btn.clicked.connect(self._send_message)
        self.send_btn.setEnabled(False)
        input_layout.addWidget(self.send_btn)

        layout.addLayout(input_layout)

        # Quick actions
        quick_actions_label = QLabel("Quick Actions:")
        quick_actions_label.setStyleSheet("font-weight: bold; margin-top: 5px;")
        layout.addWidget(quick_actions_label)

        self.summary_btn = QPushButton("Generate Summary")
        self.summary_btn.clicked.connect(self._generate_summary)
        self.summary_btn.setEnabled(False)
        layout.addWidget(self.summary_btn)

        self.insights_btn = QPushButton("Analyze Waveforms")
        self.insights_btn.clicked.connect(self._analyze_waveforms)
        self.insights_btn.setEnabled(False)
        layout.addWidget(self.insights_btn)

        self.interpret_btn = QPushButton("Interpret Measurements")
        self.interpret_btn.clicked.connect(self._interpret_measurements)
        self.interpret_btn.setEnabled(False)
        layout.addWidget(self.interpret_btn)

        # Clear button
        clear_btn = QPushButton("Clear Chat")
        clear_btn.clicked.connect(self._clear_chat)
        layout.addWidget(clear_btn)

        self.setLayout(layout)
        self.setMinimumWidth(300)

    def set_llm_client(self, client: Optional[LLMClient]):
        """
        Set the LLM client for chat.

        Args:
            client: LLM client (None to disable)
        """
        self.llm_client = client

        if client:
            self.analyzer = ReportAnalyzer(client)
            self.status_label.setText(f"Connected to {client.config.model}")
            self.status_label.setStyleSheet("color: green;")
            self._update_buttons_state()
        else:
            self.analyzer = None
            self.status_label.setText("No LLM configured")
            self.status_label.setStyleSheet("color: gray; font-style: italic;")
            self.send_btn.setEnabled(False)
            self.summary_btn.setEnabled(False)
            self.insights_btn.setEnabled(False)
            self.interpret_btn.setEnabled(False)

    def set_report(self, report: Optional[TestReport]):
        """
        Set the current report for context.

        Args:
            report: Test report to use for chat context
        """
        self.current_report = report
        self._update_buttons_state()

        if report:
            self._add_system_message(f"Report loaded: {report.metadata.title}")

    def _update_buttons_state(self):
        """Update button enabled states."""
        has_llm = self.llm_client is not None
        has_report = self.current_report is not None

        self.send_btn.setEnabled(has_llm and has_report)
        self.summary_btn.setEnabled(has_llm and has_report)
        self.insights_btn.setEnabled(has_llm and has_report)
        self.interpret_btn.setEnabled(has_llm and has_report)

    def _send_message(self):
        """Send user message and get AI response."""
        question = self.input_field.text().strip()

        if not question:
            return

        if not self.analyzer or not self.current_report:
            self._add_system_message("Error: No LLM or report configured")
            return

        # Display user message
        self._add_user_message(question)
        self.input_field.clear()

        # Disable input while processing
        self._set_input_enabled(False)
        self._add_system_message("Thinking...")

        # Start worker thread
        self.chat_worker = ChatWorker(self.analyzer, self.current_report, question)
        self.chat_worker.response_ready.connect(self._on_response)
        self.chat_worker.error_occurred.connect(self._on_error)
        self.chat_worker.start()

    def _generate_summary(self):
        """Generate executive summary."""
        if not self.analyzer or not self.current_report:
            return

        self._add_system_message("Generating executive summary...")
        self._set_input_enabled(False)

        # Use a lambda to capture the method reference
        worker = QThread()

        def run_task():
            try:
                summary = self.analyzer.generate_executive_summary(self.current_report)
                if summary:
                    self._on_response(summary)
                else:
                    self._on_error("Failed to generate summary")
            except Exception as e:
                self._on_error(str(e))
            finally:
                worker.quit()

        worker.run = run_task
        worker.start()

    def _analyze_waveforms(self):
        """Analyze waveforms for signal quality."""
        if not self.analyzer or not self.current_report:
            return

        self._add_system_message("Analyzing waveforms...")
        self._set_input_enabled(False)

        worker = QThread()

        def run_task():
            try:
                analysis = self.analyzer.analyze_waveforms(self.current_report)
                if analysis:
                    self._on_response(analysis)
                else:
                    self._on_error("Failed to analyze waveforms")
            except Exception as e:
                self._on_error(str(e))
            finally:
                worker.quit()

        worker.run = run_task
        worker.start()

    def _interpret_measurements(self):
        """Interpret measurement results."""
        if not self.analyzer or not self.current_report:
            return

        self._add_system_message("Interpreting measurements...")
        self._set_input_enabled(False)

        worker = QThread()

        def run_task():
            try:
                interpretation = self.analyzer.interpret_measurements(self.current_report)
                if interpretation:
                    self._on_response(interpretation)
                else:
                    self._on_error("Failed to interpret measurements")
            except Exception as e:
                self._on_error(str(e))
            finally:
                worker.quit()

        worker.run = run_task
        worker.start()

    def _on_response(self, response: str):
        """Handle AI response."""
        self._add_ai_message(response)
        self._set_input_enabled(True)

    def _on_error(self, error: str):
        """Handle error."""
        self._add_system_message(f"Error: {error}")
        self._set_input_enabled(True)

    def _add_user_message(self, message: str):
        """Add user message to chat."""
        self.chat_display.append(f'<p style="color: #1f77b4;"><b>You:</b> {message}</p>')
        self._scroll_to_bottom()

    def _add_ai_message(self, message: str):
        """Add AI message to chat."""
        # Replace newlines with <br> for proper HTML display
        formatted_message = message.replace("\n", "<br>")
        self.chat_display.append(f'<p style="color: #2ca02c;"><b>AI:</b> {formatted_message}</p>')
        self._scroll_to_bottom()

    def _add_system_message(self, message: str):
        """Add system message to chat."""
        self.chat_display.append(f'<p style="color: gray; font-style: italic;">{message}</p>')
        self._scroll_to_bottom()

    def _scroll_to_bottom(self):
        """Scroll chat display to bottom."""
        cursor = self.chat_display.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.chat_display.setTextCursor(cursor)

    def _set_input_enabled(self, enabled: bool):
        """Enable/disable input controls."""
        self.input_field.setEnabled(enabled)
        self.send_btn.setEnabled(enabled and self.llm_client is not None)
        self.summary_btn.setEnabled(enabled and self.llm_client is not None)
        self.insights_btn.setEnabled(enabled and self.llm_client is not None)
        self.interpret_btn.setEnabled(enabled and self.llm_client is not None)

    def _clear_chat(self):
        """Clear chat history."""
        self.chat_display.clear()
