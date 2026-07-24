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


EXEMPT_PATHS = frozenset({"/api/health"})
WS_SUBPROTOCOL_PREFIX = "scpi-token."
WS_ACCEPT_SUBPROTOCOL = "scpi"


def _bearer(headers) -> str:
    for key, value in headers:
        if key == b"authorization":
            text = value.decode("latin-1")
            if text.lower().startswith("bearer "):
                return text[7:].strip()
            return ""
    return ""


class AuthMiddleware:
    """Fail-closed ASGI middleware: every scope is authenticated unless exempt.

    Handles ``http`` and ``websocket`` scopes itself rather than delegating to
    BaseHTTPMiddleware, which never sees WebSocket upgrades.
    """

    def __init__(self, app, store: "TokenStore", exempt: Optional[frozenset] = None) -> None:
        self.app = app
        self.store = store
        self.exempt = EXEMPT_PATHS if exempt is None else exempt

    async def __call__(self, scope, receive, send):
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return
        path = scope.get("path", "")
        # Only /api/* is guarded; the SPA and its assets are served anonymously
        # so the browser can load the page that then asks for a token.
        if path in self.exempt or not path.startswith("/api/"):
            await self.app(scope, receive, send)
            return
        identity = self._identify(scope)
        if identity is None:
            await self._reject(scope, receive, send)
            return
        scope.setdefault("state", {})["identity"] = identity
        await self.app(scope, receive, send)

    def _identify(self, scope) -> Optional[str]:
        if scope["type"] == "websocket":
            for offered in scope.get("subprotocols", []):
                if offered.startswith(WS_SUBPROTOCOL_PREFIX):
                    return self.store.verify(offered[len(WS_SUBPROTOCOL_PREFIX) :])
            return None
        return self.store.verify(_bearer(scope.get("headers", [])))

    async def _reject(self, scope, receive, send) -> None:
        if scope["type"] == "websocket":
            await receive()  # consume websocket.connect before closing
            await send({"type": "websocket.close", "code": 1008})
            return
        body = json.dumps({"error": "Unauthorized", "detail": "missing or invalid bearer token"}).encode("utf-8")
        await send(
            {"type": "http.response.start", "status": 401, "headers": [(b"content-type", b"application/json"), (b"www-authenticate", b"Bearer"), (b"content-length", str(len(body)).encode("ascii"))]}
        )
        await send({"type": "http.response.body", "body": body})
