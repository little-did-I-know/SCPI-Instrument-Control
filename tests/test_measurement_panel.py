"""Measurement panel: every offered type resolves through the core measure()
dispatch. This is the load-bearing net for audit H14 -- six types used to render
'---' because the panel built measure_{name} wrappers that don't exist."""

import sys

import pytest

pytest.importorskip("PyQt6")
from PyQt6.QtWidgets import QApplication  # noqa: E402

from scpi_control import Oscilloscope  # noqa: E402
from scpi_control.connection.mock import MockConnection  # noqa: E402
from scpi_control.gui.widgets.measurement_panel import MeasurementPanel  # noqa: E402
from scpi_control.measurement import MeasurementType  # noqa: E402
from typing import get_args  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication(sys.argv)
    yield app


def _mock_scope():
    scope = Oscilloscope("mock", connection=MockConnection())
    scope.connect()
    return scope


def test_every_offered_type_is_a_valid_wire_code():
    valid = set(get_args(MeasurementType))
    for _display, key in MeasurementPanel.MEASUREMENTS:
        assert key in valid, "{0!r} is not a MeasurementType wire code".format(key)


def test_every_offered_type_returns_a_real_value(qapp):
    panel = MeasurementPanel()
    panel.scope = _mock_scope()
    for _display, key in MeasurementPanel.MEASUREMENTS:
        value = panel._get_measurement_value(1, key)
        assert isinstance(value, float), "{0} returned {1!r}, expected a float".format(key, value)


def test_formatter_labels_each_kind(qapp):
    panel = MeasurementPanel()
    assert panel._format_measurement_value("FREQ", 1000.0).endswith("kHz")
    assert panel._format_measurement_value("PER", 1e-3).endswith("ms")
    assert panel._format_measurement_value("DUTY", 50.0).endswith("%")
    assert panel._format_measurement_value("PKPK", 2.0).endswith("V")
    assert panel._format_measurement_value("WID", 5e-3).endswith("ms")


MODERN_IDN = "Siglent Technologies,SDS814X HD,MOCK0001,1.0.0.0"


def _modern_mock_scope():
    scope = Oscilloscope("mock", connection=MockConnection(idn=MODERN_IDN))
    scope.connect()
    return scope


def test_every_offered_type_returns_a_real_value_on_modern(qapp):
    """PR #102's net used a default (legacy) mock, so a modern-dialect break was
    invisible to it -- every one of these raised SiglentTimeoutError."""
    panel = MeasurementPanel()
    panel.scope = _modern_mock_scope()
    for _display, key in MeasurementPanel.MEASUREMENTS:
        value = panel._get_measurement_value(1, key)
        assert isinstance(value, float), "{0} returned {1!r} on the modern dialect".format(key, value)
