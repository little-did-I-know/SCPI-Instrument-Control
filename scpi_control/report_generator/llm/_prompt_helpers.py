"""Shared helpers for the report-generator LLM prompt layer.

Holds the single grounding rule and the small string-assembly helpers that the
oscilloscope and DAQ prompt/context modules both use, so they cannot drift.
"""

from typing import Dict

# One grounding rule, embedded in every system prompt (oscilloscope and DAQ) so it
# cannot drift across hand-edited copies. Covers both data sources: the report/
# session context a prompt is given, and any results a tool returned.
_GROUNDING = (
    "Ground every statement in the data available to you — the values in the "
    "report context you were given, or the results a tool returned. Cite specific "
    "values rather than describing them vaguely. Never invent or estimate a value: "
    "if a specific number or detail isn't in the data you have, say so plainly "
    "instead of guessing."
)
