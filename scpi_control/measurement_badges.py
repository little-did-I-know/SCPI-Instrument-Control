"""Badge-based measurements for the modern Tektronix MSO families (2/4/5/6).

These scopes have no MEASUrement:IMMed subsystem. A measurement is a stateful
"badge" that is added to the instrument, configured with a type and source, and
then read -- MSO2 PM 077-1776-07 (p.414/487/483/481/424/430) and 4/5/6 PM
077-1305-11 (p.576/717/709/705/596/607).

The pool keeps one badge per distinct (wire_type, channel) so that repeated
measurements -- the common case, e.g. the gateway polling at ~1 Hz -- cost a
single query after the first call, and so that badges a user created on the
instrument are never reused or deleted.
"""

import logging
import re
from typing import TYPE_CHECKING, Dict, Optional, Set, Tuple

from scpi_control import exceptions
from scpi_control.scpi_commands import channel_token

if TYPE_CHECKING:
    from scpi_control.oscilloscope import Oscilloscope

logger = logging.getLogger(__name__)

# MEASUrement:LIST? answers a comma-separated list of badge names ("MEAS1,MEAS4")
# or NONE when empty; match names wherever they appear so a header echo or a
# different empty-list spelling parses the same way.
_BADGE_NAME_RE = re.compile(r"MEAS(\d+)", re.IGNORECASE)


class BadgePool:
    """Allocates, reuses, and cleans up measurement badges for one scope."""

    def __init__(self, scope: "Oscilloscope"):
        self._scope = scope
        self._badges: Dict[Tuple[str, int], int] = {}
        self._foreign: Optional[Set[int]] = None

    def _discover_foreign(self) -> None:
        """Learn which slots already exist, once, before allocating any."""
        if self._foreign is not None:
            return
        response = self._scope.query(self._scope._get_command("list_badges"))
        self._foreign = {int(m.group(1)) for m in _BADGE_NAME_RE.finditer(response or "")}
        if self._foreign:
            logger.debug(f"Instrument already has badges {sorted(self._foreign)}; allocating around them")

    def _allocate_slot(self) -> int:
        used = set(self._foreign or ()) | set(self._badges.values())
        slot = 1
        while slot in used:
            slot += 1
        return slot

    def value(self, wire_type: str, channel: int) -> float:
        """Return the badge value for `wire_type` on `channel`, creating the badge once."""
        key = (wire_type, channel)
        slot = self._badges.get(key)
        if slot is None:
            self._discover_foreign()
            slot = self._allocate_slot()
            self._scope.write(self._scope._get_command("add_measurement_badge", n=slot))
            self._scope.write(self._scope._get_command("set_badge_type", n=slot, type=wire_type))
            self._scope.write(self._scope._get_command("set_badge_source", n=slot, src=channel_token(self._scope.dialect, channel)))
            self._badges[key] = slot
            logger.debug(f"Allocated badge MEAS{slot} for {wire_type} on channel {channel}")

        response = self._scope.query(self._scope._get_command("get_badge_value", n=slot))
        try:
            return float(response.strip())
        except (AttributeError, ValueError):
            raise exceptions.CommandError(
                f"Badge MEAS{slot} ({wire_type} on channel {channel}) returned {response!r}, which is not a number. "
                "Badge results accumulate across acquisitions, so the scope may need a running acquisition."
            )

    def cleanup(self) -> None:
        """Delete only the badges this pool created. Best-effort: the link may be gone."""
        for slot in self._badges.values():
            try:
                self._scope.write(self._scope._get_command("delete_badge", n=slot))
            except Exception as e:
                logger.debug(f"Could not delete badge MEAS{slot}: {e}")
        self._badges.clear()
        self._foreign = None
