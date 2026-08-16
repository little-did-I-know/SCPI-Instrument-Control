"""Form-based annotation editor for one waveform.

Positioning without a click-on-plot canvas: an "Anchor to..." combo offers every
feature that genuinely has coordinates, and selecting one fills the X and Y boxes,
which stay editable. Nothing requires an anchor -- coordinates can be typed.
"""

import logging
from typing import Optional

from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from scpi_control.report_generator.models.annotations import (
    KIND_HLINE,
    KIND_LABEL,
    KIND_SPAN,
    KIND_VLINE,
    PlotAnnotation,
)
from scpi_control.report_generator.utils.anchors import build_anchor_choices
from scpi_control.report_generator.utils.annotation_store import save_annotations

logger = logging.getLogger(__name__)

# (display text, kind) in the order the combo shows them.
KIND_CHOICES = (
    ("Text label at a point", KIND_LABEL),
    ("Vertical reference line", KIND_VLINE),
    ("Horizontal reference line", KIND_HLINE),
    ("Shaded span", KIND_SPAN),
)


class AnnotationDialog(QDialog):
    """Add, edit and delete a waveform's plot annotations."""

    def __init__(self, waveform, parent=None):
        super().__init__(parent)
        self.waveform = waveform
        self.setWindowTitle(f"Annotations — {waveform.label}")
        self.resize(720, 480)
        self._build_ui()
        self._populate_anchors()
        self._refresh_list()

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        columns = QHBoxLayout()

        self.annotation_list = QListWidget()
        self.annotation_list.currentRowChanged.connect(self._on_row_selected)
        columns.addWidget(self.annotation_list, 1)

        form = QFormLayout()
        self.kind_combo = QComboBox()
        for text, kind in KIND_CHOICES:
            self.kind_combo.addItem(text, kind)
        self.kind_combo.currentIndexChanged.connect(self._on_kind_changed)
        form.addRow("Kind:", self.kind_combo)

        self.text_edit = QLineEdit()
        form.addRow("Text:", self.text_edit)

        self.anchor_combo = QComboBox()
        self.anchor_combo.currentIndexChanged.connect(self._on_anchor_selected)
        form.addRow("Anchor to:", self.anchor_combo)

        self.x_spin = self._make_spin("s")
        form.addRow("X (seconds):", self.x_spin)
        self.y_spin = self._make_spin("V")
        form.addRow("Y (volts):", self.y_spin)
        self.x_end_spin = self._make_spin("s")
        self.x_end_label = QLabel("X end (seconds):")
        form.addRow(self.x_end_label, self.x_end_spin)

        self.arrow_check = QCheckBox("Draw an arrow to the point")
        self.arrow_check.setChecked(True)
        form.addRow("", self.arrow_check)

        self.caption_edit = QLineEdit(self.waveform.caption or "")
        form.addRow("Figure caption:", self.caption_edit)

        columns.addLayout(form, 2)
        outer.addLayout(columns)

        buttons = QHBoxLayout()
        for text, slot in (("Add", self._on_add), ("Update", self._on_update), ("Delete", self._on_delete), ("Save to file", self._on_save)):
            button = QPushButton(text)
            button.clicked.connect(slot)
            buttons.addWidget(button)
        outer.addLayout(buttons)

        box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        box.rejected.connect(self._on_close)
        outer.addWidget(box)

        # `finished` is emitted by done(), which every exit path -- the Close
        # button (accept/reject), Escape, and the OS titlebar X (whose default
        # closeEvent calls reject() directly, never touching the button box's
        # rejected signal) -- goes through. One connection here means a typed
        # caption is never lost regardless of how the dialog was closed.
        # _apply_caption() is idempotent, so also running it from _on_close is
        # harmless.
        self.finished.connect(lambda _result: self._apply_caption())

        self._on_kind_changed()

    def _make_spin(self, suffix: str) -> QDoubleSpinBox:
        spin = QDoubleSpinBox()
        spin.setDecimals(9)
        spin.setRange(-1e9, 1e9)
        spin.setSuffix(f" {suffix}")
        return spin

    def _populate_anchors(self) -> None:
        self.anchor_combo.addItem("(type coordinates)", None)
        for label, x, y in build_anchor_choices(self.waveform):
            self.anchor_combo.addItem(label, (x, y))

    def _refresh_list(self) -> None:
        self.annotation_list.clear()
        for annotation in self.waveform.annotations:
            self.annotation_list.addItem(self._describe(annotation))

    @staticmethod
    def _describe(annotation: PlotAnnotation) -> str:
        if annotation.kind == KIND_HLINE:
            return f"{annotation.kind}: {annotation.text!r} @ {annotation.y:.4g} V"
        if annotation.kind == KIND_SPAN:
            return f"{annotation.kind}: {annotation.text!r} @ {annotation.x*1e6:.3f}–{annotation.x_end*1e6:.3f} us"
        return f"{annotation.kind}: {annotation.text!r} @ {annotation.x*1e6:.3f} us"

    def _current_kind(self) -> str:
        return self.kind_combo.currentData()

    def _on_kind_changed(self) -> None:
        kind = self._current_kind()
        self.x_spin.setEnabled(kind != KIND_HLINE)
        self.y_spin.setEnabled(kind in (KIND_LABEL, KIND_HLINE))
        self.arrow_check.setEnabled(kind == KIND_LABEL)
        show_end = kind == KIND_SPAN
        self.x_end_spin.setVisible(show_end)
        self.x_end_label.setVisible(show_end)

    def _on_anchor_selected(self) -> None:
        anchor = self.anchor_combo.currentData()
        if anchor is None:
            return
        x, y = anchor
        self.x_spin.setValue(x)
        if y is not None:
            self.y_spin.setValue(y)

    def _build_annotation(self) -> Optional[PlotAnnotation]:
        kind = self._current_kind()
        try:
            return PlotAnnotation(
                kind=kind,
                text=self.text_edit.text(),
                x=self.x_spin.value() if kind != KIND_HLINE else None,
                y=self.y_spin.value() if kind in (KIND_LABEL, KIND_HLINE) else None,
                x_end=self.x_end_spin.value() if kind == KIND_SPAN else None,
                arrow=self.arrow_check.isChecked() if kind == KIND_LABEL else None,
            )
        except ValueError as exc:
            QMessageBox.warning(self, "Invalid annotation", str(exc))
            return None

    def _on_add(self) -> None:
        annotation = self._build_annotation()
        if annotation is not None:
            self.waveform.annotations.append(annotation)
            self._refresh_list()

    def _on_update(self) -> None:
        row = self.annotation_list.currentRow()
        if row < 0:
            return
        existing = self.waveform.annotations[row]
        annotation = self._build_annotation()
        if annotation is not None:
            # The form has no widgets for these four -- carry them across from
            # the annotation being replaced so an edit that only touches text
            # or a coordinate doesn't silently reset styling that round-trips
            # through the sidecar via to_dict()/from_dict(). Kind-agnostic, so
            # this is correct even if the user also changed `kind`. Add is
            # unaffected: it always builds fresh with defaults.
            annotation.text_dx = existing.text_dx
            annotation.text_dy = existing.text_dy
            annotation.color = existing.color
            annotation.fontsize = existing.fontsize
            self.waveform.annotations[row] = annotation
            self._refresh_list()
            self.annotation_list.setCurrentRow(row)

    def _on_delete(self) -> None:
        row = self.annotation_list.currentRow()
        if row < 0:
            return
        del self.waveform.annotations[row]
        self._refresh_list()

    def _on_row_selected(self, row: int) -> None:
        if row < 0 or row >= len(self.waveform.annotations):
            return
        annotation = self.waveform.annotations[row]
        index = self.kind_combo.findData(annotation.kind)
        if index >= 0:
            self.kind_combo.setCurrentIndex(index)
        self.text_edit.setText(annotation.text)
        if annotation.x is not None:
            self.x_spin.setValue(annotation.x)
        if annotation.y is not None:
            self.y_spin.setValue(annotation.y)
        if annotation.x_end is not None:
            self.x_end_spin.setValue(annotation.x_end)
        self.arrow_check.setChecked(True if annotation.arrow is None else annotation.arrow)

    def _apply_caption(self) -> None:
        self.waveform.caption = self.caption_edit.text() or None

    def _on_save(self) -> None:
        self._apply_caption()
        try:
            path = save_annotations([self.waveform])
        except ValueError as exc:
            QMessageBox.warning(self, "Cannot save", str(exc))
            return
        QMessageBox.information(self, "Saved", f"Annotations saved to {path}")

    def _on_close(self) -> None:
        self._apply_caption()
        self.accept()
