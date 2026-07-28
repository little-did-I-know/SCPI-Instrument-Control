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
anything at all beyond an uptime probe and redeeming an invitation they were
given (see [Inviting someone](#inviting-someone)). It does **not** encrypt
traffic; for that, put the gateway
behind a reverse proxy or keep it on a network you trust. See
[Deployment](#deployment) for the specifics.

## Starting the gateway

Every start prints where the gateway can be reached:

```console
$ scpi-web

Gateway ready at http://127.0.0.1:8765/
Hand out access with: scpi-web invite <name>
```

The URL is the address you bound to, with one adjustment: a wildcard bind
(`--host 0.0.0.0`) prints this machine's LAN address, because `0.0.0.0` is not
something a colleague can open. A concrete `--host` is used verbatim, and
loopback stays loopback. The gateway also records this URL in `gateway.json`
under its config directory, which is how `invite` (below) knows what link to
print.

The **very first** start is different: with no tokens on disk there is nobody
to invite you, so the gateway mints a token named `default` and prints a URL
carrying it:

```console
$ scpi-web

Gateway ready. Open:

    http://127.0.0.1:8765/?token=scpi_Qy8…f3A
```

Open that URL. The web UI lifts the token out of the address bar, stores it in
the browser, and immediately strips it from the URL — so it does not linger in
your history or leak through the `Referer` header of any link you click. From
then on the UI sends the token automatically.

That `?token=` bootstrap happens only while the token store is empty. Once it
holds anything, every start prints the plain banner above instead.

## Inviting someone

Nobody in the lab should ever have to handle a `scpi_…` string. To give a
colleague access, run one command on the gateway host:

```console
$ scpi-web invite bob

Invitation for 'bob' — expires in 10 minutes.

  Send this link:          http://127.0.0.1:8765/?invite=Vb2…9tQ
  Or read out this code:   417 902
```

Send the link, or read the six digits down the phone — the two are **one**
invitation with two ways in, and whichever is used first consumes it. Opening
the link signs that browser in with no typing at all; the code goes in the
**Join code** box on the gateway's sign-in screen. Either way the gateway
mints a token named `bob`, and that name is the identity that owns Bob's
sessions from then on.

- The invitation lives **ten minutes**. That is deliberate: a link pasted into
  a chat channel is worthless long before anyone scrolls back to it.
- It is good for **one** person. Two colleagues, two `invite` commands.
- Someone locked out — new laptop, cleared browser, no idea where the token
  went — is the same command again: `scpi-web invite bob`. Their existing
  tokens keep working alongside the new one. If they should not, run
  `scpi-web token revoke bob` **first**, then invite: revoking a name cuts off
  every token it holds, including one you just issued.

The link's host and port come from the URL the gateway recorded when it last
started, so what `invite` prints is openable as-is. If no gateway has ever
started from this config directory, `invite` prints a note saying so, falls
back to the default `http://127.0.0.1:8765/`, and points you at `--url` — pass
`--url http://host:port/` to set the base yourself.

## Tokens

A token is the gateway's actual credential: a long random string prefixed
`scpi_`, stored **hashed** (SHA-256) in `~/.siglent/tokens.json` — the raw
token is shown once, at creation, and never written to disk or logged. An
invitation redeems into one of these.

You mint one by hand for **scripts, notebooks, and CI** — the case where a
long-lived secret that can be copied into a config or a secret store is
exactly the right answer, and where nobody is sitting at a browser to type a
join code.

```console
$ scpi-web token add ci-nightly
token 'ci-nightly' created. Copy it now, it is not stored:

    scpi_7dK…2mР

$ scpi-web token list
alice                2 devices   last used 2026-07-28T09:14:02+00:00
ci-nightly           1 device    last used never

$ scpi-web token revoke alice
revoked 'alice'
```

- **`token add <name>`** mints a token and prints it **once**. Copy it then; it
  cannot be recovered. Hand it to automation through an environment variable or
  a secret store rather than pasting it into a script — see
  [Sending the token](#sending-the-token) for a worked example.
- A **name is an identity, not a credential.** One name can hold several
  tokens — a laptop, a bench tablet, a reinstalled browser — and every one of
  them reports the same owner. Running `token add bob` twice succeeds and
  leaves you with two working tokens for Bob; so does inviting him twice.
- **`token list`** shows names, how many device tokens each holds, and when one
  of them was last seen — never secrets. `last used` is best-effort bookkeeping
  kept in memory by the running gateway; it resets when the store reloads and
  is not an audit record.
- **`token revoke <name>`** removes **every** token under that name, so "Bob
  has left" is a single command whatever he signed in from.

**Revocation takes effect immediately.** The gateway watches `tokens.json` and
reloads it when it changes on disk, so a token revoked from another terminal
stops working on the very next request — no restart, no window in which a
leaked token still opens the door.

Every token is equal: there are no roles or scopes. Anyone with a valid token can
create sessions and read any session; ownership (below) governs who may *write*.

The token store lives under `~/.siglent` by default; relocate it with
`--config-dir <path>` (which applies to `token add|list|revoke`, to `invite`,
and to serving).

> **A malformed `tokens.json` is a hard error, by design.** If the file is
> corrupt, the gateway refuses to start rather than falling back to "no tokens" —
> because "no tokens" would be indistinguishable from a fresh install and could
> silently open the gateway. Fix or remove the file. Pending invitations live
> beside it in `invitations.json` and follow the same rule; that file holds no
> tokens, so deleting it costs you nothing but the invitations you have not yet
> handed out.

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
import os

import requests

# Mint it once with `scpi-web token add my-script`, then export it:
#     export SCPI_WEB_TOKEN=scpi_...
s = requests.Session()
s.headers["Authorization"] = f"Bearer {os.environ['SCPI_WEB_TOKEN']}"

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

### The two routes that need no token

Everything under `/api/` is authenticated except these:

- **`GET /api/health`** exists so a load balancer or an "is it up?" probe does
  not need a credential. It returns only `{"status": "ok"}` and touches no
  instrument.
- **`POST /api/join`** redeems an invitation — it cannot require a token,
  because it is how you get one. Unlike the health probe it is a **write**: a
  successful call mints a token and consumes the invitation. It takes
  `{"code": "417902"}` or `{"invite": "<the link's nonce>"}` and returns
  `{"token": …, "identity": …}`.

`/api/join` is the most exposed surface the gateway has, so it is built to give
nothing away. **Every** failure — wrong code, expired, already redeemed —
returns the same **401** with byte-identical wording, so it cannot be used to
probe for which invitations exist. Only a rate limit answers differently, with
**429**.

### Guessing a join code

A six-digit code is 1,000,000 possibilities, which is only enough because of
what surrounds it:

- An invitation **expires in ten minutes**, so a guesser gets ten minutes, not
  forever.
- **Failed** `/api/join` attempts are limited to **ten per minute across all
  clients** — not per IP. A per-IP budget means very little against someone on
  the same lab network who can pick their own source addresses. Successes are
  not counted, because a success consumes its invitation and so cannot be
  repeated, and counting them would let a lab arriving together at 9am lock
  each other out.

That caps a determined guesser at roughly 100 attempts over an invitation's
life: about a 1-in-10,000 chance per invitation.

There is deliberately **no per-invitation attempt cap.** A wrong code cannot be
attributed to any particular invitation, so the only way to charge one would be
to charge all of them — which would hand any passer-by a way to invalidate
everyone's pending access by typing garbage. The global failure limit is the
trade: a burst of wrong guesses delays honest joiners by a minute rather than
cancelling them.

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
  elapses, `claim` returns **409** naming the owner and how long they have been
  idle (subtract that from `--abandon-after` for the remaining wait).
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
- **General rate limiting.** The only limiter is on failed `/api/join`
  attempts (above); authenticated routes are bounded by the session cap alone.

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
| `scpi-web invite <name>` | Give a person access: a 10-minute link and code (`--url` overrides the base URL) |
| `scpi-web token add <name>` | Mint a long-lived token for a script or CI job (printed once) |
| `scpi-web token list` | List identities with device counts and last use |
| `scpi-web token revoke <name>` | Revoke every token under a name (effective immediately) |
| `scpi-web references migrate` | Convert pre-5.0 reference files |

| Status | Meaning |
|---|---|
| **401** | Missing or invalid token — or, on `join`, an invitation that is wrong, expired, or already used (one message for all three) |
| **429** on `join` | Too many failed join attempts across all clients; wait a minute |
| **409** on a write | You are not the session owner (message names who is) |
| **409** on `claim` | Owner still active/watching (message names them and their idle seconds) |
| **409** on create | Session cap reached |
| **400** on session create | Target address/port refused by the SSRF gate |
| **WS close 1008** | WebSocket handshake was not authenticated |
