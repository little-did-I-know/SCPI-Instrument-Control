"""
Template manager dialog for browsing and managing report templates.

Allows users to load, delete, import, and export report templates from
their template library.
"""

from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QDialog, QFileDialog, QGroupBox, QHBoxLayout, QInputDialog, QLabel, QListWidget, QListWidgetItem, QMessageBox, QPushButton, QTextEdit, QVBoxLayout

from siglent.report_generator.models.template import ReportTemplate


class TemplateManagerDialog(QDialog):
    """Dialog for managing saved templates."""

    template_selected = pyqtSignal(ReportTemplate)

    def __init__(self, parent=None):
        """
        Initialize template manager dialog.

        Args:
            parent: Parent widget
        """
        super().__init__(parent)

        self.selected_template: ReportTemplate = None

        self.setWindowTitle("Template Manager")
        self.setModal(True)
        self.resize(700, 500)

        self._setup_ui()
        self._refresh_template_list()

    def _setup_ui(self):
        """Set up the user interface."""
        layout = QHBoxLayout()

        # Left panel: Template list
        left_layout = QVBoxLayout()

        list_label = QLabel("Available Templates:")
        left_layout.addWidget(list_label)

        self.template_list = QListWidget()
        self.template_list.currentItemChanged.connect(self._on_template_selected)
        self.template_list.itemDoubleClicked.connect(self._load_template)
        left_layout.addWidget(self.template_list)

        # Action buttons
        action_layout = QHBoxLayout()

        import_btn = QPushButton("Import...")
        import_btn.clicked.connect(self._import_template)
        action_layout.addWidget(import_btn)

        export_btn = QPushButton("Export...")
        export_btn.clicked.connect(self._export_template)
        action_layout.addWidget(export_btn)

        left_layout.addLayout(action_layout)

        layout.addLayout(left_layout, 60)

        # Right panel: Template details and actions
        right_layout = QVBoxLayout()

        # Template info group
        info_group = QGroupBox("Template Information")
        info_layout = QVBoxLayout()

        self.name_label = QLabel("Name: ")
        info_layout.addWidget(self.name_label)

        self.desc_label = QLabel("Description:")
        info_layout.addWidget(self.desc_label)

        self.desc_text = QTextEdit()
        self.desc_text.setReadOnly(True)
        self.desc_text.setMaximumHeight(100)
        info_layout.addWidget(self.desc_text)

        self.details_label = QLabel("Details:")
        info_layout.addWidget(self.details_label)

        self.details_text = QTextEdit()
        self.details_text.setReadOnly(True)
        info_layout.addWidget(self.details_text)

        info_group.setLayout(info_layout)
        right_layout.addWidget(info_group)

        # Template action buttons
        button_layout = QVBoxLayout()

        self.load_btn = QPushButton("Load Selected")
        self.load_btn.setEnabled(False)
        self.load_btn.clicked.connect(self._load_template)
        button_layout.addWidget(self.load_btn)

        self.duplicate_btn = QPushButton("Duplicate...")
        self.duplicate_btn.setEnabled(False)
        self.duplicate_btn.clicked.connect(self._duplicate_template)
        button_layout.addWidget(self.duplicate_btn)

        self.delete_btn = QPushButton("Delete")
        self.delete_btn.setEnabled(False)
        self.delete_btn.clicked.connect(self._delete_template)
        button_layout.addWidget(self.delete_btn)

        button_layout.addStretch()

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.reject)
        button_layout.addWidget(close_btn)

        right_layout.addLayout(button_layout)

        layout.addLayout(right_layout, 40)

        self.setLayout(layout)

    def _refresh_template_list(self):
        """Reload template list from disk."""
        self.template_list.clear()

        try:
            templates = ReportTemplate.list_templates()

            if not templates:
                item = QListWidgetItem("No templates found")
                item.setFlags(Qt.ItemFlag.NoItemFlags)
                self.template_list.addItem(item)
            else:
                for template_name in sorted(templates):
                    self.template_list.addItem(template_name)

        except Exception as e:
            QMessageBox.warning(
                self,
                "Error Loading Templates",
                f"Failed to load template list:\n{str(e)}",
            )

    def _on_template_selected(self, current: QListWidgetItem, previous: QListWidgetItem):
        """
        Handle template selection.

        Args:
            current: Currently selected item
            previous: Previously selected item
        """
        if not current or current.text() == "No templates found":
            self._clear_template_info()
            return

        template_name = current.text()

        try:
            template = ReportTemplate.load_from_library(template_name)
            self.selected_template = template

            # Update UI with template info
            self.name_label.setText(f"<b>Name:</b> {template.name}")
            self.desc_text.setText(template.description or "No description")

            # Build details text
            details = []
            details.append(f"<b>Sections:</b>")
            details.append(f"  • Executive Summary: {'Yes' if template.include_executive_summary else 'No'}")
            details.append(f"  • Key Findings: {'Yes' if template.include_key_findings else 'No'}")
            details.append(f"  • Recommendations: {'Yes' if template.include_recommendations else 'No'}")
            details.append(f"  • Waveform Plots: {'Yes' if template.include_waveform_plots else 'No'}")
            details.append(f"  • FFT Analysis: {'Yes' if template.include_fft_analysis else 'No'}")
            details.append(f"")
            details.append(f"<b>AI Generation:</b>")
            details.append(f"  • Auto Summary: {'Yes' if template.auto_generate_summary else 'No'}")
            details.append(f"  • Auto Findings: {'Yes' if template.auto_generate_findings else 'No'}")
            details.append(f"  • Auto Recommendations: {'Yes' if template.auto_generate_recommendations else 'No'}")
            details.append(f"")
            details.append(f"<b>Format:</b>")
            details.append(f"  • Page Size: {template.page_size.upper()}")
            details.append(f'  • Plot Size: {template.plot_width_inches}" × {template.plot_height_inches}"')
            details.append(f"  • DPI: {template.plot_dpi}")

            if template.llm_provider:
                details.append(f"")
                details.append(f"<b>LLM Provider:</b> {template.llm_provider}")

            self.details_text.setHtml("<br>".join(details))

            # Enable action buttons
            self.load_btn.setEnabled(True)
            self.duplicate_btn.setEnabled(True)
            self.delete_btn.setEnabled(True)

        except Exception as e:
            QMessageBox.warning(
                self,
                "Error Loading Template",
                f"Failed to load template '{template_name}':\n{str(e)}",
            )
            self._clear_template_info()

    def _clear_template_info(self):
        """Clear template information display."""
        self.selected_template = None
        self.name_label.setText("<b>Name:</b> ")
        self.desc_text.clear()
        self.details_text.clear()
        self.load_btn.setEnabled(False)
        self.duplicate_btn.setEnabled(False)
        self.delete_btn.setEnabled(False)

    def _load_template(self):
        """Emit selected template and close dialog."""
        if self.selected_template:
            self.template_selected.emit(self.selected_template)
            self.accept()

    def _duplicate_template(self):
        """Duplicate the selected template with a new name."""
        if not self.selected_template:
            return

        # Get new name
        new_name, ok = QInputDialog.getText(self, "Duplicate Template", "Enter name for duplicated template:", text=f"{self.selected_template.name} (Copy)")

        if not ok or not new_name.strip():
            return

        try:
            # Create a copy with new name
            duplicate = ReportTemplate(
                name=new_name.strip(),
                description=self.selected_template.description,
                sections=self.selected_template.sections.copy(),
                criteria_set=self.selected_template.criteria_set,
                branding=self.selected_template.branding,
                include_executive_summary=self.selected_template.include_executive_summary,
                include_key_findings=self.selected_template.include_key_findings,
                include_recommendations=self.selected_template.include_recommendations,
                include_waveform_plots=self.selected_template.include_waveform_plots,
                include_fft_analysis=self.selected_template.include_fft_analysis,
                llm_provider=self.selected_template.llm_provider,
                llm_endpoint=self.selected_template.llm_endpoint,
                llm_model=self.selected_template.llm_model,
                auto_generate_summary=self.selected_template.auto_generate_summary,
                auto_generate_findings=self.selected_template.auto_generate_findings,
                auto_generate_recommendations=self.selected_template.auto_generate_recommendations,
                page_size=self.selected_template.page_size,
                plot_width_inches=self.selected_template.plot_width_inches,
                plot_height_inches=self.selected_template.plot_height_inches,
                plot_dpi=self.selected_template.plot_dpi,
                plot_style=self.selected_template.plot_style,
                default_equipment_model=self.selected_template.default_equipment_model,
                default_test_procedure=self.selected_template.default_test_procedure,
                default_company_name=self.selected_template.default_company_name,
                default_technician=self.selected_template.default_technician,
                default_temperature=self.selected_template.default_temperature,
                default_humidity=self.selected_template.default_humidity,
                default_location=self.selected_template.default_location,
            )

            duplicate.save_to_library()

            QMessageBox.information(
                self,
                "Template Duplicated",
                f"Template duplicated as '{new_name}'",
            )

            self._refresh_template_list()

        except Exception as e:
            QMessageBox.critical(
                self,
                "Error Duplicating Template",
                f"Failed to duplicate template:\n{str(e)}",
            )

    def _delete_template(self):
        """Delete the selected template."""
        if not self.selected_template:
            return

        # Confirm deletion
        reply = QMessageBox.question(
            self,
            "Confirm Deletion",
            f"Are you sure you want to delete template '{self.selected_template.name}'?\n" "This action cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            success = ReportTemplate.delete_from_library(self.selected_template.name)

            if success:
                QMessageBox.information(
                    self,
                    "Template Deleted",
                    f"Template '{self.selected_template.name}' deleted successfully",
                )
                self._clear_template_info()
                self._refresh_template_list()
            else:
                QMessageBox.warning(
                    self,
                    "Template Not Found",
                    "Template not found in library",
                )

        except Exception as e:
            QMessageBox.critical(
                self,
                "Error Deleting Template",
                f"Failed to delete template:\n{str(e)}",
            )

    def _import_template(self):
        """Import template from file."""
        file_path, _ = QFileDialog.getOpenFileName(self, "Import Template", "", "JSON Files (*.json);;All Files (*)")

        if not file_path:
            return

        try:
            # Load template from file
            template = ReportTemplate.load(Path(file_path))

            # Save to library
            template.save_to_library()

            QMessageBox.information(
                self,
                "Template Imported",
                f"Template '{template.name}' imported successfully",
            )

            self._refresh_template_list()

        except Exception as e:
            QMessageBox.critical(
                self,
                "Error Importing Template",
                f"Failed to import template:\n{str(e)}",
            )

    def _export_template(self):
        """Export selected template to file."""
        if not self.selected_template:
            return

        file_path, _ = QFileDialog.getSaveFileName(self, "Export Template", f"{self.selected_template.name}.json", "JSON Files (*.json);;All Files (*)")

        if not file_path:
            return

        try:
            self.selected_template.save(Path(file_path))

            QMessageBox.information(
                self,
                "Template Exported",
                f"Template exported to:\n{file_path}",
            )

        except Exception as e:
            QMessageBox.critical(
                self,
                "Error Exporting Template",
                f"Failed to export template:\n{str(e)}",
            )

    def get_selected_template(self) -> ReportTemplate:
        """
        Get the currently selected template.

        Returns:
            Selected template or None
        """
        return self.selected_template
