"""Badge-based measurements for the modern Tektronix MSO families (2/4/5/6).

These scopes have no MEASUrement:IMMed subsystem. A measurement is a stateful
"badge" that is added to the instrument, configured with a type and source, and
then read -- MSO2 PM 077-1776-07 (ADDNew p.2-395, TYPe p.2-468, SOUrce p.2-464,
RESUlts p.2-462, DELete p.2-405, LIST p.2-411) and 4/5/6 PM 077-1305-11
(ADDNew p.2-561, TYPe p.2-702, SOUrce p.2-694, RESUlts p.2-690, DELete p.2-581,
LIST p.2-592).

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
    """Allocates, reuses, and cleans up measurement badges for one scope.

    Two sets track slot state for different purposes, and must not be
    conflated:

    - `_created` records every slot for which the `ADDNew` write has
      succeeded, regardless of whether the type/source configuration that
      follows also succeeds. This is the cleanup ledger: a badge that exists
      on the instrument, even half-configured, must be deleted on disconnect
      or it leaks.
    - `_badges` records slots that are fully configured (type and source both
      written) and therefore safe to *reuse* for a matching (wire_type,
      channel) query without re-issuing any configuration writes. A slot only
      earns a `_badges` entry after all three writes (ADDNew, TYPe, SOUrce)
      succeed -- if configuration is interrupted partway, the slot stays out
      of `_badges` so a later call reconfigures it from scratch rather than
      silently reading a badge whose type was never set.
    """

    def __init__(self, scope: "Oscilloscope"):
        self._scope = scope
        self._badges: Dict[Tuple[str, int], int] = {}
        self._created: Set[int] = set()
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
        used = set(self._foreign or ()) | self._created | set(self._badges.values())
        slot = 1
        while slot in used:
            slot += 1
        return slot

    def value(self, wire_type: str, channel: int) -> float:
        """Return the badge value for `wire_type` on `channel`, creating the badge once.

        A slot is only considered "configured" -- and therefore eligible for
        reuse via `_badges` -- once ADDNew, TYPe, and SOUrce have all been
        written successfully. If a write fails partway through, the slot
        already exists on the instrument (tracked in `_created` so `cleanup()`
        still deletes it) but is deliberately left out of `_badges`, so the
        next call configures it from scratch instead of reading a badge whose
        type was never set.
        """
        key = (wire_type, channel)
        slot = self._badges.get(key)
        if slot is None:
            self._discover_foreign()
            slot = self._allocate_slot()
            self._scope.write(self._scope._get_command("add_measurement_badge", n=slot))
            self._created.add(slot)
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
        """Delete every badge this pool created, configured or not. Best-effort: the link may be gone.

        Iterates `_created | _badges.values()` rather than just `_badges`
        alone so a slot whose ADDNew succeeded but whose TYPe/SOUrce write
        failed -- and which therefore never earned a `_badges` entry -- is
        still deleted instead of leaking on the instrument.
        """
        for slot in self._created | set(self._badges.values()):
            try:
                self._scope.write(self._scope._get_command("delete_badge", n=slot))
            except Exception as e:
                logger.debug(f"Could not delete badge MEAS{slot}: {e}")
        self._created.clear()
        self._badges.clear()
        self._foreign = None
