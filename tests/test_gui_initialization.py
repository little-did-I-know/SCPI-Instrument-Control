"""Test GUI initialization and widget creation."""

import pytest
import sys

pytest.importorskip("PyQt6")
from PyQt6.QtWidgets import QApplication


@pytest.fixture(scope="module")
def qapp():
    """Create QApplication instance for tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    yield app


def test_main_window_creation(qapp):
    """Test that MainWindow can be created without errors."""
    from siglent.gui.main_window import MainWindow

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
    from siglent.gui.widgets.waveform_display import WaveformDisplay

    display = WaveformDisplay()
    assert display is not None
    assert hasattr(display, "ax")
    assert hasattr(display, "canvas")
    assert hasattr(display, "cursor_mode")


def test_cursor_panel_creation(qapp):
    """Test that CursorPanel can be created."""
    from siglent.gui.widgets.cursor_panel import CursorPanel

    panel = CursorPanel()
    assert panel is not None
    assert hasattr(panel, "cursor_mode_changed")
    assert hasattr(panel, "clear_cursors")


def test_math_panel_creation(qapp):
    """Test that MathPanel can be created."""
    from siglent.gui.widgets.math_panel import MathPanel

    panel = MathPanel()
    assert panel is not None
    assert hasattr(panel, "math1_expression_changed")
    assert hasattr(panel, "math2_expression_changed")


def test_fft_display_creation(qapp):
    """Test that FFTDisplay can be created."""
    from siglent.gui.widgets.fft_display import FFTDisplay

    display = FFTDisplay()
    assert display is not None
    assert hasattr(display, "fft_compute_requested")


def test_reference_panel_creation(qapp):
    """Test that ReferencePanel can be created."""
    from siglent.gui.widgets.reference_panel import ReferencePanel

    panel = ReferencePanel()
    assert panel is not None
    assert hasattr(panel, "load_reference")
    assert hasattr(panel, "save_reference")


def test_protocol_decode_panel_creation(qapp):
    """Test that ProtocolDecodePanel can be created."""
    from siglent.gui.widgets.protocol_decode_panel import ProtocolDecodePanel

    panel = ProtocolDecodePanel()
    assert panel is not None
    assert hasattr(panel, "decode_requested")
    assert hasattr(panel, "export_requested")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
