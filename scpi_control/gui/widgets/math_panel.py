"""Math channel control panel for waveform operations."""

import logging
from typing import Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QCheckBox, QComboBox, QGridLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit, QPushButton, QTextEdit, QVBoxLayout, QWidget

logger = logging.getLogger(__name__)


class MathPanel(QWidget):
    """Widget for controlling math channels.

    Provides expression builder, enable/disable toggles, and quick
    access buttons for common operations.

    Signals:
        math1_expression_changed: Emitted when Math1 expression changes (expression: str)
        math2_expression_changed: Emitted when Math2 expression changes (expression: str)
        math1_enabled_changed: Emitted when Math1 enable state changes (enabled: bool)
        math2_enabled_changed: Emitted when Math2 enable state changes (enabled: bool)
    """

    math1_expression_changed = pyqtSignal(str)
    math2_expression_changed = pyqtSignal(str)
    math1_enabled_changed = pyqtSignal(bool)
    math2_enabled_changed = pyqtSignal(bool)

    def __init__(self, parent: Optional[QWidget] = None):
        """Initialize math panel.

        Args:
            parent: Parent widget
        """
        super().__init__(parent)

        self._init_ui()
        logger.info("Math panel initialized")

    def _init_ui(self):
        """Initialize user interface."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)

        # Math channel 1
        math1_group = self._create_math_group("Math 1", 1)
        layout.addWidget(math1_group)

        # Math channel 2
        math2_group = self._create_math_group("Math 2", 2)
        layout.addWidget(math2_group)

        # Help section
        help_group = self._create_help_section()
        layout.addWidget(help_group)

        layout.addStretch()

    def _create_math_group(self, title: str, channel_num: int) -> QGroupBox:
        """Create math channel control group.

        Args:
            title: Group title
            channel_num: Math channel number (1 or 2)

        Returns:
            Math channel group box
        """
        group = QGroupBox(title)
        layout = QVBoxLayout(group)

        # Enable checkbox
        enable_check = QCheckBox("Enable")
        enable_check.setChecked(False)
        layout.addWidget(enable_check)

        # Expression input
        expr_layout = QHBoxLayout()
        expr_layout.addWidget(QLabel("Expression:"))
        expr_input = QLineEdit()
        expr_input.setPlaceholderText("e.g., C1 + C2")
        expr_layout.addWidget(expr_input)
        layout.addLayout(expr_layout)

        # Quick operation buttons
        ops_layout = QGridLayout()

        # Basic operations
        add_btn = QPushButton("C1 + C2")
        add_btn.clicked.connect(lambda: expr_input.setText("C1 + C2"))
        ops_layout.addWidget(add_btn, 0, 0)

        sub_btn = QPushButton("C1 - C2")
        sub_btn.clicked.connect(lambda: expr_input.setText("C1 - C2"))
        ops_layout.addWidget(sub_btn, 0, 1)

        mul_btn = QPushButton("C1 * C2")
        mul_btn.clicked.connect(lambda: expr_input.setText("C1 * C2"))
        ops_layout.addWidget(mul_btn, 0, 2)

        div_btn = QPushButton("C1 / C2")
        div_btn.clicked.connect(lambda: expr_input.setText("C1 / C2"))
        ops_layout.addWidget(div_btn, 0, 3)

        # Advanced operations
        intg_btn = QPushButton("INTG(C1)")
        intg_btn.clicked.connect(lambda: expr_input.setText("INTG(C1)"))
        ops_layout.addWidget(intg_btn, 1, 0)

        diff_btn = QPushButton("DIFF(C1)")
        diff_btn.clicked.connect(lambda: expr_input.setText("DIFF(C1)"))
        ops_layout.addWidget(diff_btn, 1, 1)

        abs_btn = QPushButton("ABS(C1)")
        abs_btn.clicked.connect(lambda: expr_input.setText("ABS(C1)"))
        ops_layout.addWidget(abs_btn, 1, 2)

        inv_btn = QPushButton("INV(C1)")
        inv_btn.clicked.connect(lambda: expr_input.setText("INV(C1)"))
        ops_layout.addWidget(inv_btn, 1, 3)

        layout.addLayout(ops_layout)

        # Channel selector
        channel_layout = QHBoxLayout()
        channel_layout.addWidget(QLabel("Insert Channel:"))
        channel_combo = QComboBox()
        channel_combo.addItems(["C1", "C2", "C3", "C4"])
        channel_layout.addWidget(channel_combo)
        insert_ch_btn = QPushButton("Insert")
        insert_ch_btn.clicked.connect(lambda: expr_input.insert(channel_combo.currentText()))
        channel_layout.addWidget(insert_ch_btn)
        channel_layout.addStretch()
        layout.addLayout(channel_layout)

        # Apply button
        apply_btn = QPushButton("Apply Expression")
        apply_btn.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;")
        layout.addWidget(apply_btn)

        # Store widgets as attributes
        if channel_num == 1:
            self.math1_enable = enable_check
            self.math1_expression = expr_input
            self.math1_apply = apply_btn
            self.math1_channel_combo = channel_combo

            # Connect signals
            enable_check.toggled.connect(self._on_math1_enabled_changed)
            apply_btn.clicked.connect(self._on_math1_apply)
        else:
            self.math2_enable = enable_check
            self.math2_expression = expr_input
            self.math2_apply = apply_btn
            self.math2_channel_combo = channel_combo

            # Connect signals
            enable_check.toggled.connect(self._on_math2_enabled_changed)
            apply_btn.clicked.connect(self._on_math2_apply)

        return group

    def _create_help_section(self) -> QGroupBox:
        """Create help section with syntax examples.

        Returns:
            Help section group box
        """
        group = QGroupBox("Expression Syntax Help")
        layout = QVBoxLayout(group)

        help_text = QTextEdit()
        help_text.setReadOnly(True)
        help_text.setMaximumHeight(150)
        help_text.setHtml(
            """
