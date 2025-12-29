"""Test that all modules can be imported without errors."""

import pytest


def test_import_oscilloscope():
    """Test that oscilloscope module imports successfully."""
    from siglent import Oscilloscope

    assert Oscilloscope is not None


def test_import_models():
    """Test that models module imports successfully."""
    from siglent.models import ModelCapability, detect_model_from_idn

    assert ModelCapability is not None
    assert detect_model_from_idn is not None


def test_import_scpi_commands():
    """Test that SCPI commands module imports successfully."""
    from siglent.scpi_commands import SCPICommandSet

    assert SCPICommandSet is not None


def test_import_math_channel():
    """Test that math channel module imports successfully."""
    from siglent.math_channel import MathChannel, MathOperations

    assert MathChannel is not None
    assert MathOperations is not None


def test_import_analysis():
    """Test that analysis module imports successfully."""
    from siglent.analysis import FFTAnalyzer, FFTResult

    assert FFTAnalyzer is not None
    assert FFTResult is not None


def test_import_protocol_decode():
    """Test that protocol decode module imports successfully."""
    from siglent.protocol_decode import ProtocolDecoder, DecodedEvent, EventType

    assert ProtocolDecoder is not None
    assert DecodedEvent is not None
    assert EventType is not None


def test_import_protocol_decoders():
    """Test that protocol decoders import successfully."""
    from siglent.protocol_decoders import I2CDecoder, SPIDecoder, UARTDecoder

    assert I2CDecoder is not None
    assert SPIDecoder is not None
    assert UARTDecoder is not None


def test_import_reference_waveform():
    """Test that reference waveform module imports successfully."""
    from siglent.reference_waveform import ReferenceWaveform

    assert ReferenceWaveform is not None


def test_import_gui_main_window():
    """Test that main window imports successfully."""
    pytest.importorskip("PyQt6")
    try:
        from siglent.gui.main_window import MainWindow
    except ImportError as exc:  # noqa: PERF203
        pytest.skip(f"Skipping GUI import tests due to missing Qt runtime: {exc}")

    assert MainWindow is not None


def test_import_gui_widgets():
    """Test that GUI widgets import successfully."""
    pytest.importorskip("PyQt6")
    try:
        from siglent.gui.widgets.waveform_display import WaveformDisplay
        from siglent.gui.widgets.channel_control import ChannelControl
        from siglent.gui.widgets.cursor_panel import CursorPanel
        from siglent.gui.widgets.math_panel import MathPanel
        from siglent.gui.widgets.fft_display import FFTDisplay
        from siglent.gui.widgets.reference_panel import ReferencePanel
        from siglent.gui.widgets.protocol_decode_panel import ProtocolDecodePanel
    except ImportError as exc:  # noqa: PERF203
        pytest.skip(f"Skipping GUI widget import tests due to missing Qt runtime: {exc}")

    assert WaveformDisplay is not None
    assert ChannelControl is not None
    assert CursorPanel is not None
    assert MathPanel is not None
    assert FFTDisplay is not None
    assert ReferencePanel is not None
    assert ProtocolDecodePanel is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
