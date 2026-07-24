# Gateway security

The web gateway (`scpi-web`) puts your instruments on the network. Starting in
**v5.0.0** it has a real security boundary: every request is authenticated, and
each instrument session has an owner who alone may drive it. This page explains
the model and how to work with it — from the browser, from `curl`, and from a
Python script.

> **Upgrading from 4.x?** Two things change for you: the gateway now requires a
> token (see [Tokens](#tokens)), and saved reference files must be converted once
> (see [Reference file migration](#reference-file-migration)). Both are covered
> below.

## The threat model, in one paragraph

The gateway is designed for **a lab LAN with several trusted users sharing one
gateway**. It is *not* hardened for the public internet, and it does not
terminate TLS. The boundary stops an authenticated peer from doing things they
should not — driving someone else's scope, scanning the internal network, or
running code on the gateway host — and stops an unauthenticated peer from doing
anything at all. It does **not** encrypt traffic; for that, put the gateway
behind a reverse proxy or keep it on a network you trust. See
[Deployment](#deployment) for the specifics.

## First run

Start the gateway and it mints a token for you and prints a ready-to-open URL:

```console
$ scpi-web
Gateway ready. Open:

    http://127.0.0.1:8765/?token=scpi_Qy8…f3A
```

Open that URL. The web UI lifts the token out of the address bar, stores it in
the browser, and immediately strips it from the URL — so it does not linger in
your history or leak through the `Referer` header of any link you click. From
then on the UI sends the token automatically.

The token named `default` is created only when no tokens exist yet. Restarting
the gateway does **not** mint a new one or reprint the URL — your existing token
keeps working. To get the URL again, mint another token (below) or read the
token file.

## Tokens

Tokens are the gateway's credentials. They are long random strings prefixed
`scpi_`, stored **hashed** (SHA-256) in `~/.siglent/tokens.json` — the raw token
is shown once, at creation, and never written to disk or logged. Manage them
with the `token` subcommands:

```console
$ scpi-web token add alice
token 'alice' created. Copy it now, it is not stored:

    scpi_7dK…2mР

$ scpi-web token list
alice
default

$ scpi-web token revoke default
revoked 'default'
```

- **`token add <name>`** mints a token and prints it **once**. Copy it then; it
  cannot be recovered. The *name* is the identity — it is what appears as a
  session's owner and in any attribution.
- **`token list`** shows names only, never secrets.
- **`token revoke <name>`** removes a token. Revocation takes effect
  **immediately** — the next request carrying that token is rejected, even
  mid-session. Use it when a token is shared too widely or a laptop walks off.

Every token is equal: there are no roles or scopes. Anyone with a valid token can
create sessions and read any session; ownership (below) governs who may *write*.

The token store lives under `~/.siglent` by default; relocate it with
`--config-dir <path>` (which applies to `token add|list|revoke` and to serving).

> **A malformed `tokens.json` is a hard error, by design.** If the file is
> corrupt, the gateway refuses to start rather than falling back to "no tokens" —
> because "no tokens" would be indistinguishable from a fresh install and could
> silently open the gateway. Fix or remove the file.

## Sending the token

The token travels differently over HTTP and WebSocket, because browsers cannot
set an `Authorization` header on a WebSocket handshake.

### HTTP — `Authorization: Bearer`

```console
$ curl -H "Authorization: Bearer scpi_7dK…2mР" http://127.0.0.1:8765/api/sessions
```

A query-parameter token (`?token=…`) is accepted **only** on the initial page
load of the web UI, and is **rejected** on every `/api/*` route. Putting a
credential in an API URL would leak it into logs and history, so there is exactly
one way in for the API: the header.

```python
import requests

TOKEN = "scpi_7dK…2mР"
s = requests.Session()
s.headers["Authorization"] = f"Bearer {TOKEN}"

s.post("http://127.0.0.1:8765/api/sessions", json={"label": "bench", "mock": True})
```

### WebSocket — the `scpi-token` subprotocol

The live-waveform stream authenticates through the WebSocket subprotocol list.
Offer **two** entries — the token-bearing one and the plain `scpi` fallback:

```javascript
new WebSocket(url, [`scpi-token.${token}`, "scpi"]);
```

The server reads the token from the `scpi-token.` entry and, on success, accepts
the socket selecting the non-secret `scpi` subprotocol — it never echoes your
token back in a response header. An unauthenticated handshake is closed with code
**1008** (policy violation). If you only ever offer `scpi-token.<token>` with no
`scpi` fallback, a real browser will fail the handshake, so always send both.

### Health check

`GET /api/health` is the one route that needs no token — it exists so a load
balancer or a "is it up?" probe does not require a credential. It returns only
`{"status": "ok"}` and touches no instrument.

### API schema

The OpenAPI schema is served at `/api/openapi.json` and requires a token like any
other API route. The interactive `/docs` and `/redoc` UIs are **disabled** —
they sat outside the authenticated path and would have published the whole
control surface anonymously.

## Ownership: owner writes, everyone watches

Sharing a scope is the point of a gateway, but two people writing to the same
instrument mid-capture is not. So:

- The token that **creates** a session **owns** it.
- **Any** authenticated user may **read** it — state, live stream, captures,
  exports.
- Only the **owner** may **write** — channel/timebase/trigger changes, raw SCPI
  commands, starting/stopping logging, setting references, and closing the
  session. A non-owner write returns **409 Conflict** with the owner's name in
  the message.

In the web UI, a session you do not own shows a **read-only** badge naming the
owner; your view stays live, only the controls are gated.

### Claiming an abandoned session

If an owner walks away, their session should not stay locked forever. Any
authenticated user can take it over once the owner has been inactive past a
threshold:

```console
$ curl -X POST -H "Authorization: Bearer $TOKEN" \
    http://127.0.0.1:8765/api/sessions/<id>/claim
```

- The threshold is **`--abandon-after` seconds** (default **300**). Before it
  elapses, `claim` returns **409** with how long to wait.
- "Active" counts **reads and live-stream watching**, not just writes — so an
  owner watching a long capture, without touching a control, is *not* considered
  idle and cannot be claimed out from under them.
- An **unowned** session (created before ownership existed, or explicitly
  released) is claimable immediately.

### Handing off explicitly

The current owner can pass a session to a named user:

```console
$ curl -X POST -H "Authorization: Bearer $OWNER_TOKEN" \
    -H "Content-Type: application/json" -d '{"name": "bob"}' \
    http://127.0.0.1:8765/api/sessions/<id>/owner
```

The `name` must be an existing token name; an unknown name is rejected with
**400** and ownership does not change. Passing `""` **releases** the session
(makes it unowned and immediately claimable) — that is the only way an owner lets
go without naming a successor.

## Connecting to instruments: the SSRF gate

`POST /api/sessions` names a `host:port` and the gateway opens a TCP connection
to it. Left unchecked, an authenticated user could aim that at any internal
service and use the gateway as a port scanner or banner grabber. The gateway
validates every target before connecting:

- The hostname is **resolved first**, and **every** resolved address is checked —
  so a name that resolves to a loopback or internal address is rejected, not just
  a literal one.
- **Loopback, link-local, cloud-metadata (169.254.169.254), multicast, reserved,
  and unspecified** addresses are refused.
- The port must be in an **allowlist** — by default just **5025**, the SCPI
  raw-socket port. Permit others with `--allow-port <n>` (repeatable; 5025 stays
  allowed).
- A failed connection returns a **generic** message naming only the address you
  supplied — never bytes read from the peer, so the gateway cannot be used to
  read service banners.

Ordinary private-LAN instruments (`192.168.x.x`, `10.x.x.x`) on port 5025 connect
exactly as before. **Mock** sessions (`"mock": true`) open no socket and bypass
the gate entirely — use them for hardware-free work.

## Resource limits

- **`--max-sessions` (default 8)** caps concurrent instrument sessions. Beyond
  it, `POST /api/sessions` returns **409** until one is closed. The cap holds
  under concurrent requests, so a burst cannot slip past it.
- Full-resolution CSV/JSON serialization of deep-memory captures runs **off the
  event loop**, so one large export does not freeze the gateway for everyone
  else.

## Reference file migration

Reference-waveform metadata used to be stored as a Python pickle, which meant
*loading* a reference file could execute code in it. As of v5.0.0 metadata is
stored as JSON and files load without unpickling — closing that path.

**Files saved by 4.x are in the old format and will not load** until converted.
The gateway tells you so, naming the file. Convert them once:

```console
$ scpi-web references migrate
converted 3, skipped 0, failed 0 in /home/you/.siglent/references
```

- Conversion is **atomic** — a file that fails to convert is left exactly as it
  was, never truncated.
- It is **idempotent** — running it again reports already-converted files as
  skipped.
- Point it at a non-default directory with `--dir <path>`.

`references migrate` is the **only** part of the system that still reads the old
pickled format, and it does so only on files already in your own storage
directory, when you run the command explicitly.

## Deployment

| Concern | Guidance |
|---|---|
| **Bind address** | Defaults to `127.0.0.1` (local only). Use `--host 0.0.0.0` to reach it from the LAN — and only then does the token boundary matter. |
| **TLS / encryption** | Out of scope for the gateway. Traffic (including the bearer token) is unencrypted. Put the gateway behind a TLS-terminating reverse proxy, or keep it on a trusted network. |
| **Tokens in transit** | Because traffic is unencrypted, a token on an untrusted network can be captured. This is the main reason TLS-via-proxy is recommended for any non-loopback exposure. |
| **Token storage** | `~/.siglent/tokens.json`, hashed, written `0600` where the platform supports it. Anyone who can read the *raw* tokens (e.g. from your shell history) can act as you — treat them like passwords. |
| **Browser storage** | The UI keeps the token in `localStorage`. Any cross-site-scripting flaw in the app could read it; that is the accepted trade-off for tokens that also work from `curl` and scripts. |

## What is intentionally not covered

- **User accounts, passwords, roles, or scopes.** Tokens are flat and equal;
  identity is the token name. This is deliberate — it needs no account
  management and works identically from a browser, `curl`, and Python.
- **TLS.** See the table above.
- **Per-user reference storage.** References are a shared store; ownership
  applies to live instrument sessions only.
- **Rate limiting** beyond the session cap.

## Quick reference

| Flag | Default | Purpose |
|---|---|---|
| `--host` | `127.0.0.1` | Bind address; `0.0.0.0` exposes on the LAN |
| `--port` | `8765` | Listen port |
| `--config-dir` | `~/.siglent` | Where `tokens.json` lives |
| `--allow-port <n>` | `{5025}` | Extra instrument port(s) the gateway may connect to (repeatable) |
| `--max-sessions` | `8` | Concurrent instrument-session cap |
| `--abandon-after` | `300` | Seconds of owner inactivity before a session can be claimed |

| Command | Purpose |
|---|---|
| `scpi-web token add <name>` | Mint a token (printed once) |
| `scpi-web token list` | List token names |
| `scpi-web token revoke <name>` | Revoke a token immediately |
| `scpi-web references migrate` | Convert pre-5.0 reference files |

| Status | Meaning |
|---|---|
| **401** | Missing or invalid token |
| **409** on a write | You are not the session owner (message names who is) |
| **409** on `claim` | Owner still active/watching (message says how long to wait) |
| **409** on create | Session cap reached |
| **400** on session create | Target address/port refused by the SSRF gate |
| **WS close 1008** | WebSocket handshake was not authenticated |
