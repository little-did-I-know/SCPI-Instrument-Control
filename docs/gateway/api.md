# REST & WebSocket API

This is the complete wire reference for the gateway server. All paths below
are relative to the server root (default `http://127.0.0.1:8765`); every
`/api/*` route accepts and returns JSON. This page mirrors what the browser
UI itself calls, with one noted exception: the older `/scope/command` route
(see [Scope configuration](#scope-configuration)) is public API that still
works, but the shipping frontend calls the kind-agnostic
[command console](#command-console) route instead.

Every route below requires `Authorization: Bearer <token>` **except**
`GET /api/health` and `POST /api/join`. The latter exchanges an invitation for
a token — `{"code": "417902"}` or `{"invite": "<nonce from an invite link>"}`
in, `{"token", "identity"}` back — so it cannot require the credential it
issues; every failure returns an identical **401**, and too many failures
return **429**. See the [Gateway security guide](security.md) for how to
invite someone or mint a token, how ownership gates writes, and the WebSocket
authentication handshake.

## Sessions & discovery

| Method | Path | Body / params | Response | Errors |
|---|---|---|---|---|
| `GET` | `/api/models` | — | List of `{model_name, series, num_channels, bandwidth_mhz, dialect}` — the built-in model registry | — |
| `GET` | `/api/sessions` | — | List of session objects (see below) | — |
| `POST` | `/api/sessions` | `{label?, address?, port?, mock?, model?}` | **201** session object | 400 invalid params; connection failures surface as the instrument-error codes below |
| `GET` | `/api/sessions/{id}` | — | Session object | 404 unknown session |
| `DELETE` | `/api/sessions/{id}` | — | **204** No Content | 404 unknown session |
| `GET` | `/api/discover` | `?cidr=` optional (defaults to the gateway's local /24) | List of discovered/connected instruments (see below) | 400 invalid CIDR, range wider than /22, or local network undetectable |

A **session object**: `{id, label, mock, address, state, idn, model, dialect, num_channels, viewers}`. `state` is one of `connecting` / `connected` / `error` / `closed`; `dialect` is `"legacy"` or `"modern"` once connected; `viewers` counts currently-subscribed WebSocket clients.

A **discover entry** is either a live session — `{address, idn, manufacturer, model, dialect, kind, connected: true, session_id, viewers}` — or an unconnected device found by the scan — the same shape minus `session_id`/`viewers`, with `connected: false`. `kind` is `"scope"`, `"psu"`, `"awg"`, `"daq"`, or `"unknown"`, guessed from the model prefix.

`address`/`port`/`mock`/`model` on `POST /api/sessions` are all optional: pass `{"mock": true}` for a hardware-free session, or `{"address": "192.168.1.100"}` for a real instrument (port defaults to 5025).

## Command console

| Method | Path | Body / params | Response | Errors |
|---|---|---|---|---|
| `POST` | `/api/sessions/{id}/command` | `{command}` — a raw SCPI string | `{command, response}` — `response` is the query reply, or `null` for a write | 400 empty command; 404 unknown session; 409 if the session is in an error/closed state |

The kind-agnostic console route: it works for any connected instrument kind
(scope, PSU, or AWG today), because sending a raw command needs nothing
kind-specific — every driver exposes `write`/`query`. This is what the browser UI's Terminal
drawer calls (see [Browser UI Tour](browser-ui.md#scpi-terminal)). A command
ending in `?` is a query and returns the instrument's answer; anything else is
a write and returns a `null` response — never a fabricated one.

## Power supply configuration

All paths below are under `/api/sessions/{id}/psu/`, and require a session created with
`kind: "psu"`.

| Method | Path | Body / params | Response | Errors |
|---|---|---|---|---|
| `GET` | `state` | — | `{outputs: [{output, voltage, current, enabled, measured_voltage, measured_current, measured_power}, ...]}` | 400 non-psu session; 404 unknown session; 409 if the session is in an error/closed state |
| `PATCH` | `outputs/{n}` | `{voltage?, current?}` | `{outputs: [...]}` (same shape as `GET state`) | 400 unknown output or non-psu session; 409 not the session owner, or session not accepting jobs |
| `PATCH` | `outputs/{n}/enable` | `{enabled}` | `{outputs: [...]}` | 400 unknown output or non-psu session; 409 not the session owner, or session not accepting jobs |

Every field in an output is read through the driver, never fabricated: a value the supply will not
answer (an SPD3303X's CH3 has no output-state query at all) comes back as `null`, and the browser
UI shows that as `--.--`, or as an unknown output state rather than a confident off. Every mutation
also broadcasts the fresh `outputs` list to the session's WebSocket subscribers as a `state`
message with `"kind": "psu"`.

## Function generator configuration

All paths below are under `/api/sessions/{id}/awg/`, and require a session created with
`kind: "awg"`.

| Method | Path | Body / params | Response | Errors |
|---|---|---|---|---|
| `GET` | `state` | — | `{channels: [{channel, function, frequency, amplitude, offset, phase, enabled, duty_cycle, symmetry}, ...]}` | 400 non-awg session; 404 unknown session; 409 if the session is in an error/closed state |
| `PATCH` | `channels/{n}` | `{function?, frequency?, amplitude?, offset?, phase?, duty_cycle?, symmetry?}` — `function` one of `SINE`/`SQUARE`/`RAMP`/`PULSE`/`NOISE`/`ARB`/`DC` | `{channels: [...]}` (same shape as `GET state`) | 400 unsupported `function`, unknown channel, or non-awg session; 409 not the session owner, or session not accepting jobs |
| `PATCH` | `channels/{n}/enable` | `{enabled}` | `{channels: [...]}` | 400 unknown channel or non-awg session; 409 not the session owner, or session not accepting jobs |
| `POST` | `outputs/off` | — | `{channels: [...]}` | 400 non-awg session; 409 not the session owner, or session not accepting jobs |

`duty_cycle` is only read back while `function` is `PULSE`, and `symmetry` only while it is `RAMP`
— both come back `null` otherwise, matching what the channel panel shows. Every other field is
read through the driver like the PSU's, so a value the generator will not answer, or an enable
state a model cannot query, comes back as `null`/unknown rather than a guess. `outputs/off` kills
every channel in one request rather than one `PATCH` per channel, because turning outputs off one
at a time on a live circuit races. Every mutation also broadcasts the fresh `channels` list to the
session's WebSocket subscribers as a `state` message with `"kind": "awg"`.

## Scope configuration

All paths below are under `/api/sessions/{id}/scope/`.

| Method | Path | Body / params | Response | Errors |
|---|---|---|---|---|
| `GET` | `state` | — | Full state snapshot (channels, timebase, trigger, run state) | 404 unknown session; 409 if the session is in an error/closed state |
| `PATCH` | `channels/{n}` | `{enabled?, voltage_scale?, voltage_offset?, coupling?, probe_ratio?}` | State snapshot | 400 invalid coupling (must be `DC`/`AC`/`GND`) or unknown channel; 409 if the session is in an error/closed state |
| `PATCH` | `timebase` | `{timebase}` (seconds/div, required) | State snapshot | 409 session not accepting jobs |
| `PATCH` | `trigger` | `{mode?, source?, level?, slope?, coupling?}` | State snapshot | 400 invalid value (trigger coupling must be `DC`/`AC`/`HFREJ`/`LFREJ`); 409 session not accepting jobs |
| `POST` | `run` \| `stop` \| `single` \| `auto` | — | State snapshot | 400 unknown operation (any other `{op}` value); 409 session not accepting jobs |
| `POST` | `command` | `{command}` — a raw SCPI string | `{command, response}` — `response` is the query reply, or `null` for a write | 400 empty command or non-scope session; 409 if the session is in an error/closed state |
| `PUT` | `measurements` | `[{channel, mtype}]` — `mtype` one of the 17 supported types (`PKPK`, `MAX`, `MIN`, `AMPL`, `TOP`, `BASE`, `CMEAN`, `MEAN`, `RMS`, `CRMS`, `FREQ`, `PER`, `RISE`, `FALL`, `WID`, `NWID`, `DUTY`) | `{measurements: [{channel, mtype}]}` | 400 unknown `mtype` or out-of-range channel; **409 while a trend recording is active** (selection is locked) |
| `GET` | `measurements` | — | `{measurements: [{channel, mtype}]}` | — |

The **state snapshot** returned by `GET state` and every scope mutation: `{run_state, timebase, channels: {"<n>": {enabled, voltage_scale, voltage_offset, coupling, probe_ratio}}, trigger: {mode, source, level, slope, coupling}}`. Every mutation also broadcasts this snapshot to the session's WebSocket subscribers as a `state` message.

## Acquisition & export

All paths under `/api/sessions/{id}/scope/`.

| Method | Path | Params | Response | Errors |
|---|---|---|---|---|
| `GET` | `capture.csv` | `?channels=1,2` (comma-separated) | `text/csv` — one `time_s` column plus one `C{n}_V` column per requested channel, aligned to the shortest capture | 400 no/invalid channels; 409 if the session is in an error/closed state |
| `GET` | `screenshot.png` | — | `image/png` — the instrument's display | 409 if the session is in an error/closed state |
| `GET` | `waveform` | `?channels=1,2&max_points=N` | `{"channels": [{channel, t0, dt, sample_rate, voltage_scale, voltage_offset, points}, ...]}` — `points` decimated to `max_points` (0/omitted = full resolution) | 400 no/invalid channels; 409 if the session is in an error/closed state |

## Analysis

All paths under `/api/sessions/{id}/scope/`.

| Method | Path | Body | Response | Errors |
|---|---|---|---|---|
| `GET` | `math` | — | `[{n, expression, enabled}]` for M1 and M2 | 409 if the session is in an error/closed state |
| `PATCH` | `math/{n}` | `{expression?, enabled?}` (`n` is 1 or 2) | `[{n, expression, enabled}]` (both channels) | 400 unknown `n`, or an empty expression; 409 if the session is in an error/closed state |
| `GET` | `spectrum` | — | `{enabled, channel, window, db}` | — |
| `PATCH` | `spectrum` | `{enabled?, channel?, window?, db?}` | Updated `{enabled, channel, window, db}` | 400 unknown window (must be one of `rectangular`/`hanning`/`hamming`/`blackman`/`bartlett`/`flattop`) or out-of-range channel |
| `GET` | `filters` | — | `[{n, source, kind, cutoff_low, cutoff_high, order, enabled}]` for F1 and F2 | — |
| `PATCH` | `filters/{n}` | `{source?, kind?, cutoff_low?, cutoff_high?, order?, enabled?}` (`n` is 1 or 2) | Full filter list (as above) | 400 unknown `n`/`kind`, out-of-range `source` or `order` (1-10), non-positive cutoff, or missing cutoff(s) required by `kind` when `enabled: true` |

Math, spectrum, and filter results are **not** returned inline — they stream to WebSocket subscribers as `waveform` (math/filters) or `spectrum` frames on the next poll tick. `PATCH` here only changes configuration.

## References

All paths under `/api/sessions/{id}/scope/`.

| Method | Path | Body | Response | Errors |
|---|---|---|---|---|
| `GET` | `references` | — | List of saved references: `[{name, channel, timestamp, num_samples, time_span}]` | — |
| `POST` | `references` | `{name, channel}` — snapshots the channel's current waveform | **201** — the full updated reference list (same shape as `GET references`, replace-on-save if `name` already existed) | 400 empty name or out-of-range channel; 409 if the session is in an error/closed state |
| `DELETE` | `references/{name}` | — | **204** No Content | 404 unknown reference name |
| `GET` | `reference` | — | The active overlay: `{name, channel, t0, dt, points}` (`name`/`channel` are `null` when no reference is active) | — |
| `PUT` | `reference` | `{name}` or `{name: null}` to clear | The active overlay (as above) | 404 unknown reference name (**400** if the store holds un-migrated pre-5.0 files — run `scpi-web references migrate`) |

Setting the active reference (via `PUT`) broadcasts a `reference` message, and every poll tick afterward broadcasts a `reference_stats` message with live correlation/deviation.

## Trend log

All paths under `/api/sessions/{id}/scope/`.

| Method | Path | Params | Response | Errors |
|---|---|---|---|---|
| `POST` | `log/start` | — | Recorder status (see below) | 400 no measurements selected; 409 already recording |
| `POST` | `log/stop` | — | Recorder status | — |
| `GET` | `log` | — | Recorder status | — |
| `GET` | `log/data` | `?since=<unix-seconds>` | `{columns: [{channel, mtype}], rows: [[timestamp, v1, v2, ...], ...]}` — rows after `since` | — |
| `GET` | `log.csv` | — | `text/csv` — `timestamp,elapsed_s,C{n} {mtype}...` | 404 if no recording has ever been started this session |

**Recorder status**: `{state, started_at, columns: [{channel, mtype}], row_count, max_rows}` (`state` is `"idle"` or `"recording"`; `max_rows` is the ring-buffer cap, 86400 rows = 24 h at 1 Hz). Starting or stopping a recording also broadcasts a `log_status` WebSocket message with the same fields **except `max_rows`**, which is REST-only.

## WebSocket

`GET /api/sessions/{id}/stream` (upgrade to WebSocket) — the server pushes JSON messages as the session's state changes; there is nothing to send except an open connection (the socket is read from only to detect disconnects). On connect the server immediately sends a `state` message with the current snapshot, then streams the following message types:

| Type | Example |
|---|---|
| `state` | `{"type": "state", "state": {"run_state": "STOP", "timebase": 0.001, "channels": {...}, "trigger": {...}}}` |
| `waveform` | `{"type": "waveform", "channel": 1, "t0": 0.0, "dt": 1e-6, "points": [0.01, 0.02, ...]}` — `channel` is an int (1-4) for a real channel, or `"M1"`/`"M2"`/`"F1"`/`"F2"` for math/filter traces; an empty `points: []` marks a math/filter trace being cleared |
| `measurements` | `{"type": "measurements", "values": [{"channel": 1, "mtype": "FREQ", "value": 1000.0}], "timestamp": 1752600000.0}` |
| `measurements_config` | `{"type": "measurements_config", "items": [{"channel": 1, "mtype": "FREQ"}]}` |
| `spectrum` | `{"type": "spectrum", "channel": 1, "f0": 0.0, "df": 500.0, "points": [-80.0, -75.2, ...], "db": true, "window": "hanning", "peaks": [[1000.0, -12.5]], "thd": 0.02}` |
| `reference` | `{"type": "reference", "name": "baseline", "channel": 1, "t0": 0.0, "dt": 1e-6, "points": [...]}` |
| `reference_stats` | `{"type": "reference_stats", "correlation": 0.998, "max_deviation": 0.012}` |
| `log_status` | `{"type": "log_status", "state": "recording", "started_at": 1752600000.0, "row_count": 42, "columns": [{"channel": 1, "mtype": "FREQ"}]}` |
| `error` | `{"type": "error", "detail": "connection lost"}` |
| `closed` | `{"type": "closed"}` |

The connection closes with code **4404** if the session ID does not exist, and **4410** when the session itself closes (after which the socket receives a final `closed` message). The server-side outbox is bounded (256 frames); under sustained backpressure it drops the oldest queued `waveform` frame to make room rather than growing unbounded — `state`/`error`/`closed` control frames are never dropped.

## Errors

Every error response is JSON: `{"error": "<ExceptionClassName>", "detail": "<message>"}`.

| Status | Meaning |
|---|---|
| 400 | Validation failure — bad/missing parameters, invalid enum value, out-of-range channel |
| 404 | Unknown resource — session ID, reference name, or (for `log.csv`) no recording ever started |
| 409 | State conflict — session not accepting jobs (error/closed), already recording, or measurement selection locked while recording |
| 504 | Instrument communication timed out |
| 500 | Other instrument error |

## Curl quickstart

Create a mock session, configure a channel, and fetch its waveform as JSON — no hardware required. Start the gateway first, then mint a token for this script with `scpi-web token add curl-demo` (that is what `token add` is for: scripts and CI, where a long-lived secret is the right answer) and export it:

```bash
export TOKEN=scpi_...   # printed once by `scpi-web token add curl-demo`

# 1. Create a mock scope session
curl -s -X POST http://127.0.0.1:8765/api/sessions \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"mock": true, "label": "curl demo"}'
# -> 201 {"id": "a1b2c3d4", "label": "curl demo", "mock": true, "address": null,
#         "state": "connected", "idn": "Siglent Technologies,SDS1104X-E,MOCK0001,1.0.0.0",
#         "model": "SDS1104X-E", "dialect": "legacy", "num_channels": 4, "viewers": 0}

SESSION_ID=a1b2c3d4   # substitute the "id" from the response above

# 2. Enable channel 1 and set its vertical scale
curl -s -X PATCH "http://127.0.0.1:8765/api/sessions/$SESSION_ID/scope/channels/1" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"enabled": true, "voltage_scale": 0.5}'

# 3. Fetch channel 1's waveform as JSON, decimated to 200 points
curl -s -H "Authorization: Bearer $TOKEN" \
  "http://127.0.0.1:8765/api/sessions/$SESSION_ID/scope/waveform?channels=1&max_points=200"

# 4. Clean up
curl -s -X DELETE -H "Authorization: Bearer $TOKEN" \
  "http://127.0.0.1:8765/api/sessions/$SESSION_ID"
```
