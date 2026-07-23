"""Vendor-neutral formatting helpers shared by the mock connection shell and every
personality module. Lives separately so personality modules never need to import
from `base` (which imports these helpers), avoiding an import cycle."""

from __future__ import annotations


def _format_scientific(value: float, unit: str) -> str:
    """Format a numeric value with a unit using Siglent-style scientific notation."""
    return f"{value:.2E}{unit}"


def _format_nr3(value: float) -> str:
    """Format a bare NR3 numeric value (no unit) as used by modern-dialect queries."""
    return f"{value:.2E}"


def _format_si_sample_rate(value: float) -> str:
    """Format a sample rate the way legacy Siglent scopes do (RC01020-E01C p.117).

    1e9 -> "SARA 1.00GSa", 500e3 -> "SARA 500.00kSa", 1000 -> "SARA 1.00kSa".
    """
    for threshold, letter in ((1e9, "G"), (1e6, "M"), (1e3, "k")):
        if value >= threshold:
            return f"SARA {value / threshold:.2f}{letter}Sa"
    return f"SARA {value:.2f}Sa"


def _build_ieee_block(payload: bytes) -> bytes:
    """Wrap payload in an IEEE-488.2 definite-length block: #<ndigits><length><payload>."""
    length_str = str(len(payload)).encode()
    return b"#" + str(len(length_str)).encode() + length_str + payload


# Minimal valid 1x1 24bpp BMP, so a mock SCDP? screenshot decodes as a real image.
MOCK_SCREENSHOT_BMP = bytes.fromhex("424d3a000000000000003600000028000000010000000100000001001800000000000400000000000000000000000000000000000000ffffff00")
