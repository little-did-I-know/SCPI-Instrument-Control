"""Vector graphics panel for XY mode drawing on oscilloscope.

This panel provides UI controls for generating vector graphics waveforms
that can be displayed in XY mode on the oscilloscope.

Features:
    - Multiple shape types (circle, rectangle, star, etc.)
    - Parameter controls for each shape
    - Live preview of generated paths
    - Waveform generation and export
    - Animation frame generation

Requires 'fun' extras installation:
    pip install "Siglent-Oscilloscope[fun]"
"""

import logging
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QCheckBox, QComboBox, QDoubleSpinBox, QFileDialog, QFormLayout, QGroupBox, QHBoxLayout, QLabel, QMessageBox, QPushButton, QSpinBox, QTextEdit, QVBoxLayout, QWidget

logger = logging.getLogger(__name__)

# Check if vector graphics dependencies are available
try:
    import numpy as np

    from siglent.vector_graphics import Shape, VectorDisplay, VectorPath

    VECTOR_GRAPHICS_AVAILABLE = True
except ImportError as e:
    VECTOR_GRAPHICS_AVAILABLE = False
    IMPORT_ERROR_MSG = str(e)


class VectorGraphicsPanel(QWidget):
    """Panel for vector graphics generation and XY mode control.

    This panel allows users to generate waveforms for drawing shapes
    on the oscilloscope in XY mode.
    """

    def __init__(self, parent: Optional[QWidget] = None):
        """Initialize vector graphics panel.

        Args:
            parent: Parent widget
        """
        super().__init__(parent)
        self._scope = None
        self._vector_display = None
        self._current_path: Optional[VectorPath] = None

        self._init_ui()

    def _init_ui(self):
        """Initialize user interface."""
        layout = QVBoxLayout(self)

        # Check if dependencies are available
        if not VECTOR_GRAPHICS_AVAILABLE:
            self._create_install_message(layout)
            return

        # XY Mode Control
        xy_group = QGroupBox("XY Mode Control")
        xy_layout = QVBoxLayout()

        xy_info = QLabel("<b>Setup:</b><br>" "1. Connect AWG outputs to scope inputs<br>" "2. AWG CH1 → Scope CH1 (X axis)<br>" "3. AWG CH2 → Scope CH2 (Y axis)<br>" "4. Enable XY mode below")
        xy_info.setWordWrap(True)
        xy_layout.addWidget(xy_info)

        xy_btn_layout = QHBoxLayout()
        self.enable_xy_btn = QPushButton("Enable XY Mode")
        self.enable_xy_btn.clicked.connect(self._enable_xy_mode)
        self.disable_xy_btn = QPushButton("Disable XY Mode")
        self.disable_xy_btn.clicked.connect(self._disable_xy_mode)
        self.disable_xy_btn.setEnabled(False)
        xy_btn_layout.addWidget(self.enable_xy_btn)
        xy_btn_layout.addWidget(self.disable_xy_btn)
        xy_layout.addLayout(xy_btn_layout)

        xy_group.setLayout(xy_layout)
        layout.addWidget(xy_group)

        # Shape Selection
        shape_group = QGroupBox("Shape Generator")
        shape_layout = QVBoxLayout()

        # Shape type selector
        type_layout = QHBoxLayout()
        type_layout.addWidget(QLabel("Shape Type:"))
        self.shape_combo = QComboBox()
        self.shape_combo.addItems(["Circle", "Rectangle", "Star", "Triangle", "Lissajous", "Line"])
        self.shape_combo.currentTextChanged.connect(self._on_shape_changed)
        type_layout.addWidget(self.shape_combo)
        shape_layout.addLayout(type_layout)

        # Parameter inputs (will change based on shape)
        self.param_widget = QWidget()
        self.param_layout = QFormLayout()
        self.param_widget.setLayout(self.param_layout)
        shape_layout.addWidget(self.param_widget)

        # Generate button
        self.generate_btn = QPushButton("Generate Shape")
        self.generate_btn.clicked.connect(self._generate_shape)
        shape_layout.addWidget(self.generate_btn)

        shape_group.setLayout(shape_layout)
        layout.addWidget(shape_group)

        # Waveform Export
        export_group = QGroupBox("Waveform Export")
        export_layout = QVBoxLayout()

        # Sample rate
        rate_layout = QHBoxLayout()
        rate_layout.addWidget(QLabel("Sample Rate:"))
        self.sample_rate_spin = QDoubleSpinBox()
        self.sample_rate_spin.setRange(1, 1000)
        self.sample_rate_spin.setValue(1.0)
        self.sample_rate_spin.setSuffix(" MSa/s")
        rate_layout.addWidget(self.sample_rate_spin)
        export_layout.addLayout(rate_layout)

        # Duration
        duration_layout = QHBoxLayout()
        duration_layout.addWidget(QLabel("Duration:"))
        self.duration_spin = QDoubleSpinBox()
        self.duration_spin.setRange(0.001, 10.0)
        self.duration_spin.setValue(0.1)
        self.duration_spin.setSuffix(" s")
        duration_layout.addWidget(self.duration_spin)
        export_layout.addLayout(duration_layout)

        # Format selection
        format_layout = QHBoxLayout()
        format_layout.addWidget(QLabel("Format:"))
        self.format_combo = QComboBox()
        self.format_combo.addItems(["CSV", "NumPy", "Binary"])
        format_layout.addWidget(self.format_combo)
        export_layout.addLayout(format_layout)

        # Export button
        self.export_btn = QPushButton("Save Waveforms...")
        self.export_btn.clicked.connect(self._export_waveforms)
        self.export_btn.setEnabled(False)
        export_layout.addWidget(self.export_btn)

        export_group.setLayout(export_layout)
        layout.addWidget(export_group)

        # Status/Info
        info_group = QGroupBox("Info")
        info_layout = QVBoxLayout()
        self.info_text = QTextEdit()
        self.info_text.setReadOnly(True)
        self.info_text.setMaximumHeight(100)
        self.info_text.setPlainText("Select a shape type and adjust parameters.\n" "Click 'Generate Shape' to create the vector path.\n" "Then 'Save Waveforms' to export for AWG upload.")
        info_layout.addWidget(self.info_text)
        info_group.setLayout(info_layout)
        layout.addWidget(info_group)

        layout.addStretch()

        # Initialize parameter inputs for default shape
        self._on_shape_changed(self.shape_combo.currentText())

    def _create_install_message(self, layout: QVBoxLayout):
        """Create installation message when dependencies missing."""
        msg_group = QGroupBox("Vector Graphics - Installation Required")
        msg_layout = QVBoxLayout()

        icon_label = QLabel("🎨")
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_label.setStyleSheet("font-size: 48px;")
        msg_layout.addWidget(icon_label)

        title = QLabel("<h2>Vector Graphics Feature</h2>")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        msg_layout.addWidget(title)

        info = QLabel(
            "<p>This feature allows you to draw shapes, text, and animations<br>"
            "on your oscilloscope screen using XY mode!</p>"
            "<p><b>Installation Required:</b></p>"
            "<p>The vector graphics feature requires additional packages.</p>"
        )
        info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        info.setWordWrap(True)
        msg_layout.addWidget(info)

        install_label = QLabel('<p><code>pip install "Siglent-Oscilloscope[fun]"</code></p>')
        install_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        install_label.setStyleSheet("background-color: #f0f0f0; padding: 10px; font-family: monospace;")
        msg_layout.addWidget(install_label)

        features = QLabel(
            "<p><b>What you can do:</b></p>"
            "<ul>"
            "<li>Draw circles, stars, rectangles, and more</li>"
            "<li>Display text messages on screen</li>"
            "<li>Create Lissajous figures</li>"
            "<li>Generate animations</li>"
            "</ul>"
        )
        features.setWordWrap(True)
        msg_layout.addWidget(features)

        msg_group.setLayout(msg_layout)
        layout.addWidget(msg_group)
        layout.addStretch()

    def _on_shape_changed(self, shape_type: str):
        """Update parameter inputs when shape type changes."""
        if not VECTOR_GRAPHICS_AVAILABLE:
            return

        # Clear current parameters
        while self.param_layout.count():
            child = self.param_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        # Add parameters based on shape type
        if shape_type == "Circle":
            self.radius_spin = QDoubleSpinBox()
            self.radius_spin.setRange(0.1, 2.0)
            self.radius_spin.setValue(0.8)
            self.radius_spin.setSingleStep(0.1)
            self.param_layout.addRow("Radius:", self.radius_spin)

            self.points_spin = QSpinBox()
            self.points_spin.setRange(100, 5000)
            self.points_spin.setValue(1000)
            self.points_spin.setSingleStep(100)
            self.param_layout.addRow("Points:", self.points_spin)

        elif shape_type == "Rectangle":
            self.width_spin = QDoubleSpinBox()
            self.width_spin.setRange(0.1, 2.0)
            self.width_spin.setValue(1.6)
            self.width_spin.setSingleStep(0.1)
            self.param_layout.addRow("Width:", self.width_spin)

            self.height_spin = QDoubleSpinBox()
            self.height_spin.setRange(0.1, 2.0)
            self.height_spin.setValue(1.2)
            self.height_spin.setSingleStep(0.1)
            self.param_layout.addRow("Height:", self.height_spin)

            self.points_spin = QSpinBox()
            self.points_spin.setRange(50, 1000)
            self.points_spin.setValue(250)
            self.param_layout.addRow("Points/Side:", self.points_spin)

        elif shape_type == "Star":
            self.star_points_spin = QSpinBox()
            self.star_points_spin.setRange(3, 20)
            self.star_points_spin.setValue(5)
            self.param_layout.addRow("Points:", self.star_points_spin)

            self.outer_radius_spin = QDoubleSpinBox()
            self.outer_radius_spin.setRange(0.1, 2.0)
            self.outer_radius_spin.setValue(0.9)
            self.outer_radius_spin.setSingleStep(0.1)
            self.param_layout.addRow("Outer Radius:", self.outer_radius_spin)

            self.inner_radius_spin = QDoubleSpinBox()
            self.inner_radius_spin.setRange(0.1, 2.0)
            self.inner_radius_spin.setValue(0.4)
            self.inner_radius_spin.setSingleStep(0.1)
            self.param_layout.addRow("Inner Radius:", self.inner_radius_spin)

        elif shape_type == "Triangle":
            self.size_spin = QDoubleSpinBox()
            self.size_spin.setRange(0.1, 2.0)
            self.size_spin.setValue(1.0)
            self.size_spin.setSingleStep(0.1)
            self.param_layout.addRow("Size:", self.size_spin)

            self.points_spin = QSpinBox()
            self.points_spin.setRange(50, 1000)
            self.points_spin.setValue(300)
            self.param_layout.addRow("Points/Side:", self.points_spin)

        elif shape_type == "Lissajous":
            self.liss_a_spin = QSpinBox()
            self.liss_a_spin.setRange(1, 10)
            self.liss_a_spin.setValue(3)
            self.param_layout.addRow("Frequency A:", self.liss_a_spin)

            self.liss_b_spin = QSpinBox()
            self.liss_b_spin.setRange(1, 10)
            self.liss_b_spin.setValue(2)
            self.param_layout.addRow("Frequency B:", self.liss_b_spin)

            self.liss_delta_spin = QDoubleSpinBox()
            self.liss_delta_spin.setRange(0, 360)
            self.liss_delta_spin.setValue(90)
            self.liss_delta_spin.setSuffix("°")
            self.param_layout.addRow("Phase Shift:", self.liss_delta_spin)

            self.points_spin = QSpinBox()
            self.points_spin.setRange(500, 5000)
            self.points_spin.setValue(2000)
            self.param_layout.addRow("Points:", self.points_spin)

        elif shape_type == "Line":
            self.start_x_spin = QDoubleSpinBox()
            self.start_x_spin.setRange(-2.0, 2.0)
            self.start_x_spin.setValue(-0.8)
            self.start_x_spin.setSingleStep(0.1)
            self.param_layout.addRow("Start X:", self.start_x_spin)

            self.start_y_spin = QDoubleSpinBox()
            self.start_y_spin.setRange(-2.0, 2.0)
            self.start_y_spin.setValue(-0.8)
            self.start_y_spin.setSingleStep(0.1)
            self.param_layout.addRow("Start Y:", self.start_y_spin)

            self.end_x_spin = QDoubleSpinBox()
            self.end_x_spin.setRange(-2.0, 2.0)
            self.end_x_spin.setValue(0.8)
            self.end_x_spin.setSingleStep(0.1)
            self.param_layout.addRow("End X:", self.end_x_spin)

            self.end_y_spin = QDoubleSpinBox()
            self.end_y_spin.setRange(-2.0, 2.0)
            self.end_y_spin.setValue(0.8)
            self.end_y_spin.setSingleStep(0.1)
            self.param_layout.addRow("End Y:", self.end_y_spin)

            self.points_spin = QSpinBox()
            self.points_spin.setRange(10, 1000)
            self.points_spin.setValue(100)
            self.param_layout.addRow("Points:", self.points_spin)

    def _generate_shape(self):
        """Generate the selected shape."""
        if not VECTOR_GRAPHICS_AVAILABLE:
            return

        shape_type = self.shape_combo.currentText()

        try:
            if shape_type == "Circle":
                radius = self.radius_spin.value()
                points = self.points_spin.value()
                self._current_path = Shape.circle(radius=radius, points=points)
                info = f"Generated circle: radius={radius}, {points} points"

            elif shape_type == "Rectangle":
                width = self.width_spin.value()
                height = self.height_spin.value()
                points = self.points_spin.value()
                self._current_path = Shape.rectangle(width=width, height=height, points_per_side=points)
                info = f"Generated rectangle: {width}x{height}, {points} points/side"

            elif shape_type == "Star":
                num_points = self.star_points_spin.value()
                outer = self.outer_radius_spin.value()
                inner = self.inner_radius_spin.value()
                self._current_path = Shape.star(num_points=num_points, outer_radius=outer, inner_radius=inner)
                info = f"Generated star: {num_points} points, outer={outer}, inner={inner}"

            elif shape_type == "Triangle":
                size = self.size_spin.value()
                points = self.points_spin.value()
                vertices = [
                    (0, size * 0.8),
                    (-size * 0.7, -size * 0.4),
                    (size * 0.7, -size * 0.4),
                ]
                self._current_path = Shape.polygon(vertices, points_per_side=points)
                info = f"Generated triangle: size={size}, {points} points/side"

            elif shape_type == "Lissajous":
                a = self.liss_a_spin.value()
                b = self.liss_b_spin.value()
                delta = np.radians(self.liss_delta_spin.value())
                points = self.points_spin.value()
                self._current_path = Shape.lissajous(a=a, b=b, delta=delta, points=points)
                info = f"Generated Lissajous: {a}:{b}, phase={self.liss_delta_spin.value()}°, {points} points"

            elif shape_type == "Line":
                start = (self.start_x_spin.value(), self.start_y_spin.value())
                end = (self.end_x_spin.value(), self.end_y_spin.value())
                points = self.points_spin.value()
                self._current_path = Shape.line(start=start, end=end, points=points)
                info = f"Generated line: from {start} to {end}, {points} points"

            self.info_text.setPlainText(f"{info}\n\n" f"Shape ready! Click 'Save Waveforms' to export.\n" f"Total points: {len(self._current_path.x)}")

            self.export_btn.setEnabled(True)
            logger.info(info)

        except Exception as e:
            QMessageBox.critical(self, "Generation Error", f"Failed to generate shape:\n{e}")
            logger.error(f"Shape generation failed: {e}")

    def _export_waveforms(self):
        """Export waveforms to files."""
        if not VECTOR_GRAPHICS_AVAILABLE or self._current_path is None:
            return

        # Get save location
        filename, _ = QFileDialog.getSaveFileName(self, "Save Waveforms", "", "All Files (*)")

        if not filename:
            return

        # Remove extension if provided
        filename = Path(filename).stem

        try:
            # Get parameters
            sample_rate = self.sample_rate_spin.value() * 1e6  # Convert MSa/s to Sa/s
            duration = self.duration_spin.value()
            format_map = {"CSV": "csv", "NumPy": "npy", "Binary": "bin"}
            file_format = format_map[self.format_combo.currentText()]

            # Check if we have a scope connection with vector display
            if self._scope and hasattr(self._scope, "vector_display"):
                display = self._scope.vector_display
            else:
                # Create temporary display for export (no scope needed)
                from siglent.vector_graphics import VectorDisplay

                display = VectorDisplay(None, ch_x=1, ch_y=2)

            # Save waveforms
            display.save_waveforms(
                self._current_path,
                filename,
                sample_rate=sample_rate,
                duration=duration,
                format=file_format,
            )

            QMessageBox.information(
                self,
                "Export Successful",
                f"Waveforms saved:\n"
                f"  {filename}_x.{file_format}\n"
                f"  {filename}_y.{file_format}\n\n"
                f"Sample rate: {sample_rate/1e6:.1f} MSa/s\n"
                f"Duration: {duration*1000:.1f} ms\n\n"
                f"Load these files into your AWG channels to display the shape!",
            )

            self.info_text.append(f"\nExported to {filename}_x/y.{file_format}\n" f"Ready for AWG upload!")

        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Failed to export waveforms:\n{e}")
            logger.error(f"Waveform export failed: {e}")

    def _enable_xy_mode(self):
        """Enable XY mode on oscilloscope."""
        if not self._scope:
            QMessageBox.warning(self, "Not Connected", "Please connect to an oscilloscope first.")
            return

        try:
            if self._vector_display is None:
                self._vector_display = self._scope.vector_display

            voltage_scale = 1.0
            self._vector_display.enable_xy_mode(voltage_scale=voltage_scale)

            self.enable_xy_btn.setEnabled(False)
            self.disable_xy_btn.setEnabled(True)

            self.info_text.setPlainText(
                "XY mode enabled!\n\n"
                "Channels configured:\n"
                f"  CH{self._vector_display.ch_x} = X axis\n"
                f"  CH{self._vector_display.ch_y} = Y axis\n\n"
                "You may need to manually enable XY mode on scope:\n"
                "  Display → XY Mode → ON"
            )

            logger.info("XY mode enabled")

        except Exception as e:
            QMessageBox.critical(self, "XY Mode Error", f"Failed to enable XY mode:\n{e}")
            logger.error(f"XY mode enable failed: {e}")

    def _disable_xy_mode(self):
        """Disable XY mode on oscilloscope."""
        if not self._vector_display:
            return

        try:
            self._vector_display.disable_xy_mode()

            self.enable_xy_btn.setEnabled(True)
            self.disable_xy_btn.setEnabled(False)

            self.info_text.setPlainText("XY mode disabled")
            logger.info("XY mode disabled")

        except Exception as e:
            QMessageBox.critical(self, "XY Mode Error", f"Failed to disable XY mode:\n{e}")
            logger.error(f"XY mode disable failed: {e}")

    def set_scope(self, scope):
        """Set the oscilloscope instance.

        Args:
            scope: Oscilloscope instance or None
        """
        self._scope = scope
        self._vector_display = None

        if VECTOR_GRAPHICS_AVAILABLE:
            if scope:
                self.enable_xy_btn.setEnabled(True)
                self.info_text.setPlainText(f"Connected to: {scope.model_capability.model_name}\n\n" "Ready to configure XY mode!")
            else:
                self.enable_xy_btn.setEnabled(False)
                self.disable_xy_btn.setEnabled(False)
                self.info_text.setPlainText("Not connected.\n\n" "You can still generate and export waveforms!")

    def __repr__(self) -> str:
        """String representation."""
        return f"VectorGraphicsPanel(available={VECTOR_GRAPHICS_AVAILABLE})"
