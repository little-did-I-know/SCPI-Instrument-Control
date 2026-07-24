"""Test GUI initialization and widget creation."""

import sys

import numpy as np
import pytest

pytest.importorskip("PyQt6")
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication


class _Waveform:
    """Minimal stand-in for a captured waveform, just enough for save_reference."""

    def __init__(self):
        self.time = np.linspace(0, 1, 16)
        self.voltage = np.sin(self.time)
        self.channel = 1


@pytest.fixture(scope="module")
def qapp():
    """Create QApplication instance for tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    yield app


def test_main_window_creation(qapp):
    """Test that MainWindow can be created without errors."""
    from scpi_control.gui.main_window import MainWindow

    # This should not raise any AttributeError
    window = MainWindow()

    # Verify critical attributes exist
    assert hasattr(window, "waveform_display"), "waveform_display not created"
    assert hasattr(window, "channel_control"), "channel_control not created"
    assert hasattr(window, "cursor_panel"), "cursor_panel not created"
    assert hasattr(window, "math_panel"), "math_panel not created"
    assert hasattr(window, "fft_display"), "fft_display not created"
    assert hasattr(window, "reference_panel"), "reference_panel not created"
    assert hasattr(window, "protocol_decode_panel"), "protocol_decode_panel not created"

    # Verify waveform_display is created before cursor_panel connections
    assert window.waveform_display is not None

    window.close()


def test_waveform_display_creation(qapp):
    """Test that WaveformDisplay can be created."""
    from scpi_control.gui.widgets.waveform_display import WaveformDisplay

    display = WaveformDisplay()
    assert display is not None
    assert hasattr(display, "ax")
    assert hasattr(display, "canvas")
    assert hasattr(display, "cursor_mode")


def test_cursor_panel_creation(qapp):
    """Test that CursorPanel can be created."""
    from scpi_control.gui.widgets.cursor_panel import CursorPanel

    panel = CursorPanel()
    assert panel is not None
    assert hasattr(panel, "cursor_mode_changed")
    assert hasattr(panel, "clear_cursors")


def test_math_panel_creation(qapp):
    """Test that MathPanel can be created."""
    from scpi_control.gui.widgets.math_panel import MathPanel

    panel = MathPanel()
    assert panel is not None
    assert hasattr(panel, "math1_expression_changed")
    assert hasattr(panel, "math2_expression_changed")


def test_fft_display_creation(qapp):
    """Test that FFTDisplay can be created."""
    from scpi_control.gui.widgets.fft_display import FFTDisplay

    display = FFTDisplay()
    assert display is not None
    assert hasattr(display, "fft_compute_requested")


def test_reference_panel_creation(qapp):
    """Test that ReferencePanel can be created."""
    from scpi_control.gui.widgets.reference_panel import ReferencePanel

    panel = ReferencePanel()
    assert panel is not None
    assert hasattr(panel, "load_reference")
    assert hasattr(panel, "save_reference")


def test_reference_panel_list_items_carry_loadable_names(qapp, tmp_path):
    """The panel must feed load_reference/delete_reference a short *name*.

    reference_waveform._find_reference_file now confines lookups to
    storage_dir (the RCE-closing security fix) and no longer accepts the
    absolute filepath that list_references() also returns. If
    ReferencePanel.update_reference_list ever goes back to storing
    ref["filepath"] as a list item's payload -- which is what the Load and
    Delete buttons emit -- load_reference/delete_reference silently return
    None/False for every reference, with no exception raised. Reproduce that
    failure mode at the panel+store boundary here instead of relying on a
    human clicking the button and finding nothing happens.
    """
    from scpi_control.gui.widgets.reference_panel import ReferencePanel
    from scpi_control.reference_waveform import ReferenceWaveform

    store = ReferenceWaveform(str(tmp_path))
    store.save_reference(_Waveform(), "panel-ref")

    panel = ReferencePanel()
    panel.update_reference_list(store.list_references())

    item = panel.reference_list.item(0)
    payload = item.data(Qt.ItemDataRole.UserRole)

    # This is exactly what _on_load_reference_item/_on_delete_reference emit
    # via the load_reference/delete_reference signals.
    loaded = store.load_reference(payload)
    assert loaded is not None
    assert loaded["metadata"]["name"] == "panel-ref"

    assert store.delete_reference(payload) is True


def test_protocol_decode_panel_creation(qapp):
    """Test that ProtocolDecodePanel can be created."""
    from scpi_control.gui.widgets.protocol_decode_panel import ProtocolDecodePanel

    panel = ProtocolDecodePanel()
    assert panel is not None
    assert hasattr(panel, "decode_requested")
    assert hasattr(panel, "export_requested")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
