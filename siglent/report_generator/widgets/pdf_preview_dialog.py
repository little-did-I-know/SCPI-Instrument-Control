"""
PDF preview dialog for reviewing generated reports before saving.

Provides image-based PDF viewing with zoom controls, page navigation, and actions
for editing options, saving, printing, or copying the report.
"""

import io
from pathlib import Path
from typing import List, Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QAction, QImage, QPixmap
from PyQt6.QtWidgets import QApplication, QDialog, QFileDialog, QHBoxLayout, QLabel, QMessageBox, QPushButton, QScrollArea, QToolBar, QVBoxLayout

try:
    import fitz  # PyMuPDF

    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False

try:
    from PyQt6.QtPrintSupport import QPrintDialog, QPrinter

    PRINT_SUPPORT_AVAILABLE = True
except ImportError:
    PRINT_SUPPORT_AVAILABLE = False


class PDFPreviewDialog(QDialog):
    """Dialog for previewing PDF reports before saving."""

    # Signals for workflow coordination
    edit_options_requested = pyqtSignal()
    save_pdf_requested = pyqtSignal(Path)
    save_markdown_requested = pyqtSignal(Path)

    def __init__(self, pdf_path: Path, parent=None):
        """
        Initialize PDF preview dialog.

        Args:
            pdf_path: Path to the temporary PDF file to preview
            parent: Parent widget
        """
        super().__init__(parent)

        if not PYMUPDF_AVAILABLE:
            QMessageBox.critical(parent, "Missing Dependency", "PDF preview requires PyMuPDF (fitz).\n\n" "Install with: pip install PyMuPDF\n\n" "The preview dialog will now close.")
            raise ImportError("PyMuPDF is required for PDF preview")

        self.pdf_path = pdf_path
        self._edit_options_clicked = False
        self.current_page = 0
        self.zoom_level = 1.0  # 100%
        self.pdf_document = None
        self.page_count = 0

        self.setWindowTitle("PDF Report Preview")
        self.setModal(True)
        self.resize(900, 1000)

        self._load_pdf_document()
        self._setup_ui()
        self._render_current_page()

    def _load_pdf_document(self):
        """Load the PDF document using PyMuPDF."""
        if not self.pdf_path.exists():
            raise FileNotFoundError(f"PDF file does not exist: {self.pdf_path}")

        try:
            self.pdf_document = fitz.open(str(self.pdf_path))
            self.page_count = len(self.pdf_document)
            print(f"Loaded PDF: {self.page_count} pages")
        except Exception as e:
            raise RuntimeError(f"Failed to load PDF: {e}")

    def _setup_ui(self):
        """Set up the user interface."""
        layout = QVBoxLayout()

        # Toolbar with navigation and zoom controls
        toolbar = self._create_toolbar()
        layout.addWidget(toolbar)

        # Scroll area for PDF page image
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(False)
        self.scroll_area.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.scroll_area.setStyleSheet("QScrollArea { background-color: #525659; }")

        # Label to display the PDF page as image
        self.page_label = QLabel()
        self.page_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.page_label.setScaledContents(False)
        self.scroll_area.setWidget(self.page_label)

        layout.addWidget(self.scroll_area)

        # Bottom action buttons
        button_layout = self._create_bottom_buttons()
        layout.addLayout(button_layout)

        self.setLayout(layout)

    def _create_toolbar(self) -> QToolBar:
        """Create toolbar with zoom and navigation controls."""
        toolbar = QToolBar()
        toolbar.setMovable(False)

        # Page navigation
        self.prev_page_action = QAction("◀ Previous", self)
        self.prev_page_action.triggered.connect(self._previous_page)
        toolbar.addAction(self.prev_page_action)

        self.page_info_label = QLabel(f"Page 1 of {self.page_count}")
        self.page_info_label.setMinimumWidth(100)
        self.page_info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        toolbar.addWidget(self.page_info_label)

        self.next_page_action = QAction("Next ▶", self)
        self.next_page_action.triggered.connect(self._next_page)
        toolbar.addAction(self.next_page_action)

        toolbar.addSeparator()

        # Zoom controls
        zoom_out_action = QAction("🔍−", self)
        zoom_out_action.triggered.connect(self._zoom_out)
        toolbar.addAction(zoom_out_action)

        self.zoom_info_label = QLabel("100%")
        self.zoom_info_label.setMinimumWidth(60)
        self.zoom_info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        toolbar.addWidget(self.zoom_info_label)

        zoom_in_action = QAction("🔍+", self)
        zoom_in_action.triggered.connect(self._zoom_in)
        toolbar.addAction(zoom_in_action)

        toolbar.addSeparator()

        fit_width_action = QAction("Fit Width", self)
        fit_width_action.triggered.connect(self._fit_width)
        toolbar.addAction(fit_width_action)

        reset_zoom_action = QAction("100%", self)
        reset_zoom_action.triggered.connect(self._reset_zoom)
        toolbar.addAction(reset_zoom_action)

        return toolbar

    def _create_bottom_buttons(self) -> QHBoxLayout:
        """Create bottom action buttons."""
        button_layout = QHBoxLayout()

        # Edit Options button
        edit_btn = QPushButton("Edit Options...")
        edit_btn.clicked.connect(self._edit_options)
        button_layout.addWidget(edit_btn)

        # Save PDF button
        save_pdf_btn = QPushButton("Save PDF...")
        save_pdf_btn.clicked.connect(self._save_pdf)
        button_layout.addWidget(save_pdf_btn)

        # Save as Markdown button
        save_md_btn = QPushButton("Save as Markdown...")
        save_md_btn.clicked.connect(self._save_markdown)
        button_layout.addWidget(save_md_btn)

        # Print button
        if PRINT_SUPPORT_AVAILABLE:
            print_btn = QPushButton("Print...")
            print_btn.clicked.connect(self._print_pdf)
            button_layout.addWidget(print_btn)

        # Copy path button
        copy_btn = QPushButton("Copy Path")
        copy_btn.clicked.connect(self._copy_to_clipboard)
        button_layout.addWidget(copy_btn)

        button_layout.addStretch()

        # Close button
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.reject)
        button_layout.addWidget(close_btn)

        return button_layout

    def _render_current_page(self):
        """Render the current PDF page as an image."""
        if not self.pdf_document or self.current_page >= self.page_count:
            return

        try:
            # Get the page
            page = self.pdf_document[self.current_page]

            # Calculate zoom matrix (2.0 is base DPI scale for good quality)
            zoom = 2.0 * self.zoom_level
            mat = fitz.Matrix(zoom, zoom)

            # Render page to pixmap
            pix = page.get_pixmap(matrix=mat, alpha=False)

            # Convert to QImage
            img_data = pix.samples
            qimage = QImage(img_data, pix.width, pix.height, pix.stride, QImage.Format.Format_RGB888)

            # Convert to QPixmap and display
            pixmap = QPixmap.fromImage(qimage)
            self.page_label.setPixmap(pixmap)
            self.page_label.adjustSize()

            # Update navigation controls
            self._update_controls()

        except Exception as e:
            QMessageBox.critical(self, "Render Error", f"Failed to render page {self.current_page + 1}:\n{str(e)}")

    def _update_controls(self):
        """Update toolbar controls based on current state."""
        # Update page info
        self.page_info_label.setText(f"Page {self.current_page + 1} of {self.page_count}")

        # Update navigation buttons
        self.prev_page_action.setEnabled(self.current_page > 0)
        self.next_page_action.setEnabled(self.current_page < self.page_count - 1)

        # Update zoom info
        self.zoom_info_label.setText(f"{int(self.zoom_level * 100)}%")

    def _previous_page(self):
        """Navigate to previous page."""
        if self.current_page > 0:
            self.current_page -= 1
            self._render_current_page()

    def _next_page(self):
        """Navigate to next page."""
        if self.current_page < self.page_count - 1:
            self.current_page += 1
            self._render_current_page()

    def _zoom_in(self):
        """Zoom in on the PDF."""
        self.zoom_level = min(self.zoom_level * 1.2, 5.0)
        self._render_current_page()

    def _zoom_out(self):
        """Zoom out on the PDF."""
        self.zoom_level = max(self.zoom_level / 1.2, 0.25)
        self._render_current_page()

    def _reset_zoom(self):
        """Reset zoom to 100%."""
        self.zoom_level = 1.0
        self._render_current_page()

    def _fit_width(self):
        """Fit PDF page to window width."""
        if not self.pdf_document:
            return

        try:
            # Get page dimensions
            page = self.pdf_document[self.current_page]
            page_rect = page.rect

            # Calculate zoom to fit width
            available_width = self.scroll_area.viewport().width() - 20  # Padding
            page_width = page_rect.width

            # Account for base DPI scale (2.0)
            self.zoom_level = available_width / (page_width * 2.0)
            self._render_current_page()

        except Exception as e:
            print(f"Error fitting to width: {e}")

    def _edit_options(self):
        """Signal that user wants to edit report options."""
        self._edit_options_clicked = True
        self.edit_options_requested.emit()
        self.reject()

    def _save_pdf(self):
        """Save the PDF to a user-selected location."""
        file_path, _ = QFileDialog.getSaveFileName(self, "Save PDF Report", "test_report.pdf", "PDF Files (*.pdf);;All Files (*)")

        if not file_path:
            return

        self.save_pdf_requested.emit(Path(file_path))
        self.accept()

    def _save_markdown(self):
        """Request markdown version of the report."""
        file_path, _ = QFileDialog.getSaveFileName(self, "Save Markdown Report", "test_report.md", "Markdown Files (*.md);;All Files (*)")

        if not file_path:
            return

        self.save_markdown_requested.emit(Path(file_path))
        self.accept()

    def _print_pdf(self):
        """Print the PDF document."""
        if not PRINT_SUPPORT_AVAILABLE:
            QMessageBox.information(self, "Print Unavailable", "Print functionality requires PyQt6.QtPrintSupport")
            return

        try:
            # Use system print dialog with file path
            import platform
            import subprocess

            if platform.system() == "Windows":
                subprocess.run(["start", "", str(self.pdf_path)], shell=True)
            elif platform.system() == "Darwin":  # macOS
                subprocess.run(["open", str(self.pdf_path)])
            else:  # Linux
                subprocess.run(["xdg-open", str(self.pdf_path)])

            QMessageBox.information(self, "Print Initiated", "Opening PDF in system default viewer for printing.")

        except Exception as e:
            QMessageBox.critical(self, "Print Error", f"Failed to initiate printing:\n{str(e)}")

    def _copy_to_clipboard(self):
        """Copy PDF file path to clipboard."""
        QApplication.clipboard().setText(str(self.pdf_path.absolute()))

        QMessageBox.information(self, "Copied", "PDF file path copied to clipboard!")

    def closeEvent(self, event):
        """Clean up when dialog closes."""
        if self.pdf_document:
            self.pdf_document.close()
        event.accept()

    def reject(self):
        """Override reject to ensure document is closed."""
        if self.pdf_document:
            self.pdf_document.close()
        super().reject()

    def accept(self):
        """Override accept to ensure document is closed."""
        if self.pdf_document:
            self.pdf_document.close()
        super().accept()
