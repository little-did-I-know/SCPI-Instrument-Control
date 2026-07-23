"""SPD3303X SYSTem:STATus? bit decode (QS0503X-E01B p.41-42).

Vectors below are hand-decoded against the p.42 state-correspondence table:
bit 4 = CH1 output, bit 5 = CH2 output (0 = OFF, 1 = ON).

    0x0224 = 0b1000100100 -> bits {2, 5, 9}    -> CH1 OFF, CH2 ON
             (this is the manual's own "Typical Return" for SYSTem:STATus?)
    0x0014 = 0b0000010100 -> bits {2, 4}       -> CH1 ON,  CH2 OFF
    0x0034 = 0b0000110100 -> bits {2, 4, 5}    -> CH1 ON,  CH2 ON
    0x0004 = 0b0000000100 -> bits {2}          -> CH1 OFF, CH2 OFF
"""

import pytest

from scpi_control.psu_scpi_commands import decode_spd_status


@pytest.mark.parametrize(
    "word,ch1_on,ch2_on",
    [
        ("0x0224", False, True),  # the manual's own Typical Return
        ("0x0014", True, False),
        ("0x0034", True, True),
        ("0x0004", False, False),
    ],
)
def test_output_state_decodes_from_status_word(word, ch1_on, ch2_on):
    state = decode_spd_status(word)
    assert state["ch1_output"] is ch1_on
    assert state["ch2_output"] is ch2_on


def test_garbage_status_word_raises():
    with pytest.raises(ValueError):
        decode_spd_status("banana")
