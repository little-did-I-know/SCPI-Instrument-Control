"""Regression tests for the I2C and SPI `is None` guards added alongside the
bounded `_sample_at_time`/`_get_bit_at_time` fix (see test_protocol_decode_bounds.py
and AUDIT.md 2026-08-09 L1).

On the I2C and SPI paths, `_get_bit_at_time` samples at literal members of the
same `time` array (via `_detect_edge`), so the out-of-range branch never
trips naturally there -- unlike UART, which computes a sample time by adding
a fractional bit period to an edge time. The guards on these two paths are
deliberate defensive consistency: they match the now-`Optional` signature and
protect against a future change that introduces a computed sample time. These
tests reach the guarded branches by monkeypatching the seam the fix actually
introduced (`_get_bit_at_time`, and `_decode_word` for SPI's own call site)
rather than by contriving a real out-of-range waveform, and assert the
contract: a bit read that returns None must cause the decoder to abandon that
frame/word and emit no event built from the partial read, while any earlier,
fully-read events in the same decode() call must survive.
"""

import numpy as np
import pytest

from scpi_control.protocol_decode import EventType
from scpi_control.protocol_decoders import I2CDecoder, SPIDecoder
from scpi_control.waveform import WaveformData

# ---------------------------------------------------------------------------
# I2C waveform construction
#
# Builds a real, physically-consistent I2C SDA/SCL capture (START, 7-bit
# address, R/W bit, ACK, N data bytes each followed by ACK, STOP) so that an
# unpatched decode() call produces genuine ADDRESS/ACK/DATA/STOP events.
# `_get_bit_at_time` is called exactly once per SCL clock edge consumed by
# `_decode_transaction`, in a fixed, predictable order:
#   address bits 0-6, R/W bit (7), address ACK (8),
#   then per data byte: 8 data bits, 1 data ACK.
# That makes the call index a reliable way to target one specific guarded
# read without needing a signal that is actually truncated.
# ---------------------------------------------------------------------------


