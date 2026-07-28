"""Short-lived invitations that redeem into a real token.

An invitation is the only credential that ever leaves the gateway host. It
carries two redeemers for one grant: a long random nonce for a clickable link,
and a six-digit code that can be read down a phone. Both expire in ten minutes
and both are consumed on first use, so a leaked chat message is worthless
almost immediately.

Storage is a file, not process memory, because `scpi-web invite` runs in a
different process from the serving gateway.

The two redeemers are stored differently, deliberately. The link nonce is 32
random bytes and is hashed for the same reason tokens are (see auth.py). The
code is stored in the clear: hashing a secret drawn from a space of 10**6
would be theater, since anyone who can read this file can enumerate every
possible hash in well under a second. The code's real defenses are its
lifetime, the failure limiter on /api/join, and the 0600 file mode. Hashing it
would only make the code look safer than it is.
"""

import hmac
import json
import secrets
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from scpi_control.server.auth import DEFAULT_CONFIG_DIR, _atomic_write_json, _hash, _stat_key

INVITATION_TTL_SECONDS = 600.0
CODE_DIGITS = 6


def format_code(code: str) -> str:
    """Group a code for reading aloud: "417902" -> "417 902"."""
    half = len(code) // 2
    return code[:half] + " " + code[half:]


def _normalize_code(value: str) -> str:
    """Accept the code however it comes back: spaces, hyphens, stray padding.

    The ASCII set is written out rather than using ``str.isdigit()`` on
    purpose, and must stay that way. ``"²".isdigit()`` and ``"٣".isdigit()``
    are both True, but ``hmac.compare_digest`` raises TypeError on a str with
    any non-ASCII character -- and that comparison only runs when at least one
    invitation is live. Letting a non-ASCII digit through therefore turned an
    anonymous request into a free oracle for gateway state: 401 with nothing
    pending, 500 with an invitation waiting. Keep the comparison fed with
    ASCII only.
    """
    return "".join(char for char in value if char in "0123456789")


