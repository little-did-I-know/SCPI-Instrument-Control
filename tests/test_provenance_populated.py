"""Backend review 2026-07-31 finding High-11: four modern queries the real scope
answers (measured fw 3.8.12.1.1.3.6: :CHANnel1:BWLimit? -> 'FULL',
:TIMebase:DELay? -> '0.00E+00', *OPC? -> '1', :CHANnel1:PROBe? -> '1.00E+00',
task 4) raised timeouts on the mock, so every CI provenance channel snapshot
was all-None and no test noticed. Channel.get_configuration() (channel.py)
does not individually try/except its `bandwidth_limit` read the way it does
`probe_ratio`/`unit` -- so a SiglentTimeoutError from an unanswered BWLimit?
propagated out of get_configuration() entirely, was caught by the blanket
per-channel `except Exception` in AcquisitionProvenance.from_scope
(provenance.py), and blanked EVERY field of that channel's snapshot, not just
bandwidth_limit. This file pins the now-populated snapshot so the emptiness
class cannot return silently."""

from scpi_control.connection.mock import MockConnection
from scpi_control.oscilloscope import Oscilloscope

MODERN_IDN = "Siglent Technologies,SDS824X HD,SDS08A0X804831,3.8.12.1.1.3.6"


def test_modern_mock_provenance_channel_snapshot_is_populated():
    conn = MockConnection(idn=MODERN_IDN)
    scope = Oscilloscope("mock", connection=conn)
    scope.connect()
    wf = scope.get_waveform(1)
    ch = wf.provenance.channels[1]
    assert ch.probe_ratio == 1.0
    # channel.py's modern bandwidth_limit getter (channel.py ~L237-241)
    # normalizes the wire FULL/20M/200M vocabulary to the driver's public
    # ON/OFF vocabulary: FULL (no limiting -- the hardware-measured default)
    # maps to public "OFF". "FULL" itself is the wire token, never the
    # public property value, on this dialect.
    assert ch.bandwidth_limit == "OFF"
    assert ch.voltage_scale is not None
    assert ch.voltage_offset is not None
    assert ch.coupling is not None
    assert ch.enabled is not None


def test_modern_mock_answers_opc():
    conn = MockConnection(idn=MODERN_IDN)
    scope = Oscilloscope("mock", connection=conn)
    scope.connect()
    # wait_complete() (oscilloscope.py) queries *OPC? and returns None
    # unconditionally -- the invariant under test is that the query does not
    # raise SiglentTimeoutError, not any particular return value.
    assert scope.wait_complete() is None
