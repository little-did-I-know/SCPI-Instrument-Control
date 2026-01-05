"""
Report options dialog for customizing report generation.

Provides interactive UI for selecting report sections, AI generation options,
output formats, and plot styles before generating a report.
"""

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from siglent.report_generator.models.plot_style import PlotStyle
from siglent.report_generator.models.report_options import ReportOptions
from siglent.report_generator.models.template import ReportTemplate


class ReportOptionsDialog(QDialog):
    """Dialog for customizing report generation options."""

    def __init__(self, parent=None, current_options: ReportOptions = None, current_plot_style: PlotStyle = None):
        """
        Initialize report options dialog.

        Args:
            parent: Parent widget
            current_options: Current report options (defaults if None)
            current_plot_style: Current plot style (defaults if None)
        """
        super().__init__(parent)

        self.options = current_options or ReportOptions()
        self.plot_style = current_plot_style or PlotStyle()

        self.setWindowTitle("Report Options")
        self.setModal(True)
        self.resize(600, 500)

        self._setup_ui()
        self._load_options()

    def _setup_ui(self):
        """Set up the user interface."""
        layout = QVBoxLayout()

        # Tab widget for different option categories
        tabs = QTabWidget()

        # Content tab
        content_tab = self._create_content_tab()
        tabs.addTab(content_tab, "Content")

        # Format tab
        format_tab = self._create_format_tab()
        tabs.addTab(format_tab, "Format")

        # Plot Style tab
        plot_style_tab = self._create_plot_style_tab()
        tabs.addTab(plot_style_tab, "Plot Style")

        # Statistics tab
        statistics_tab = self._create_statistics_tab()
        tabs.addTab(statistics_tab, "Statistics")

        layout.addWidget(tabs)

        # Bottom buttons
        button_layout = QHBoxLayout()

        load_template_btn = QPushButton("Load from Template...")
        load_template_btn.clicked.connect(self._load_from_template)
        button_layout.addWidget(load_template_btn)

        save_template_btn = QPushButton("Save as Template...")
        save_template_btn.clicked.connect(self._save_as_template)
        button_layout.addWidget(save_template_btn)

        button_layout.addStretch()

        generate_btn = QPushButton("Generate Report")
        generate_btn.setDefault(True)
        generate_btn.clicked.connect(self.accept)
        button_layout.addWidget(generate_btn)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        layout.addLayout(button_layout)

        self.setLayout(layout)

    def _create_content_tab(self) -> QWidget:
        """Create content options tab."""
        widget = QWidget()
        layout = QVBoxLayout()

        # Sections to include
        sections_group = QGroupBox("Sections to Include")
        sections_layout = QVBoxLayout()

        self.include_executive_summary_cb = QCheckBox("Include Executive Summary")
        sections_layout.addWidget(self.include_executive_summary_cb)

        self.include_key_findings_cb = QCheckBox("Include Key Findings")
        sections_layout.addWidget(self.include_key_findings_cb)

        self.include_recommendations_cb = QCheckBox("Include Recommendations")
        sections_layout.addWidget(self.include_recommendations_cb)

        self.include_waveform_plots_cb = QCheckBox("Include Waveform Plots")
        sections_layout.addWidget(self.include_waveform_plots_cb)

        self.include_fft_analysis_cb = QCheckBox("Include FFT Analysis")
        sections_layout.addWidget(self.include_fft_analysis_cb)

        sections_group.setLayout(sections_layout)
        layout.addWidget(sections_group)

        # Note about AI features
        ai_note = QLabel("Note: AI features (Executive Summary, Key Findings, Recommendations) " "can be generated in the AI Analysis panel before creating the report.")
        ai_note.setWordWrap(True)
        ai_note.setStyleSheet("color: #666; font-style: italic; margin: 10px;")
        layout.addWidget(ai_note)

        layout.addStretch()

        widget.setLayout(layout)
        return widget

    def _create_format_tab(self) -> QWidget:
        """Create format options tab."""
        widget = QWidget()
        layout = QVBoxLayout()

        form = QFormLayout()

        # Page size
        self.page_size_combo = QComboBox()
        self.page_size_combo.addItems(["Letter", "A4"])
        form.addRow("Page Size:", self.page_size_combo)

        # Plot dimensions
        self.plot_width_spin = QDoubleSpinBox()
        self.plot_width_spin.setRange(2.0, 12.0)
        self.plot_width_spin.setSingleStep(0.5)
        self.plot_width_spin.setSuffix(" inches")
        self.plot_width_spin.setValue(6.5)
        form.addRow("Plot Width:", self.plot_width_spin)

        self.plot_height_spin = QDoubleSpinBox()
        self.plot_height_spin.setRange(1.0, 10.0)
        self.plot_height_spin.setSingleStep(0.5)
        self.plot_height_spin.setSuffix(" inches")
        self.plot_height_spin.setValue(3.0)
        form.addRow("Plot Height:", self.plot_height_spin)

        # Plot DPI
        self.plot_dpi_spin = QSpinBox()
        self.plot_dpi_spin.setRange(72, 600)
        self.plot_dpi_spin.setSingleStep(50)
        self.plot_dpi_spin.setValue(150)
        form.addRow("Plot DPI:", self.plot_dpi_spin)

        layout.addLayout(form)
        layout.addStretch()

        widget.setLayout(layout)
        return widget

    def _create_plot_style_tab(self) -> QWidget:
        """Create plot style options tab."""
        widget = QWidget()
        layout = QVBoxLayout()

        # Matplotlib style preset
        preset_layout = QFormLayout()
        self.matplotlib_style_combo = QComboBox()
        self.matplotlib_style_combo.addItems(["default", "seaborn-v0_8", "ggplot", "bmh", "fivethirtyeight", "grayscale"])
        preset_layout.addRow("Style Preset:", self.matplotlib_style_combo)
        layout.addLayout(preset_layout)

        # Colors group
        colors_group = QGroupBox("Colors")
        colors_layout = QFormLayout()

        self.waveform_color_btn = QPushButton()
        self.waveform_color_btn.clicked.connect(lambda: self._pick_color("waveform"))
        colors_layout.addRow("Waveform Color:", self.waveform_color_btn)

        self.fft_color_btn = QPushButton()
        self.fft_color_btn.clicked.connect(lambda: self._pick_color("fft"))
        colors_layout.addRow("FFT Color:", self.fft_color_btn)

        self.grid_color_btn = QPushButton()
        self.grid_color_btn.clicked.connect(lambda: self._pick_color("grid"))
        colors_layout.addRow("Grid Color:", self.grid_color_btn)

        self.background_color_btn = QPushButton()
        self.background_color_btn.clicked.connect(lambda: self._pick_color("background"))
        colors_layout.addRow("Background Color:", self.background_color_btn)

        colors_group.setLayout(colors_layout)
        layout.addWidget(colors_group)

        # Line style group
        line_group = QGroupBox("Line Style")
        line_layout = QFormLayout()

        self.linewidth_spin = QDoubleSpinBox()
        self.linewidth_spin.setRange(0.1, 5.0)
        self.linewidth_spin.setSingleStep(0.1)
        self.linewidth_spin.setValue(0.8)
        line_layout.addRow("Line Width:", self.linewidth_spin)

        self.grid_enabled_cb = QCheckBox("Show Grid")
        line_layout.addRow("", self.grid_enabled_cb)

        self.grid_alpha_spin = QDoubleSpinBox()
        self.grid_alpha_spin.setRange(0.0, 1.0)
        self.grid_alpha_spin.setSingleStep(0.1)
        self.grid_alpha_spin.setValue(0.3)
        line_layout.addRow("Grid Transparency:", self.grid_alpha_spin)

        line_group.setLayout(line_layout)
        layout.addWidget(line_group)

        # Font sizes group
        font_group = QGroupBox("Font Sizes")
        font_layout = QFormLayout()

        self.title_fontsize_spin = QSpinBox()
        self.title_fontsize_spin.setRange(6, 24)
        self.title_fontsize_spin.setValue(11)
        font_layout.addRow("Title Font Size:", self.title_fontsize_spin)

        self.label_fontsize_spin = QSpinBox()
        self.label_fontsize_spin.setRange(6, 20)
        self.label_fontsize_spin.setValue(10)
        font_layout.addRow("Label Font Size:", self.label_fontsize_spin)

        self.tick_fontsize_spin = QSpinBox()
        self.tick_fontsize_spin.setRange(6, 16)
        self.tick_fontsize_spin.setValue(9)
        font_layout.addRow("Tick Font Size:", self.tick_fontsize_spin)

        font_group.setLayout(font_layout)
        layout.addWidget(font_group)

        layout.addStretch()

        widget.setLayout(layout)
        return widget

    def _create_statistics_tab(self) -> QWidget:
        """Create statistics options tab."""
        widget = QWidget()
        layout = QVBoxLayout()

        # Master statistics enable checkbox
        self.include_statistics_table_cb = QCheckBox("Include Statistics Table")
        self.include_statistics_table_cb.setChecked(True)
        self.include_statistics_table_cb.setToolTip("Add a table with calculated signal statistics below each waveform plot")
        font = self.include_statistics_table_cb.font()
        font.setBold(True)
        self.include_statistics_table_cb.setFont(font)
        layout.addWidget(self.include_statistics_table_cb)

        layout.addSpacing(10)

        # Statistics categories group
        stats_group = QGroupBox("Statistics Categories")
        stats_layout = QVBoxLayout()

        # Frequency/Period stats
        self.include_frequency_stats_cb = QCheckBox("Frequency / Period")
        self.include_frequency_stats_cb.setChecked(True)
        self.include_frequency_stats_cb.setToolTip("Fundamental frequency (Hz) and period (s/ms/µs)")
        stats_layout.addWidget(self.include_frequency_stats_cb)

        # Amplitude stats
        self.include_amplitude_stats_cb = QCheckBox("Amplitude Measurements")
        self.include_amplitude_stats_cb.setChecked(True)
        self.include_amplitude_stats_cb.setToolTip("Vpp, Vmax, Vmin, Vamp, Vrms, Vmean, DC offset")
        stats_layout.addWidget(self.include_amplitude_stats_cb)

        # Timing stats
        self.include_timing_stats_cb = QCheckBox("Timing Measurements")
        self.include_timing_stats_cb.setChecked(True)
        self.include_timing_stats_cb.setToolTip("Rise time, fall time, pulse width, duty cycle")
        stats_layout.addWidget(self.include_timing_stats_cb)

        # Quality stats
        self.include_quality_stats_cb = QCheckBox("Signal Quality Metrics")
        self.include_quality_stats_cb.setChecked(True)
        self.include_quality_stats_cb.setToolTip("SNR, noise level, overshoot, undershoot, jitter")
        stats_layout.addWidget(self.include_quality_stats_cb)

        # Plateau stability
        self.include_plateau_stability_cb = QCheckBox("Plateau Stability Analysis (Advanced)")
        self.include_plateau_stability_cb.setChecked(False)
        self.include_plateau_stability_cb.setToolTip("Measures noise on high and low plateaus for square waves, pulses, and periodic signals. " "Shows how stable/clean the plateau levels are.")
        stats_layout.addWidget(self.include_plateau_stability_cb)

        stats_group.setLayout(stats_layout)
        layout.addWidget(stats_group)

        # Info label
        info_label = QLabel("Note: Statistics are automatically calculated from waveform data. " "Complex signals may have inaccurate measurements for timing/quality metrics.")
        info_label.setWordWrap(True)
        info_label.setStyleSheet("color: #666; font-style: italic; margin: 10px;")
        layout.addWidget(info_label)

        layout.addStretch()

        widget.setLayout(layout)
        return widget

    def _pick_color(self, color_type: str):
        """
        Open color picker dialog.

        Args:
            color_type: Type of color to pick ("waveform", "fft", "grid", "background")
        """
        # Get current color
        current_colors = {
            "waveform": self.plot_style.waveform_color,
            "fft": self.plot_style.fft_color,
            "grid": self.plot_style.grid_color,
            "background": self.plot_style.background_color,
        }
        current_color = QColor(current_colors[color_type])

        # Show color picker
        color = QColorDialog.getColor(current_color, self, f"Select {color_type.title()} Color")

        if color.isValid():
            # Update plot style
            color_hex = color.name()
            if color_type == "waveform":
                self.plot_style.waveform_color = color_hex
                self.waveform_color_btn.setStyleSheet(f"background-color: {color_hex}")
            elif color_type == "fft":
                self.plot_style.fft_color = color_hex
                self.fft_color_btn.setStyleSheet(f"background-color: {color_hex}")
            elif color_type == "grid":
                self.plot_style.grid_color = color_hex
                self.grid_color_btn.setStyleSheet(f"background-color: {color_hex}")
            elif color_type == "background":
                self.plot_style.background_color = color_hex
                self.background_color_btn.setStyleSheet(f"background-color: {color_hex}")

    def _load_options(self):
        """Load current options into UI."""
        # Content tab
        self.include_executive_summary_cb.setChecked(self.options.include_executive_summary)
        self.include_key_findings_cb.setChecked(self.options.include_key_findings)
        self.include_recommendations_cb.setChecked(self.options.include_recommendations)
        self.include_waveform_plots_cb.setChecked(self.options.include_waveform_plots)
        self.include_fft_analysis_cb.setChecked(self.options.include_fft_analysis)

        # Format tab
        self.page_size_combo.setCurrentText(self.options.page_size.capitalize())
        self.plot_width_spin.setValue(self.options.plot_width_inches)
        self.plot_height_spin.setValue(self.options.plot_height_inches)
        self.plot_dpi_spin.setValue(self.options.plot_dpi)

        # Plot style tab
        self.matplotlib_style_combo.setCurrentText(self.plot_style.matplotlib_style)
        self.linewidth_spin.setValue(self.plot_style.waveform_linewidth)
        self.grid_enabled_cb.setChecked(self.plot_style.grid_enabled)
        self.grid_alpha_spin.setValue(self.plot_style.grid_alpha)
        self.title_fontsize_spin.setValue(self.plot_style.title_fontsize)
        self.label_fontsize_spin.setValue(self.plot_style.label_fontsize)
        self.tick_fontsize_spin.setValue(self.plot_style.tick_fontsize)

        # Set color button backgrounds
        self.waveform_color_btn.setStyleSheet(f"background-color: {self.plot_style.waveform_color}")
        self.fft_color_btn.setStyleSheet(f"background-color: {self.plot_style.fft_color}")
        self.grid_color_btn.setStyleSheet(f"background-color: {self.plot_style.grid_color}")
        self.background_color_btn.setStyleSheet(f"background-color: {self.plot_style.background_color}")

        # Statistics tab
        self.include_statistics_table_cb.setChecked(self.options.include_statistics_table)
        self.include_frequency_stats_cb.setChecked(self.options.include_frequency_stats)
        self.include_amplitude_stats_cb.setChecked(self.options.include_amplitude_stats)
        self.include_timing_stats_cb.setChecked(self.options.include_timing_stats)
        self.include_quality_stats_cb.setChecked(self.options.include_quality_stats)
        self.include_plateau_stability_cb.setChecked(self.options.include_plateau_stability)

    def get_options(self) -> ReportOptions:
        """
        Get the configured report options.

        Returns:
            ReportOptions instance
        """
        self.options.include_executive_summary = self.include_executive_summary_cb.isChecked()
        self.options.include_key_findings = self.include_key_findings_cb.isChecked()
        self.options.include_recommendations = self.include_recommendations_cb.isChecked()
        self.options.include_waveform_plots = self.include_waveform_plots_cb.isChecked()
        self.options.include_fft_analysis = self.include_fft_analysis_cb.isChecked()

        # AI generation is now handled in AI Analysis Panel, not in this dialog
        # Keep the options values unchanged (they might be set from templates)

        self.options.page_size = self.page_size_combo.currentText().lower()
        self.options.plot_width_inches = self.plot_width_spin.value()
        self.options.plot_height_inches = self.plot_height_spin.value()
        self.options.plot_dpi = self.plot_dpi_spin.value()

        # Statistics options
        self.options.include_statistics_table = self.include_statistics_table_cb.isChecked()
        self.options.include_frequency_stats = self.include_frequency_stats_cb.isChecked()
        self.options.include_amplitude_stats = self.include_amplitude_stats_cb.isChecked()
        self.options.include_timing_stats = self.include_timing_stats_cb.isChecked()
        self.options.include_quality_stats = self.include_quality_stats_cb.isChecked()
        self.options.include_plateau_stability = self.include_plateau_stability_cb.isChecked()

        return self.options

    def get_plot_style(self) -> PlotStyle:
        """
        Get the configured plot style.

        Returns:
            PlotStyle instance
        """
        self.plot_style.matplotlib_style = self.matplotlib_style_combo.currentText()
        self.plot_style.waveform_linewidth = self.linewidth_spin.value()
        self.plot_style.grid_enabled = self.grid_enabled_cb.isChecked()
        self.plot_style.grid_alpha = self.grid_alpha_spin.value()
        self.plot_style.title_fontsize = self.title_fontsize_spin.value()
        self.plot_style.label_fontsize = self.label_fontsize_spin.value()
        self.plot_style.tick_fontsize = self.tick_fontsize_spin.value()

        return self.plot_style

    def set_options(self, options: ReportOptions, plot_style: PlotStyle = None):
        """
        Load options into the UI.

        Args:
            options: Report options to load
            plot_style: Plot style to load (optional)
        """
        self.options = options
        if plot_style:
            self.plot_style = plot_style
        self._load_options()

    def _load_from_template(self):
        """Load settings from a saved template."""
        from siglent.report_generator.widgets.template_manager_dialog import TemplateManagerDialog

        dialog = TemplateManagerDialog(self)
        if dialog.exec():
            template = dialog.get_selected_template()
            if template:
                # Load options from template
                self.options.include_executive_summary = template.include_executive_summary
                self.options.include_key_findings = template.include_key_findings
                self.options.include_recommendations = template.include_recommendations
                self.options.include_waveform_plots = template.include_waveform_plots
                self.options.include_fft_analysis = template.include_fft_analysis

                self.options.auto_generate_summary = template.auto_generate_summary
                self.options.auto_generate_findings = template.auto_generate_findings
                self.options.auto_generate_recommendations = template.auto_generate_recommendations

                self.options.page_size = template.page_size
                self.options.plot_width_inches = template.plot_width_inches
                self.options.plot_height_inches = template.plot_height_inches
                self.options.plot_dpi = template.plot_dpi

                self.plot_style = template.plot_style

                self._load_options()

                QMessageBox.information(
                    self,
                    "Template Loaded",
                    f"Loaded settings from template: {template.name}",
                )

    def _save_as_template(self):
        """Save current settings as a template."""
        # Get template name from user
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

        # Create template from current options
        template = ReportTemplate(
            name=name.strip(),
            description=description.strip() if description else None,
            include_executive_summary=self.include_executive_summary_cb.isChecked(),
            include_key_findings=self.include_key_findings_cb.isChecked(),
            include_recommendations=self.include_recommendations_cb.isChecked(),
            include_waveform_plots=self.include_waveform_plots_cb.isChecked(),
            include_fft_analysis=self.include_fft_analysis_cb.isChecked(),
            auto_generate_summary=self.auto_generate_summary_cb.isChecked(),
            auto_generate_findings=self.auto_generate_findings_cb.isChecked(),
            auto_generate_recommendations=self.auto_generate_recommendations_cb.isChecked(),
            page_size=self.page_size_combo.currentText().lower(),
            plot_width_inches=self.plot_width_spin.value(),
            plot_height_inches=self.plot_height_spin.value(),
            plot_dpi=self.plot_dpi_spin.value(),
            plot_style=self.get_plot_style(),
        )

        # Save to library
        try:
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
