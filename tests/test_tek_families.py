"""Per-model coverage for the Tektronix MSO 4/5/6 family (MSO44/46/54/56/58/58LP/64)."""

import pytest

from scpi_control import Oscilloscope, exceptions
from scpi_control.connection.mock import MockConnection
from scpi_control.models import detect_model_from_idn


@pytest.mark.parametrize(
    "model,channels",
    [
        ("MSO44", 4),
        ("MSO46", 6),
        ("MSO54", 4),
        ("MSO56", 6),
        ("MSO58", 8),
        ("MSO58LP", 8),
        ("MSO64", 4),
    ],
)
def test_mso456_models_detected(model, channels):
    cap = detect_model_from_idn(f"TEKTRONIX,{model},C000123,CF:91.1CT FV:2.0")
    assert cap.model_name == model
    assert cap.vendor == "tektronix"
    assert cap.dialect == "tektronix"
    assert cap.scpi_variant == "tek_mso"
    assert cap.num_channels == channels


def test_mso58_connects_with_eight_channels():
    conn = MockConnection(
        "mock",
        idn="TEKTRONIX,MSO58,MOCK0300,CF:91.1CT FV:2.0",
        channel_states={i: True for i in range(1, 9)},
        # An explicit payload keeps this test's expectations deterministic at
        # the wire level, independent of synthesis; channel 8 needs one since
        # the removed fixed default no longer supplies one.
        waveform_payloads={8: bytes([0, 25, 50, 75])},
    )
    scope = Oscilloscope("mock", connection=conn)
    scope.connect()

    assert scope.supported_channels == list(range(1, 9))
    assert scope.channel8._channel == 8

    scope.channel8.voltage_scale = 0.5
    assert "CH8:SCAle 0.5" in conn.writes

    # Waveform acquisition must work on the widest channel, not just channel 1
    waveform = scope.get_waveform(8)
    assert len(waveform.voltage) > 0
    assert "DATa:SOUrce CH8" in conn.writes

    with pytest.raises(exceptions.InvalidParameterError):
        scope.get_waveform(9)

    scope.disconnect()
