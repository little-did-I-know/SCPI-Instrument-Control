"""Bearer-token store for the lab gateway.

Tokens are high-entropy machine-generated secrets, not user-chosen passwords, so
SHA-256 is the right hash here: there is no guessable plaintext for a slow KDF to
defend against. If user-supplied tokens are ever accepted this must change.
"""

import hashlib
import hmac
import json
import os
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

DEFAULT_CONFIG_DIR = Path.home() / ".siglent"
TOKEN_PREFIX = "scpi_"


class DuplicateTokenName(ValueError):
    """Raised when minting a token with a name that already exists."""


def _hash(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class TokenStore:
    """Named bearer tokens persisted as {name, hash, created, last_used}."""

    def __init__(self, path: Optional[str] = None) -> None:
        self.path = Path(path) if path is not None else DEFAULT_CONFIG_DIR / "tokens.json"
        self._tokens: List[Dict[str, Any]] = []
        if self.path.exists():
            try:
                raw = json.loads(self.path.read_text(encoding="utf-8"))
                self._tokens = self._validate_tokens(raw)
            except (ValueError, OSError) as exc:
                # Never fall back to "no tokens" — that would silently open the gateway.
                raise ValueError("token store {0} is unreadable: {1}".format(self.path, exc))

    @staticmethod
    def _validate_tokens(raw: Any) -> List[Dict[str, Any]]:
        """Validate the parsed store shape; raise ValueError for anything malformed.

        A store that parses as JSON but has the wrong shape must fail exactly like
        corrupt JSON does -- never silently degrade to "no tokens".
        """
        if not isinstance(raw, dict):
            raise ValueError("expected a JSON object at the top level, got {0}".format(type(raw).__name__))
        tokens = raw.get("tokens", [])
        if not isinstance(tokens, list):
            raise ValueError('expected "tokens" to be a list, got {0}'.format(type(tokens).__name__))
        for entry in tokens:
            if not isinstance(entry, dict):
                raise ValueError("expected each token entry to be an object, got {0}".format(type(entry).__name__))
            if not isinstance(entry.get("name"), str) or not isinstance(entry.get("hash"), str):
                raise ValueError('each token entry must have string "name" and "hash" keys')
        return tokens

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps({"tokens": self._tokens}, indent=2), encoding="utf-8")
        try:
            os.chmod(self.path, 0o600)
        except OSError:
            pass  # best effort; Windows ACLs do not map onto POSIX modes

    def mint(self, name: str) -> str:
        if any(entry["name"] == name for entry in self._tokens):
            raise DuplicateTokenName("a token named {0!r} already exists".format(name))
        raw = TOKEN_PREFIX + secrets.token_urlsafe(32)
        self._tokens.append({"name": name, "hash": _hash(raw), "created": _now(), "last_used": None})
        self._save()
        return raw

    def verify(self, raw: str) -> Optional[str]:
        if not raw:
            return None
        candidate = _hash(raw)
        for entry in self._tokens:
            if hmac.compare_digest(entry["hash"], candidate):
                entry["last_used"] = _now()
                self._save()
                return str(entry["name"])
        return None

    def revoke(self, name: str) -> bool:
        remaining = [entry for entry in self._tokens if entry["name"] != name]
        if len(remaining) == len(self._tokens):
            return False
        self._tokens = remaining
        self._save()
        return True

    def names(self) -> List[str]:
        return [str(entry["name"]) for entry in self._tokens]

    def is_empty(self) -> bool:
        return not self._tokens