<b>Supported Operations:</b><br>
<ul>
<li><b>Basic:</b> C1 + C2, C1 - C2, C1 * C2, C1 / C2</li>
<li><b>Scale:</b> 2 * C1, C1 / 10</li>
<li><b>Offset:</b> C1 + 1.5, C1 - 0.5</li>
<li><b>Functions:</b>
  <ul>
    <li>INTG(C1) - Integration</li>
    <li>DIFF(C1) - Differentiation</li>
    <li>ABS(C1) - Absolute value</li>
    <li>INV(C1) - Invert (negate)</li>
  </ul>
</li>
</ul>
<b>Examples:</b><br>
• Differential: C1 - C2<br>
• Scaled sum: 2 * C1 + C2<br>
• Power: C1 * C2 (voltage × current)<br>
• Average: (C1 + C2) / 2 (not yet supported - use two steps)
        """
        )
        layout.addWidget(help_text)

        return group

    def _on_math1_enabled_changed(self, enabled: bool):
        """Handle Math1 enable state change.

        Args:
            enabled: New enable state
        """
        logger.info(f"Math1 enabled changed to: {enabled}")
        self.math1_enabled_changed.emit(enabled)

        # Enable/disable expression input and apply button
        self.math1_expression.setEnabled(enabled)
        self.math1_apply.setEnabled(enabled)
        self.math1_channel_combo.setEnabled(enabled)

    def _on_math2_enabled_changed(self, enabled: bool):
        """Handle Math2 enable state change.

        Args:
            enabled: New enable state
        """
        logger.info(f"Math2 enabled changed to: {enabled}")
        self.math2_enabled_changed.emit(enabled)

        # Enable/disable expression input and apply button
        self.math2_expression.setEnabled(enabled)
        self.math2_apply.setEnabled(enabled)
        self.math2_channel_combo.setEnabled(enabled)

    def _on_math1_apply(self):
        """Handle Math1 apply button click."""
        expression = self.math1_expression.text().strip()
        if expression:
            logger.info(f"Math1 expression applied: {expression}")
            self.math1_expression_changed.emit(expression)
        else:
            logger.warning("Math1 expression is empty")

    def _on_math2_apply(self):
        """Handle Math2 apply button click."""
        expression = self.math2_expression.text().strip()
        if expression:
            logger.info(f"Math2 expression applied: {expression}")
            self.math2_expression_changed.emit(expression)
        else:
            logger.warning("Math2 expression is empty")

    def set_math1_enabled(self, enabled: bool):
        """Set Math1 enable state programmatically.

        Args:
            enabled: Enable state
        """
        self.math1_enable.setChecked(enabled)

    def set_math2_enabled(self, enabled: bool):
        """Set Math2 enable state programmatically.

        Args:
            enabled: Enable state
        """
        self.math2_enable.setChecked(enabled)

    def set_math1_expression(self, expression: str):
        """Set Math1 expression programmatically.

        Args:
            expression: Expression string
        """
        self.math1_expression.setText(expression)

    def set_math2_expression(self, expression: str):
        """Set Math2 expression programmatically.

        Args:
            expression: Expression string
        """
        self.math2_expression.setText(expression)

    def get_math1_expression(self) -> str:
        """Get Math1 expression.

        Returns:
            Expression string
        """
        return self.math1_expression.text().strip()

    def get_math2_expression(self) -> str:
        """Get Math2 expression.

        Returns:
            Expression string
        """
        return self.math2_expression.text().strip()

    def is_math1_enabled(self) -> bool:
        """Check if Math1 is enabled.

        Returns:
            True if enabled
        """
        return self.math1_enable.isChecked()

    def is_math2_enabled(self) -> bool:
        """Check if Math2 is enabled.

        Returns:
            True if enabled
        """
        return self.math2_enable.isChecked()

    def update_available_channels(self, num_channels: int):
        """Update available channels in channel selector.

        Args:
            num_channels: Number of available channels (2 or 4)
        """
        channels = [f"C{i+1}" for i in range(num_channels)]

        self.math1_channel_combo.clear()
        self.math1_channel_combo.addItems(channels)

        self.math2_channel_combo.clear()
        self.math2_channel_combo.addItems(channels)

        logger.info(f"Math panel updated for {num_channels} channels")