class InvitationStore:
    """Pending invitations persisted as {id, name, link_hash, code, expires}."""

    def __init__(self, path: Optional[str] = None) -> None:
        self.path = Path(path) if path is not None else DEFAULT_CONFIG_DIR / "invitations.json"
        self._invitations: List[Dict[str, Any]] = []
        self._stat = None
        self._load()

    def _load(self) -> None:
        # Same ordering rule as TokenStore._load: commit the stat key only
        # after a successful read, or a corrupt file matches its own recorded
        # key forever and the store silently serves stale state.
        stat = _stat_key(self.path)
        if stat is None:
            self._stat = stat
            self._invitations = []
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            invitations = self._validate(raw)
        except (ValueError, OSError) as exc:
            # Same rule as the token store: a file we cannot parse is an
            # error, never an empty set. Silently discarding invitations
            # would be less dangerous than silently discarding tokens, but
            # the surprise -- "I sent Bob a link and it just did not work" --
            # is exactly the failure this whole feature exists to remove.
            #
            # Unlike a genuinely corrupt file, an unreadable-but-parseable
            # file (e.g. one written before the "id" field existed) has an
            # easy way out, and the operator should not have to guess it:
            # nothing in here outlives ten minutes, so the file can simply be
            # deleted and the gateway restarted -- any invitation that was
            # still pending just needs reissuing.
            raise ValueError(
                "invitation store {0} is unreadable: {1}. If this file predates "
                "an upgrade, it is safe to delete: invitations expire in minutes, "
                "so nothing in it outlives a restart -- reissue any that were still "
                "pending.".format(self.path, exc)
            )
        self._invitations = invitations
        self._stat = stat

    @staticmethod
    def _validate(raw: Any) -> List[Dict[str, Any]]:
        if not isinstance(raw, dict):
            raise ValueError("expected a JSON object at the top level, got {0}".format(type(raw).__name__))
        entries = raw.get("invitations", [])
        if not isinstance(entries, list):
            raise ValueError('expected "invitations" to be a list, got {0}'.format(type(entries).__name__))
        for entry in entries:
            if not isinstance(entry, dict):
                raise ValueError("expected each invitation to be an object, got {0}".format(type(entry).__name__))
            if not isinstance(entry.get("name"), str) or not isinstance(entry.get("link_hash"), str) or not isinstance(entry.get("code"), str):
                raise ValueError('each invitation must have string "name", "link_hash" and "code" keys')
            if not isinstance(entry.get("expires"), (int, float)):
                raise ValueError('each invitation must have a numeric "expires" key')
            if not isinstance(entry.get("id"), str):
                raise ValueError('each invitation must have a string "id" key')
        return entries

    def _reload_if_changed(self) -> None:
        if _stat_key(self.path) != self._stat:
            self._load()

    def _save(self) -> None:
        _atomic_write_json(self.path, {"invitations": self._invitations})
        self._stat = _stat_key(self.path)

    def _prune(self) -> None:
        now = time.time()
        self._invitations = [entry for entry in self._invitations if entry["expires"] > now]

    def create(self, name: str, ttl: float = INVITATION_TTL_SECONDS) -> Tuple[str, str]:
        """Create an invitation for ``name``; returns (link_nonce, code).

        Both are returned in the clear exactly once, to be printed and then
        forgotten by this process.
        """
        if not name or not name.strip():
            # Mirrors TokenStore.mint: an empty identity owns nothing, which
            # makes every session it creates writable by anyone.
            raise ValueError("invitation name must not be empty or whitespace-only")
        self._reload_if_changed()
        link = secrets.token_urlsafe(32)
        code = "{0:0{1}d}".format(secrets.randbelow(10**CODE_DIGITS), CODE_DIGITS)
        self._prune()
        self._invitations.append({"id": secrets.token_hex(4), "name": name, "link_hash": _hash(link), "code": code, "expires": time.time() + ttl})
        self._save()
        return link, code

    def redeem(self, code: Optional[str] = None, link: Optional[str] = None) -> Optional[str]:
        """Consume the invitation matching ``code`` or ``link``; return its name.

        Returns None for anything that does not match a live invitation --
        wrong, expired, or already used. The caller must not distinguish those
        cases to its client: doing so turns this into an oracle.
        """
        self._reload_if_changed()
        self._prune()
        match = None
        if link:
            candidate = _hash(link)
            match = next((entry for entry in self._invitations if hmac.compare_digest(entry["link_hash"], candidate)), None)
        elif code:
            wanted = _normalize_code(code)
            if wanted:
                match = next((entry for entry in self._invitations if hmac.compare_digest(entry["code"], wanted)), None)
        if match is None:
            return None
        self._invitations.remove(match)
        self._save()
        return str(match["name"])

    def pending(self) -> int:
        self._reload_if_changed()
        self._prune()
        return len(self._invitations)

    def pending_list(self) -> List[Dict[str, Any]]:
        """Live invitations, soonest to expire first.

        Includes the code. That is safe here and nowhere else: the code is
        stored in clear (see the module docstring), the file is 0600, and the
        only consumer is the host-only admin panel. It is what lets the panel
        re-show an invitation you closed the window on -- the CLI prints once
        and forgets, so today the only remedy for a lost code is waiting ten
        minutes.
        """
        self._reload_if_changed()
        self._prune()
        rows = [{"id": str(entry["id"]), "name": str(entry["name"]), "code": str(entry["code"]), "expires": float(entry["expires"])} for entry in self._invitations]
        return sorted(rows, key=lambda row: row["expires"])

    def cancel(self, invitation_id: str) -> bool:
        """Withdraw a pending invitation. True if one was removed.

        Addressed by id rather than by code so a cancellation never puts a live
        credential in a URL path, and therefore never puts one in the gateway's
        access log. Name would not work either: one person can hold several
        pending invitations.
        """
        self._reload_if_changed()
        self._prune()
        remaining = [entry for entry in self._invitations if entry["id"] != invitation_id]
        if len(remaining) == len(self._invitations):
            return False
        self._invitations = remaining
        self._save()
        return True