def _build_i2c_waveform(address_byte, rw_bit, data_bytes, samples_per_bit=20, dt=1e-6, second_transaction=None):
    """Build (time, sda, scl) arrays encoding one or two full I2C transactions."""
    sda_samples = []
    scl_samples = []

    def append(sda_level, scl_level, n):
        sda_samples.extend([sda_level] * n)
        scl_samples.extend([scl_level] * n)

    def send_bit(bit, last=False):
        # setup: SCL low, SDA set
        append(bit, 0, samples_per_bit // 2)
        # sample: SCL high, SDA held -- this is where the clock edge (and
        # the bit sample) lands
        append(bit, 1, samples_per_bit)
        if not last:
            # teardown: SCL low again before the next bit's setup
            append(bit, 0, samples_per_bit // 2)

    def emit_transaction(addr, rw, dbytes):
        append(1, 1, samples_per_bit)  # idle: SDA/SCL high
        append(0, 1, samples_per_bit)  # START: SDA falls while SCL high

        for b in [(addr >> i) & 1 for i in range(6, -1, -1)]:
            send_bit(b)
        send_bit(rw)
        send_bit(0)  # address ACK

        for bi, byte in enumerate(dbytes):
            for b in [(byte >> i) & 1 for i in range(7, -1, -1)]:
                send_bit(b)
            is_last_byte = bi == len(dbytes) - 1
            # The final data ACK of the transaction skips its teardown so
            # SCL is still high when SDA rises for STOP -- no spurious
            # extra clock edge is introduced.
            send_bit(0, last=is_last_byte)

        append(1, 1, samples_per_bit)  # STOP: SDA rises while SCL still high
        append(1, 1, samples_per_bit)  # idle after

    emit_transaction(address_byte, rw_bit, data_bytes)
    if second_transaction is not None:
        emit_transaction(*second_transaction)

    n = len(sda_samples)
    time = np.arange(n) * dt
    sda = np.array(sda_samples, dtype=float) * 3.3
    scl = np.array(scl_samples, dtype=float) * 3.3
    return time, sda, scl


def _i2c_decoder_and_waveforms(*args, **kwargs):
    time, sda, scl = _build_i2c_waveform(*args, **kwargs)
    decoder = I2CDecoder()
    waveforms = {
        "SDA": WaveformData(time=time, voltage=sda, channel=1),
        "SCL": WaveformData(time=time, voltage=scl, channel=2),
    }
    return decoder, waveforms


def _patch_get_bit_at_time_none_at(monkeypatch, decoder, target_index):
    """Delegate to the real `_get_bit_at_time` for every call except
    `target_index` (0-based, in call order), where it returns None -- as if
    that one sample had fallen outside the captured buffer.
    """
    original = decoder._get_bit_at_time
    call_count = {"n": 0}

    def fake(signal, time, sample_time, threshold):
        idx = call_count["n"]
        call_count["n"] += 1
        if idx == target_index:
            return None
        return original(signal, time, sample_time, threshold)

    monkeypatch.setattr(decoder, "_get_bit_at_time", fake)
    return call_count


# ---------------------------------------------------------------------------
# I2C: early-transaction guards (address bit, R/W bit, address ACK bit)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "call_index,site",
    [
        (0, "address bit"),
        (7, "R/W bit"),
        (8, "address ACK bit"),
    ],
)
def test_i2c_early_bit_none_abandons_transaction_with_no_address_event(monkeypatch, call_index, site):
    """A None read for the address byte, R/W bit, or address ACK must abandon
    the whole transaction before any ADDRESS/ACK/DATA event is built.

    START and STOP still appear: decode() emits both unconditionally around
    `_decode_transaction`, independent of whether the transaction body
    produced anything.
    """
    decoder, waveforms = _i2c_decoder_and_waveforms(0x50, rw_bit=0, data_bytes=[0xAB])
    _patch_get_bit_at_time_none_at(monkeypatch, decoder, call_index)

    events = decoder.decode(waveforms)

    types = [e.event_type for e in events]
    assert EventType.ADDRESS not in types, f"{site}: guard did not abandon the transaction: {events}"
    assert EventType.DATA not in types
    assert types == [EventType.START, EventType.STOP], f"{site}: expected only START/STOP, got {events}"


# ---------------------------------------------------------------------------
# I2C: mid-transaction data guards
# ---------------------------------------------------------------------------


def test_i2c_data_bit_none_abandons_remaining_bytes_but_keeps_earlier_byte(monkeypatch):
    """If a data bit read fails partway through the second byte of a
    transaction, the first byte's DATA/ACK events must survive and the second
    byte must not appear -- a partial second byte is worse than no second
    byte at all.
    """
    decoder, waveforms = _i2c_decoder_and_waveforms(0x50, rw_bit=0, data_bytes=[0xAB, 0xCD])
    # Call order: address(0-6), rw(7), addr-ack(8), byte1 bits(9-16),
    # byte1 ack(17), byte2 bit0(18) <- force this one to None.
    _patch_get_bit_at_time_none_at(monkeypatch, decoder, target_index=18)

    events = decoder.decode(waveforms)

    data_events = [e for e in events if e.event_type == EventType.DATA]
    assert len(data_events) == 1, f"expected only the first byte's DATA event, got {data_events}"
    assert data_events[0].data == 0xAB

    types = [e.event_type for e in events]
    assert types == [
        EventType.START,
        EventType.ADDRESS,
        EventType.ACK,
        EventType.DATA,
        EventType.ACK,
        EventType.STOP,
    ], f"unexpected event sequence: {events}"


def test_i2c_data_ack_none_drops_the_fully_read_data_byte_too(monkeypatch):
    """A data byte can be read completely (all 8 bits in range) and still be
    dropped: the DATA and ACK events for a byte are only appended together,
    after the ACK bit is read successfully. If the ACK bit's sample falls
    out of range, the byte's DATA event must not be emitted either, even
    though every data bit for that byte was read.
    """
    decoder, waveforms = _i2c_decoder_and_waveforms(0x50, rw_bit=0, data_bytes=[0xAB])
    # Call order: address(0-6), rw(7), addr-ack(8), data bits(9-16),
    # data ack(17) <- force this one to None.
    _patch_get_bit_at_time_none_at(monkeypatch, decoder, target_index=17)

    events = decoder.decode(waveforms)

    types = [e.event_type for e in events]
    assert EventType.DATA not in types, f"data byte was reported despite its ACK sample being out of range: {events}"
    assert types == [EventType.START, EventType.ADDRESS, EventType.ACK, EventType.STOP], f"unexpected event sequence: {events}"


# ---------------------------------------------------------------------------
# I2C: cross-transaction retention
# ---------------------------------------------------------------------------


def test_i2c_second_transaction_abandoned_does_not_lose_first_transactions_events(monkeypatch):
    """Two transactions in one capture: the first is fully captured, the
    second's address bit sample falls out of range. The first transaction's
    complete ADDRESS/ACK/DATA/ACK/STOP sequence must be unaffected by the
    second transaction's abandonment -- a guard tripping later in the same
    decode() call must not retroactively lose earlier good events.
    """
    decoder, waveforms = _i2c_decoder_and_waveforms(
        0x50,
        rw_bit=0,
        data_bytes=[0xAB],
        second_transaction=(0x60, 0, [0x11]),
    )
    # The first (1-data-byte) transaction consumes exactly 18 bit reads
    # (7 address + 1 R/W + 1 address-ACK + 8 data bits + 1 data ACK).
    # Call index 18 is therefore the second transaction's first address bit.
    _patch_get_bit_at_time_none_at(monkeypatch, decoder, target_index=18)

    events = decoder.decode(waveforms)

    addresses = [e for e in events if e.event_type == EventType.ADDRESS]
    assert len(addresses) == 1, f"expected exactly the first transaction's ADDRESS event, got {addresses}"
    assert addresses[0].data == {"address": 0x50, "rw": "WRITE"}

    data_events = [e for e in events if e.event_type == EventType.DATA]
    assert len(data_events) == 1
    assert data_events[0].data == 0xAB

    starts = [e for e in events if e.event_type == EventType.START]
    stops = [e for e in events if e.event_type == EventType.STOP]
    assert len(starts) == 2, "both transactions' START events should still be reported"
    assert len(stops) == 2, "both transactions' STOP events should still be reported"


# ---------------------------------------------------------------------------
# SPI waveform construction
#
# Builds a real CS-active period with `num_bits` genuine SCK rising edges
# (mode 0: CPOL=0, CPHA=0). MOSI/MISO content is irrelevant in the tests
# below because `_decode_word` itself is monkeypatched -- only the CS
# boundaries and clock-edge count coming out of the real signal matter, since
# those drive how many words decode() attempts to decode.
# ---------------------------------------------------------------------------


def _build_spi_clock_train(num_bits, samples_per_bit=10, dt=1e-6, include_miso=True):
    sck = []
    cs = []

    def append(sck_level, cs_level, n):
        sck.extend([sck_level] * n)
        cs.extend([cs_level] * n)

    append(0, 1, samples_per_bit)  # idle: CS inactive (high), SCK low

    for i in range(num_bits):
        append(0, 0, samples_per_bit // 2)  # setup: SCK low, CS active
        append(1, 0, samples_per_bit)  # sample edge: SCK rises
        if i != num_bits - 1:
            append(0, 0, samples_per_bit // 2)  # teardown before next bit

    append(1, 0, samples_per_bit // 2)  # hold SCK high a little longer
    append(1, 1, samples_per_bit)  # CS deactivates while SCK still high (no spurious edge)
    append(0, 1, samples_per_bit)  # idle after

    n = len(sck)
    time = np.arange(n) * dt
    sck_v = np.array(sck, dtype=float) * 3.3
    cs_v = np.array(cs, dtype=float) * 3.3
    mosi_v = np.zeros(n)
    miso_v = np.zeros(n) if include_miso else None
    return time, sck_v, mosi_v, miso_v, cs_v


def _spi_decoder_and_waveforms(num_bits, include_miso):
    time, sck, mosi, miso, cs = _build_spi_clock_train(num_bits, include_miso=include_miso)
    decoder = SPIDecoder()
    waveforms = {
        "SCK": WaveformData(time=time, voltage=sck, channel=1),
        "MOSI": WaveformData(time=time, voltage=mosi, channel=2),
        "CS": WaveformData(time=time, voltage=cs, channel=3),
    }
    if include_miso:
        waveforms["MISO"] = WaveformData(time=time, voltage=miso, channel=4)
    return decoder, waveforms


# ---------------------------------------------------------------------------
# SPI: `_decode_word`'s own guard (the call site that reads `_get_bit_at_time`)
# ---------------------------------------------------------------------------


def test_spi_decode_word_returns_none_when_one_bit_is_out_of_range(monkeypatch):
    """`_decode_word` must return None -- not a value built from the bits it
    did manage to read -- if any single bit in the word comes back None.
    This is the guard's own call site (spi_decoder.py, inside `_decode_word`),
    tested directly against the seam the fix introduced.
    """
    decoder = SPIDecoder()
    time = np.linspace(0.0, 1e-3, 100)
    signal = np.full_like(time, 3.3)  # constant high; content doesn't matter
    clock_edges = [time[10], time[20], time[30]]

    original = decoder._get_bit_at_time

    def fake(sig, t, sample_time, threshold):
        if sample_time == clock_edges[1]:
            return None
        return original(sig, t, sample_time, threshold)

    monkeypatch.setattr(decoder, "_get_bit_at_time", fake)

    result = decoder._decode_word(signal, time, clock_edges, threshold=1.4, bit_order="MSB")

    assert result is None


# ---------------------------------------------------------------------------
# SPI: decode()'s guards over `_decode_word`'s result
# ---------------------------------------------------------------------------


def test_spi_second_word_mosi_none_abandons_transaction_but_keeps_first_word(monkeypatch):
    """A transaction with two words, no MISO: the first word decodes, the
    second word's MOSI decode returns None. decode() must report only the
    first word's DATA event and stop -- not skip ahead to look for further
    words in the transaction.
    """
    decoder, waveforms = _spi_decoder_and_waveforms(num_bits=16, include_miso=False)

    calls = {"n": 0}
    results = [0xA5, None]

    def fake_decode_word(signal, time, clock_edges, threshold, bit_order):
        idx = calls["n"]
        calls["n"] += 1
        return results[idx]

    monkeypatch.setattr(decoder, "_decode_word", fake_decode_word)

    events = decoder.decode(waveforms, bits_per_word=8)

    data_events = [e for e in events if e.event_type == EventType.DATA]
    assert len(data_events) == 1, f"expected only the first word's DATA event, got {data_events}"
    assert data_events[0].data == {"mosi": 0xA5}


def test_spi_second_word_miso_none_drops_that_word_despite_good_mosi_but_keeps_first(monkeypatch):
    """A transaction with two words, MISO present: the first word decodes
    fully on both lines. The second word's MOSI decodes fine, but its MISO
    decode returns None. decode() must not emit an event for the second word
    using only its (valid) MOSI value -- a word is reported as a whole or not
    at all -- while the first word's complete event must still be present.
    """
    decoder, waveforms = _spi_decoder_and_waveforms(num_bits=16, include_miso=True)

    calls = {"n": 0}
    # word1: mosi, miso both decode; word2: mosi decodes, miso does not.
    results = [0x5A, 0xC3, 0x11, None]

    def fake_decode_word(signal, time, clock_edges, threshold, bit_order):
        idx = calls["n"]
        calls["n"] += 1
        return results[idx]

    monkeypatch.setattr(decoder, "_decode_word", fake_decode_word)

    events = decoder.decode(waveforms, bits_per_word=8)

    data_events = [e for e in events if e.event_type == EventType.DATA]
    assert len(data_events) == 1, f"expected only the first word's DATA event, got {data_events}"
    assert data_events[0].data == {"mosi": 0x5A, "miso": 0xC3}
    assert not any(e.data == {"mosi": 0x11} for e in events), "second word's good MOSI value must not leak into an event on its own"
