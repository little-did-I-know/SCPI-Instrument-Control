# Admin panel

Managing who can use the gateway used to mean remembering CLI subcommands. It
does not any more. The gateway serves a small **admin panel** on the machine it
runs on, at:

```
http://127.0.0.1:8766/
```

Open that in a browser **on the gateway machine** and you get one screen showing
everyone who has access, with buttons to invite someone or cut them off. The
`scpi-web invite` and `scpi-web token` commands still work exactly as before —
the panel is a second way in, not a replacement.

> **This page is for whoever administers the gateway.** If you are a user
> wanting to sign in, you need a link or a six-digit code from that person;
> see the [Browser UI tour](browser-ui.md).

## Why there is no sign-in

The panel asks for no password and no token. That is deliberate, and it rests on
**two independent defences** — which is worth spelling out, because each one
looks redundant until you see the attacker the other misses. Removing either
opens the panel up.

**1. The listener binds `127.0.0.1`.** The operating system refuses every
non-local connection before any gateway code runs. A colleague on the LAN
pointing a browser at `http://gateway-pc:8766/` does not get a login screen —
they get a refused connection. **Physical access to the gateway machine is the
credential**, the same standard as being able to sit down and type
`scpi-web token revoke bob`.

**2. Requests must carry a `Host` of `127.0.0.1` or `localhost`.** The bind stops
a non-local *socket*. It does not stop a *browser*. A page the admin visits in
the ordinary course of a day can point its own hostname at `127.0.0.1` — DNS
rebinding — and become same-origin with the panel. The connection then really
does arrive on loopback, so the bind is satisfied and waves it through; without
this check that page could quietly issue an invitation and read the redeemable
link straight back out of the response. A `Host` allowlist breaks it, because
the request still carries the attacker's hostname. CORS does not help here:
rebinding defeats it by construction.

So: **the bind stops the lab; the `Host` check stops the web.** Neither covers
the other's attacker.

