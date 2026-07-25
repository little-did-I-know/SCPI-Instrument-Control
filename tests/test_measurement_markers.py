"""GUI measurement markers: shared period estimator and duty-cycle calc."""

import subprocess
import sys
import textwrap

import numpy as np
import pytest

from scpi_control.gui.widgets.measurement_markers.period import estimate_period
from scpi_control.gui.widgets.measurement_markers.timing_marker import TimingMarker


def test_marker_math_imports_without_pyqt6():
    """The period/duty math must import with no Qt installed.

    CI installs `.[dev,web]` (no `gui` extra), so PyQt6 is absent there while it
    is present on a dev machine -- which is how an eager
    `scpi_control/gui/widgets/__init__.py` made this whole module uncollectable
    in CI while every local run stayed green. These marker modules are pure
    numpy/matplotlib; nothing here may drag in Qt.

    Runs in a subprocess with PyQt6 blocked so the guarantee holds even on a
    machine that has PyQt6 installed.
    """
    program = textwrap.dedent("""
        import importlib.abc
        import sys

        class BlockPyQt6(importlib.abc.MetaPathFinder):
            def find_spec(self, fullname, path=None, target=None):
                if fullname == "PyQt6" or fullname.startswith("PyQt6."):
                    raise ModuleNotFoundError("No module named " + repr(fullname))
                return None

        sys.meta_path.insert(0, BlockPyQt6())

        from scpi_control.gui.widgets.measurement_markers.period import estimate_period
        from scpi_control.gui.widgets.measurement_markers.timing_marker import TimingMarker

        assert "PyQt6" not in sys.modules
        """)
    result = subprocess.run([sys.executable, "-c", program], capture_output=True, text=True)
    assert result.returncode == 0, "marker math must import without PyQt6:\n{0}".format(result.stderr)


def _square(periods, duty=0.5, n=2000, period=1e-3, start_high=True):
    """periods full cycles of a duty-fraction square wave over `periods*period` seconds.

    start_high=True (default, used by the period-estimator tests below) begins
    the gate already in the high state. start_high=False begins low instead, so
    the gate contains a complete rising-then-falling pulse -- needed by the duty
    tests, since _calculate_positive_width looks for the first rising edge
    followed by a later falling edge and returns None if the gate opens mid-pulse.
    """
    t = np.linspace(0, periods * period, n, endpoint=False)
    phase = (t % period) / period
    if start_high:
        v = np.where(phase < duty, 1.0, -1.0)
    else:
        v = np.where(phase < (1 - duty), -1.0, 1.0)
    return t, v


def test_estimate_period_of_a_clean_square_wave():
    t, v = _square(periods=5, period=1e-3)
    period = estimate_period(t, v)
    assert period == pytest.approx(1e-3, rel=0.05)


def test_estimate_period_returns_none_on_a_flat_signal():
    t = np.linspace(0, 1e-3, 500)
    v = np.zeros_like(t)  # no edges at all
    assert estimate_period(t, v) is None


def test_estimate_period_returns_none_below_one_cycle():
    # Three quarters of a cycle: one falling transition, no rising zero-crossing
    # and no detectable peak -> not enough to measure a period.
    #
    # (A naive half-cycle slice at duty=0.5 lands entirely within the initial
    # high plateau -- a flat array indistinguishable from the "no edges at
    # all" case above. 0.75 cycles guarantees the slice actually contains an
    # edge while still falling short of the two crossings a period needs.)
    t, v = _square(periods=0.75, period=1e-3)
    assert estimate_period(t, v) is None


def test_duty_cycle_uses_the_true_period_over_a_multi_period_gate():
    # 3 periods of a 50% square wave. The old code divided the first pulse width
    # by the 3-period gate span -> ~16.7%. The fix divides by one true period.
    t, v = _square(periods=3, duty=0.5, period=1e-3, start_high=False)
    marker = TimingMarker.__new__(TimingMarker)  # logic-only; no Qt construction
    duty = marker._calculate_duty_cycle(t, v)
    assert duty == pytest.approx(50.0, abs=2.0)


def test_duty_cycle_reads_a_25_percent_wave_correctly():
    t, v = _square(periods=3, duty=0.25, period=1e-3, start_high=False)
    marker = TimingMarker.__new__(TimingMarker)
    assert marker._calculate_duty_cycle(t, v) == pytest.approx(25.0, abs=3.0)


def test_duty_cycle_is_none_when_no_period_is_detectable():
    t = np.linspace(0, 1e-3, 500)
    v = np.zeros_like(t)
    marker = TimingMarker.__new__(TimingMarker)
    assert marker._calculate_duty_cycle(t, v) is None
