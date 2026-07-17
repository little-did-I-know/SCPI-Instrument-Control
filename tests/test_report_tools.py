"""The tools the local model calls to inspect a loaded report.

These need no LLM, no mock and no network: ReportTools is pure CPU over
in-memory arrays. The schema tests at the bottom are the ones that keep the
signature discipline honest -- see their docstrings.
"""

from datetime import datetime

import numpy as np
import pytest

from scpi_control.report_generator.llm.tools import MAX_TRANSIENTS, ReportTools
from scpi_control.report_generator.models.report_data import (
    MeasurementResult,
    ReportMetadata,
    TestReport,
    TestSection,
    WaveformData,
)


def make_waveform(channel="C1", n=2000, rate=1e6, freq=10_000, label=None):
    t = np.arange(n) / rate
    return WaveformData(
        channel=channel,
        time=t,
        voltage=np.sin(2 * np.pi * freq * t),
        sample_rate=rate,
        record_length=n,
        label=label,
    )


def make_report(waveforms=None, measurements=None):
    section = TestSection(
        title="Captures",
        content="Bench run.",
        waveforms=[make_waveform()] if waveforms is None else list(waveforms),
        measurements=[] if measurements is None else list(measurements),
    )
    return TestReport(
        metadata=ReportMetadata(title="Bench Check", technician="robin", test_date=datetime(2026, 7, 16)),
        sections=[section],
    )


def test_functions_returns_exactly_the_four_tools():
    names = [fn.__name__ for fn in ReportTools(make_report()).functions()]
    assert names == ["list_waveforms", "analyze_waveform", "detect_transients", "list_measurements"]


def test_list_waveforms_names_every_channel():
    tools = ReportTools(make_report(waveforms=[make_waveform("C1"), make_waveform("C2")]))
    out = tools.list_waveforms()
    assert "C1" in out and "C2" in out


def test_list_waveforms_on_a_report_with_none():
    assert "no waveforms" in ReportTools(make_report(waveforms=[])).list_waveforms().lower()


def make_two_section_report():
    """The normal shape of a real report: several sections each capturing C1."""
    return TestReport(
        metadata=ReportMetadata(title="Bench Check", technician="robin", test_date=datetime(2026, 7, 16)),
        sections=[
            TestSection(title="Rise Time Test", waveforms=[make_waveform("C1")]),
            TestSection(title="Overshoot Test", waveforms=[make_waveform("C1")]),
        ],
    )


def test_list_waveforms_distinguishes_the_same_channel_in_two_sections():
    """Two bare "C1:" rows would read as a duplicate or a bug. The section is
    what tells them apart."""
    out = ReportTools(make_two_section_report()).list_waveforms()

    assert "Rise Time Test" in out and "Overshoot Test" in out


def test_analyze_waveform_names_the_section_it_actually_used():
    """Only the first C1 is reachable, so the result must say which capture it
    is. Silently analyzing Rise Time while the model believes it asked about
    Overshoot is the failure this prevents."""
    out = ReportTools(make_two_section_report()).analyze_waveform("C1")

    assert "Rise Time Test" in out
    assert "Overshoot Test" not in out


def test_detect_transients_names_the_section_it_actually_used():
    out = ReportTools(make_two_section_report()).detect_transients("C1")

    assert "Rise Time Test" in out
    assert "Overshoot Test" not in out


def test_analyze_waveform_identifies_a_sine():
    """The payload: the model can reach signal-type detection, which the
    eight-scalar context could never express."""
    out = ReportTools(make_report()).analyze_waveform("C1")
    assert "signal_type" in out
    assert "sine" in out.lower()


def test_analyze_waveform_formats_values_with_units():
    """Tool results reuse the report's own unit-aware formatter, so the model
    reads the same units a human does."""
    out = ReportTools(make_report()).analyze_waveform("C1")
    assert "kHz" in out or "Hz" in out


def test_analyze_waveform_unknown_channel_lists_the_valid_ones():
    """The error is data for the model: it must be able to recover by itself."""
    with pytest.raises(ValueError) as exc:
        ReportTools(make_report()).analyze_waveform("C9")
    assert "C9" in str(exc.value) and "C1" in str(exc.value)


def test_tool_results_echo_their_arguments():
    """Ollama tags tool results by tool_name only -- there is no tool_call_id --
    so two parallel calls to one tool are indistinguishable at the protocol
    level. Echoing the arguments is what lets the model tell them apart."""
    out = ReportTools(make_report()).analyze_waveform("C1")
    assert "channel=C1" in out


def test_detect_transients_reports_none_on_a_clean_sine():
    out = ReportTools(make_report()).detect_transients("C1")
    assert "none" in out.lower()


def test_detect_transients_caps_its_output_and_says_so(bursty_waveform):
    """A noisy capture can produce hundreds of transients and blow the context.
    Truncation must be stated: silently returning 10 of 400 teaches the model the
    signal is cleaner than it is.

    The TOTAL is the load-bearing half. Reporting "10 found, showing first 10"
    on a 20-transient capture would announce truncation while still lying about
    the size of what was dropped, so the count is pinned exactly, not just its
    presence. Deterministic: the fixture's spikes are placed by linspace, not RNG.
    """
    out = ReportTools(make_report(waveforms=[bursty_waveform])).detect_transients("C1")

    assert "20 found, showing first 10" in out
    assert out.count("µs") == MAX_TRANSIENTS


def test_detect_transients_rejects_an_out_of_range_sensitivity():
    """ollama strips minimum/maximum from tool schemas, so out-of-range values
    arrive no matter what we declare. The dispatcher is the only real bound."""
    with pytest.raises(ValueError):
        ReportTools(make_report()).detect_transients("C1", sensitivity=99.0)


def test_list_measurements_reports_pass_and_fail():
    measurements = [
        MeasurementResult(name="Rise Time", value=1.2e-9, unit="s", channel="C1", passed=True),
        MeasurementResult(name="Overshoot", value=12.0, unit="%", channel="C1", passed=False),
    ]
    out = ReportTools(make_report(measurements=measurements)).list_measurements()
    assert "PASS" in out and "FAIL" in out
    assert "Rise Time" in out and "Overshoot" in out


def test_list_measurements_on_a_report_with_none():
    assert "no measurements" in ReportTools(make_report()).list_measurements().lower()


def test_every_tool_has_a_description_and_described_parameters():
    """ollama builds each schema from the signature and the Google-style
    docstring, so both are wire contract. A missing Args: entry means the model
    gets a parameter with no description."""
    convert_function_to_tool = pytest.importorskip("ollama._utils").convert_function_to_tool
    for fn in ReportTools(make_report()).functions():
        tool = convert_function_to_tool(fn)
        assert tool.function.description, f"{fn.__name__} has no description"
        for pname, prop in (tool.function.parameters.properties or {}).items():
            assert prop.description, f"{fn.__name__}.{pname} has no description"


def test_optional_parameters_are_not_marked_required():
    """THE discipline test. ollama marks `x: float = 3.0` REQUIRED despite the
    default; only `Optional[X] = None` escapes, and an unhinted parameter is
    silently typed "string". Every other test here passes either way, so this is
    the only thing standing between the tools and a schema that lies to the model.
    """
    convert_function_to_tool = pytest.importorskip("ollama._utils").convert_function_to_tool
    tool = convert_function_to_tool(ReportTools(make_report()).detect_transients)
    params = tool.function.parameters

    assert set(params.properties) == {"channel", "sensitivity"}
    assert params.required == ["channel"], "sensitivity has a default and must not be required"
    assert params.properties["channel"].type == "string"
    assert params.properties["sensitivity"].type == "number"
