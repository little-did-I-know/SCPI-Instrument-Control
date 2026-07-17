"""The tools the local model calls to inspect a loaded report.

These need no LLM, no mock and no network: ReportTools is pure CPU over
in-memory arrays. The schema tests at the bottom are the ones that keep the
signature discipline honest -- see their docstrings.
"""

from datetime import datetime

import numpy as np
import pytest

from scpi_control.report_generator.llm.tools import MAX_PLATEAUS, MAX_TRANSIENTS, ReportTools
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


def test_analyze_waveform_unknown_channel_tags_each_option_with_its_section():
    """A two-section report answering an unknown channel with a bare "C1, C1"
    would invite the exact "two separately addressable C1s" misconception the
    section-naming fix exists to prevent. Each available channel must be tagged
    with the section it came from."""
    with pytest.raises(ValueError) as exc:
        ReportTools(make_two_section_report()).analyze_waveform("C9")
    message = str(exc.value)
    assert "Rise Time Test" in message
    assert "Overshoot Test" in message


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


def make_square(channel="C1", n=4000, rate=1e6, freq=500.1):
    """A clean square wave, ~2 cycles over 4000 samples -> a few long plateaus
    (well under MAX_PLATEAUS, so nothing truncates and both plateau_high and
    plateau_low show). Raise freq to force many plateaus.

    Note: detect_plateaus thresholds at median(v) +/- 0.3*std(v). A perfect +-1
    square wave is bimodal, so that threshold only splits both polarities apart
    when the high/low sample counts are exactly equal (median lands on 0);
    otherwise the median snaps entirely to whichever side has one more sample
    and the other polarity is never detected. At an exact divisor like 500 Hz
    every zero-crossing lands on an integer sample index and ties into the high
    side (`>= 0`), which is why 500.1 Hz -- not 500 Hz -- is the default: it
    avoids that exact tie so both plateau_high and plateau_low actually appear.

    Also note: detect_plateaus requires each plateau to last >= 1% of the record,
    so a high-frequency square whose half-periods fall below that yields NO
    plateaus -- keep freq low enough that half_period_samples =
    rate/(2*freq) >> n*0.01."""
    t = np.arange(n) / rate
    v = np.where(np.sin(2 * np.pi * freq * t) >= 0, 1.0, -1.0)
    return WaveformData(channel=channel, time=t, voltage=v, sample_rate=rate, record_length=n)


def make_flatless(channel="C1", n=2000, rate=1e6, freq=50_000):
    """A fast sine: its arcs above threshold are too brief to register as plateaus
    (detect_plateaus -> none), and a pure sine's slope never crosses detect_edges'
    2-sigma derivative threshold (detect_edges -> none). One deterministic 'empty'
    fixture for both the no-plateaus and no-edges cases."""
    t = np.arange(n) / rate
    return WaveformData(channel=channel, time=t, voltage=np.sin(2 * np.pi * freq * t), sample_rate=rate, record_length=n)


def report_of(waveform):
    return make_report(waveforms=[waveform])


def test_analyze_plateaus_reports_slope_per_plateau():
    out = ReportTools(report_of(make_square())).analyze_plateaus("C1")
    assert "plateau_high" in out and "plateau_low" in out
    assert "slope=" in out and "V/s" in out
    assert "channel=C1" in out and "[Captures]" in out


def test_analyze_plateaus_on_a_signal_with_no_plateaus():
    out = ReportTools(report_of(make_flatless())).analyze_plateaus("C1")
    assert "no flat plateaus" in out.lower()


def test_analyze_plateaus_caps_its_output_and_states_the_true_total():
    """A many-cycle square wave yields far more than MAX_PLATEAUS regions. The
    reported total must be true and the truncation stated -- the detect_transients
    lesson: a silent slice teaches the model the signal is simpler than it is."""
    many = make_square(freq=5_000)  # 20 cycles over 4000 samples -> 19 plateaus, well over MAX_PLATEAUS
    out = ReportTools(report_of(many)).analyze_plateaus("C1")
    # Pin the TRUE total, not just the truncation marker: printing "8 found,
    # showing first 8" would still satisfy "showing first" and the bullet count
    # (that is the exact silent-slice regression), so assert the real number.
    assert "19 found, showing first 8" in out
    assert "showing first" in out
    # one plateau line per shown region; count the leading "  plateau_" bullets
    assert out.count("  plateau_") == MAX_PLATEAUS


def test_analyze_plateaus_does_not_mutate_the_report():
    """Read-only: the tool must never append to waveform.regions."""
    report = report_of(make_square())
    waveform = report.sections[0].waveforms[0]
    before = len(waveform.regions)
    ReportTools(report).analyze_plateaus("C1")
    assert len(waveform.regions) == before


def test_list_edges_reports_rising_and_falling_edges():
    out = ReportTools(report_of(make_square())).list_edges("C1")
    assert "rising" in out and "falling" in out
    assert "µs" in out
    assert "channel=C1" in out and "[Captures]" in out


def test_list_edges_names_the_cap_so_the_model_can_raise_it():
    """detect_edges gives no true total, so the honest signal is the cap itself:
    if the model sees as many edges as it asked for, it can ask for more."""
    out = ReportTools(report_of(make_square())).list_edges("C1", max_edges=2)
    assert "max_edges=2" in out


def test_list_edges_on_a_flat_signal():
    out = ReportTools(report_of(make_flatless())).list_edges("C1")
    assert "no edges" in out.lower()


def test_list_edges_rejects_an_out_of_range_max_edges():
    """ollama strips numeric bounds from the schema, so the dispatcher is the only
    real guard."""
    with pytest.raises(ValueError):
        ReportTools(report_of(make_square())).list_edges("C1", max_edges=99)


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
