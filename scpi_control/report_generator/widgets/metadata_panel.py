"""
Metadata input panel for report information.

Allows users to enter report metadata like technician name, test date,
equipment details, and other custom fields.
"""

from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import QDateTime, Qt, pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QColorDialog, QComboBox, QDateTimeEdit, QFileDialog, QFormLayout, QGroupBox, QLineEdit, QPushButton, QTextEdit, QVBoxLayout, QWidget

from scpi_control.report_generator.models.report_data import ReportMetadata
from scpi_control.report_generator.models.test_types import get_test_type_names

#: Default brand colors, matching `BrandingTemplate`'s field defaults.
DEFAULT_BRAND_COLORS = {
    "primary_color": "#1f77b4",
    "secondary_color": "#ff7f0e",
    "success_color": "#2ca02c",
    "failure_color": "#d62728",
}

#: Human-readable labels for each brand color key, used for button/dialog titles.
BRAND_COLOR_LABELS = {
    "primary_color": "Title",
    "secondary_color": "Heading",
    "success_color": "Pass",
    "failure_color": "Fail",
}


class MetadataPanel(QWidget):
    """Panel for inputting report metadata."""

    metadata_changed = pyqtSignal()

    def __init__(self, parent=None):
        """
        Initialize metadata panel.

        Args:
            parent: Parent widget
        """
        super().__init__(parent)

        self.company_logo_path = None
        self._brand_colors = dict(DEFAULT_BRAND_COLORS)

        self._setup_ui()

    def _setup_ui(self):
        """Set up the user interface."""
        layout = QVBoxLayout()

        # Basic information
        basic_group = QGroupBox("Basic Information")
        basic_layout = QFormLayout()

        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText("e.g., Power Supply Ripple Test")
        self.title_edit.textChanged.connect(self.metadata_changed.emit)
        basic_layout.addRow("Report Title:", self.title_edit)

        self.technician_edit = QLineEdit()
        self.technician_edit.textChanged.connect(self.metadata_changed.emit)
        basic_layout.addRow("Technician:", self.technician_edit)

        self.test_date_edit = QDateTimeEdit()
        self.test_date_edit.setDateTime(QDateTime.currentDateTime())
        self.test_date_edit.setCalendarPopup(True)
        self.test_date_edit.dateTimeChanged.connect(self.metadata_changed.emit)
        basic_layout.addRow("Test Date:", self.test_date_edit)

        basic_group.setLayout(basic_layout)
        layout.addWidget(basic_group)

        # Equipment information
        equipment_group = QGroupBox("Equipment Information")
        equipment_layout = QFormLayout()

        self.equipment_model_edit = QLineEdit()
        self.equipment_model_edit.setPlaceholderText("e.g., SDS2104X Plus")
        self.equipment_model_edit.textChanged.connect(self.metadata_changed.emit)
        equipment_layout.addRow("Model:", self.equipment_model_edit)

        self.equipment_id_edit = QLineEdit()
        self.equipment_id_edit.setPlaceholderText("e.g., SN123456")
        self.equipment_id_edit.textChanged.connect(self.metadata_changed.emit)
        equipment_layout.addRow("ID/Serial:", self.equipment_id_edit)

        equipment_group.setLayout(equipment_layout)
        layout.addWidget(equipment_group)

        # Test details
        test_group = QGroupBox("Test Details")
        test_layout = QFormLayout()

        # Test type selector
        self.test_type_combo = QComboBox()
        self.test_type_combo.setToolTip("Select the type of test being performed.\n" "This helps the AI understand the expected signal characteristics.")
        # Populate with test types
        for test_id, test_name in get_test_type_names():
            self.test_type_combo.addItem(test_name, test_id)
        self.test_type_combo.currentIndexChanged.connect(self.metadata_changed.emit)
        test_layout.addRow("Test Type:", self.test_type_combo)

        self.project_edit = QLineEdit()
        self.project_edit.textChanged.connect(self.metadata_changed.emit)
        test_layout.addRow("Project:", self.project_edit)

        self.customer_edit = QLineEdit()
        self.customer_edit.textChanged.connect(self.metadata_changed.emit)
        test_layout.addRow("Customer:", self.customer_edit)

        self.procedure_edit = QLineEdit()
        self.procedure_edit.setPlaceholderText("e.g., TEST-PWR-001")
        self.procedure_edit.textChanged.connect(self.metadata_changed.emit)
        test_layout.addRow("Procedure:", self.procedure_edit)

        test_group.setLayout(test_layout)
        layout.addWidget(test_group)

        # Environmental conditions
        env_group = QGroupBox("Environmental Conditions")
        env_layout = QFormLayout()

        self.temperature_edit = QLineEdit()
        self.temperature_edit.setPlaceholderText("e.g., 23°C")
        self.temperature_edit.textChanged.connect(self.metadata_changed.emit)
        env_layout.addRow("Temperature:", self.temperature_edit)

        self.humidity_edit = QLineEdit()
        self.humidity_edit.setPlaceholderText("e.g., 45% RH")
        self.humidity_edit.textChanged.connect(self.metadata_changed.emit)
        env_layout.addRow("Humidity:", self.humidity_edit)

        self.location_edit = QLineEdit()
        self.location_edit.setPlaceholderText("e.g., Lab 3")
        self.location_edit.textChanged.connect(self.metadata_changed.emit)
        env_layout.addRow("Location:", self.location_edit)

        env_group.setLayout(env_layout)
        layout.addWidget(env_group)

        # Branding
        branding_group = QGroupBox("Branding")
        branding_layout = QFormLayout()

        self.company_name_edit = QLineEdit()
        self.company_name_edit.textChanged.connect(self.metadata_changed.emit)
        branding_layout.addRow("Company:", self.company_name_edit)

        logo_layout = QVBoxLayout()
        self.logo_path_label = QLineEdit()
        self.logo_path_label.setReadOnly(True)
        self.logo_path_label.setPlaceholderText("No logo selected")
        logo_layout.addWidget(self.logo_path_label)

        logo_btn = QPushButton("Select Logo...")
        logo_btn.clicked.connect(self._select_logo)
        logo_layout.addWidget(logo_btn)

        branding_layout.addRow("Logo:", logo_layout)

        self.title_color_btn = QPushButton()
        self.title_color_btn.clicked.connect(lambda: self._pick_color("primary_color"))
        branding_layout.addRow("Title Color:", self.title_color_btn)

        self.heading_color_btn = QPushButton()
        self.heading_color_btn.clicked.connect(lambda: self._pick_color("secondary_color"))
        branding_layout.addRow("Heading Color:", self.heading_color_btn)

        self.pass_color_btn = QPushButton()
        self.pass_color_btn.clicked.connect(lambda: self._pick_color("success_color"))
        branding_layout.addRow("Pass Color:", self.pass_color_btn)

        self.fail_color_btn = QPushButton()
        self.fail_color_btn.clicked.connect(lambda: self._pick_color("failure_color"))
        branding_layout.addRow("Fail Color:", self.fail_color_btn)

        self._color_buttons = {
            "primary_color": self.title_color_btn,
            "secondary_color": self.heading_color_btn,
            "success_color": self.pass_color_btn,
            "failure_color": self.fail_color_btn,
        }
        self._refresh_color_swatches()

        self.header_edit = QLineEdit()
        self.header_edit.setPlaceholderText("e.g., CONFIDENTIAL")
        self.header_edit.textChanged.connect(self.metadata_changed.emit)
        branding_layout.addRow("Header Text:", self.header_edit)

        self.footer_edit = QLineEdit()
        self.footer_edit.setPlaceholderText("e.g., Company Confidential")
        self.footer_edit.textChanged.connect(self.metadata_changed.emit)
        branding_layout.addRow("Footer Text:", self.footer_edit)

        branding_group.setLayout(branding_layout)
        layout.addWidget(branding_group)

        # Notes
        notes_group = QGroupBox("Notes")
        notes_layout = QVBoxLayout()

        self.notes_edit = QTextEdit()
        self.notes_edit.setPlaceholderText("Additional notes or comments...")
        self.notes_edit.setMaximumHeight(100)
        self.notes_edit.textChanged.connect(self.metadata_changed.emit)
        notes_layout.addWidget(self.notes_edit)

        notes_group.setLayout(notes_layout)
        layout.addWidget(notes_group)

        layout.addStretch()

        self.setLayout(layout)

    def _select_logo(self):
        """Open file dialog to select company logo."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Company Logo",
            "",
            "Images (*.png *.jpg *.jpeg *.bmp);;All Files (*)",
        )

        if file_path:
            self.company_logo_path = Path(file_path)
            self.logo_path_label.setText(str(self.company_logo_path))
            self.metadata_changed.emit()

    def _pick_color(self, key: str):
        """
        Open a color picker dialog for one brand color.

        Args:
            key: One of "primary_color", "secondary_color", "success_color", "failure_color".
        """
        label = BRAND_COLOR_LABELS.get(key, key)
        current_color = QColor(self._brand_colors[key])
        color = QColorDialog.getColor(current_color, self, f"Select {label} Color")

        if color.isValid():
            self._brand_colors[key] = color.name()
            self._refresh_color_swatches()
            self.metadata_changed.emit()

    def _refresh_color_swatches(self):
        """Re-paint the four brand color buttons to match `self._brand_colors`."""
        for key, button in self._color_buttons.items():
            button.setStyleSheet(f"background-color: {self._brand_colors[key]}")

    def get_branding_colors(self) -> dict:
        """
        Get the current brand colors.

        Returns:
            Dict with keys "primary_color", "secondary_color", "success_color", "failure_color".
        """
        return dict(self._brand_colors)

    def set_branding_colors(self, colors: dict) -> None:
        """
        Load brand colors into the form, updating only the keys present in `colors`.

        Args:
            colors: Dict of brand color hex strings, keyed as in get_branding_colors().
        """
        for key in self._brand_colors:
            if colors.get(key):
                self._brand_colors[key] = colors[key]
        self._refresh_color_swatches()

    def get_metadata(self) -> ReportMetadata:
        """
        Get the current metadata from the form.

        Returns:
            ReportMetadata object
        """
        # Get selected test type ID from combo box
        test_type_id = self.test_type_combo.currentData()
        if test_type_id is None:
            test_type_id = "general"

        return ReportMetadata(
            title=self.title_edit.text().strip(),
            technician=self.technician_edit.text().strip(),
            test_date=self.test_date_edit.dateTime().toPyDateTime(),
            equipment_model=self.equipment_model_edit.text().strip() or None,
            equipment_id=self.equipment_id_edit.text().strip() or None,
            test_procedure=self.procedure_edit.text().strip() or None,
            test_type=test_type_id,
            project_name=self.project_edit.text().strip() or None,
            customer=self.customer_edit.text().strip() or None,
            temperature=self.temperature_edit.text().strip() or None,
            humidity=self.humidity_edit.text().strip() or None,
            location=self.location_edit.text().strip() or None,
            notes=self.notes_edit.toPlainText().strip() or None,
            company_name=self.company_name_edit.text().strip() or None,
            company_logo_path=self.company_logo_path,
            header_text=self.header_edit.text().strip() or None,
            footer_text=self.footer_edit.text().strip() or None,
        )

    def set_metadata(self, metadata: ReportMetadata):
        """
        Load metadata into the form.

        Args:
            metadata: ReportMetadata to load
        """
        self.title_edit.setText(metadata.title or "")
        self.technician_edit.setText(metadata.technician or "")
        self.test_date_edit.setDateTime(QDateTime(metadata.test_date))

        # Set test type
        if metadata.test_type:
            # Find index of test type in combo box
            index = self.test_type_combo.findData(metadata.test_type)
            if index >= 0:
                self.test_type_combo.setCurrentIndex(index)
            else:
                # If not found, default to "general"
                index = self.test_type_combo.findData("general")
                if index >= 0:
                    self.test_type_combo.setCurrentIndex(index)

        if metadata.equipment_model:
            self.equipment_model_edit.setText(metadata.equipment_model)
        if metadata.equipment_id:
            self.equipment_id_edit.setText(metadata.equipment_id)
        if metadata.test_procedure:
            self.procedure_edit.setText(metadata.test_procedure)
        if metadata.project_name:
            self.project_edit.setText(metadata.project_name)
        if metadata.customer:
            self.customer_edit.setText(metadata.customer)
        if metadata.temperature:
            self.temperature_edit.setText(metadata.temperature)
        if metadata.humidity:
            self.humidity_edit.setText(metadata.humidity)
        if metadata.location:
            self.location_edit.setText(metadata.location)
        if metadata.notes:
            self.notes_edit.setPlainText(metadata.notes)
        if metadata.company_name:
            self.company_name_edit.setText(metadata.company_name)
        if metadata.company_logo_path:
            self.company_logo_path = metadata.company_logo_path
            self.logo_path_label.setText(str(self.company_logo_path))
        if metadata.header_text:
            self.header_edit.setText(metadata.header_text)
        if metadata.footer_text:
            self.footer_edit.setText(metadata.footer_text)

    def clear_form(self):
        """Clear all form fields."""
        self.title_edit.clear()
        self.technician_edit.clear()
        self.test_date_edit.setDateTime(QDateTime.currentDateTime())
        self.equipment_model_edit.clear()
        self.equipment_id_edit.clear()
        self.procedure_edit.clear()
        # Reset test type to "general"
        index = self.test_type_combo.findData("general")
        if index >= 0:
            self.test_type_combo.setCurrentIndex(index)
        self.project_edit.clear()
        self.customer_edit.clear()
        self.temperature_edit.clear()
        self.humidity_edit.clear()
        self.location_edit.clear()
        self.notes_edit.clear()
        self.company_name_edit.clear()
        self.company_logo_path = None
        self.logo_path_label.clear()
        self._brand_colors = dict(DEFAULT_BRAND_COLORS)
        self._refresh_color_swatches()
        self.header_edit.clear()
        self.footer_edit.clear()