What this model does *not* survive is someone who can already run a browser on
the gateway machine as you. If that is in your threat model, do not run the
panel — see [Turning it off](#turning-it-off).

## Where it is, and moving it

| Flag | Default | Purpose |
|---|---|---|
| `--admin-port` | `8766` | Port for the admin panel |
| `--no-admin` | *(off)* | Do not start the admin listener at all |

`--port` and `--admin-port` must differ; the gateway says so and exits rather
than failing later inside the socket bind.

**There is deliberately no `--admin-host`.** Every argument above depends on the
listener being on loopback, so making the address configurable would turn a
guarantee into a footgun — one flag, probably copied from a forum post, and an
unauthenticated access-management UI is on the LAN. The address is a constant in
the source, and the gateway asserts it is a loopback address before binding.

If you need the panel from another machine, forward the port over SSH rather
than rebinding it. The tunnel terminates on the gateway's own loopback, so the
bind is satisfied honestly, and your browser sends a `Host` of `localhost`, so
the allowlist is too:

```console
$ ssh -L 8766:127.0.0.1:8766 you@gateway-pc
```

Then open `http://localhost:8766/` on your own machine. This does move the
boundary — anyone who can SSH to the gateway as you can now administer it — but
that is a boundary you already chose, authenticated by SSH keys rather than by
an unauthenticated port on the LAN.

## The People screen

There is one screen, because the person administering a gateway sits down to do
a job, not to navigate.

**Who has access** lists each identity with the number of devices signed in
under it and when one of them was last seen. This is `scpi-web token list` with
a **Revoke** button. Revoking asks first, and the confirmation names the
consequence — *"Revoke bob? This signs out all 2 of their devices"* — because
the device count is exactly what the CLI cannot easily tell you before you act.
Revocation takes effect on the next request; there is no restart.

**Invitations** takes a name and creates a ten-minute invitation, showing:

- the **link** to send, which signs a browser in with no typing at all;
- the **six-digit code** to read down a phone, grouped as `417 902`;
- a **countdown** to expiry, so you can see whether it is still worth sending.

Both are one invitation with two ways in; whichever is used first consumes it.

**Cancelling a pending invitation is new here.** From the CLI, an invitation
sent to the wrong person or with a typo in the name could only be waited out —
ten minutes with a live credential in someone's chat window. The panel lists
everything still pending and cancels it outright.

### A code can be shown again; a link cannot

Reopen the panel five minutes later and a pending invitation still shows its
code, so an admin who closed the window can read it out without cancelling and
starting over.

The link is not shown again, and this is not an oversight. Only a **hash** of
the link's nonce is stored, so the link genuinely exists once, at the moment of
creation — there is nothing on disk to rebuild it from. If a link is lost,
cancel the invitation and make a new one.

The code, by contrast, is stored **in the clear**, and that deserves an
explanation rather than a raised eyebrow. Hashing a secret drawn from a space of
1,000,000 would be theatre: anyone holding the file could enumerate all
1,000,000 hashes in well under a second. The code's real defences are that it
expires in ten minutes and that failed redemptions are rate-limited (see
[Guessing a join code](security.md#guessing-a-join-code)). Storing it hashed
would only make it *look* safer than it is.

Storing it in clear is safe **here and nowhere else**: `invitations.json` is
written `0600` where the platform supports it, and the only thing that ever
reads a code back out is the host-only panel. It is never served to the LAN app.

## First run

Starting a gateway with an empty token store no longer mints anything. There is
no auto-created `default` identity and no `?token=…` bootstrap URL — the first
person to use a gateway should be a named human, not a placeholder that then
owns every session it touches.

Instead the gateway prints where it is and opens the panel on the host:

```console
$ scpi-web

Gateway ready at http://127.0.0.1:8765/
No one has access yet — finish setup at http://127.0.0.1:8766/
```

The panel shows *"No one has access yet. Invite someone below to get started."*
Type your own name, press **Invite**, and open the link it gives you. That
mints an identity for **you**, and from then on the sessions you create are
owned by your name.

If no browser can be opened — a headless box, an SSH session, a machine with no
associated browser — the gateway carries on regardless and the printed URL is
still there to open by hand. A browser problem can never stop a gateway
starting.

Once anyone has access, every later start prints the ordinary banner:

```console
$ scpi-web

Gateway ready at http://127.0.0.1:8765/
Admin panel (this machine only) at http://127.0.0.1:8766/
Hand out access with: scpi-web invite <name>
```

## Turning it off

`--no-admin` starts the gateway with no admin listener at all. Nothing else
changes; the CLI still does everything the panel does, apart from cancelling a
pending invitation.

On a gateway that **already** has users, that is all you need to know. On a
**fresh** one it would otherwise be a trap — no panel and no auto-minted token
means no way in — so the gateway says what to do instead:

```console
$ scpi-web --no-admin

Gateway ready at http://127.0.0.1:8765/
No one has access yet, and the admin panel is disabled (--no-admin).
Create the first identity with: scpi-web invite <name>
```

That is the path a headless or containerised deployment takes: run
`scpi-web invite <name>` once, from the same `--config-dir`, and send yourself
the link.

## For maintainers: the panel is a separate bundle

The admin UI is built and shipped separately from the LAN app, and the two must
never meet:

- `npm run build:admin` emits to `webapp/app/dist-admin/`, which
  `make webapp-build` copies to `scpi_control/server/admin/static/`.
- The LAN app builds to `dist/` and is served from
  `scpi_control/server/static/`.

They are kept apart because the main app's SPA catch-all serves any real file it
finds in *its* static directory — so a shared directory would hand the
access-management UI to every browser in the lab. For the same reason the admin
app is never mounted under the main app and never shares its router.

CI enforces this by **content, not filename**: it greps the built LAN bundle for
an admin-only route string and fails if one appears. A check that only looked
for a file called `admin.*` would miss the case actually worth catching — an
`import` from `src/admin/*` into the main app's module graph pulls admin code
into `dist/` while leaving every filename untouched.

## Where to next

- [Gateway security](security.md) — invitations, tokens, session ownership,
  the SSRF gate, and deployment guidance
- [Browser UI tour](browser-ui.md) — what the people you invite will see
