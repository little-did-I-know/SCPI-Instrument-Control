"""Lab gateway entry point: python -m scpi_control.server / scpi-web."""

import argparse
import asyncio
import contextlib
import ipaddress
import sys
from pathlib import Path

import uvicorn

from scpi_control.server.adapters import DEFAULT_STREAM_MAX_FPS, DENSE_MAX_POINTS
from scpi_control.server.admin.app import DEFAULT_ADMIN_PORT, create_admin_app
from scpi_control.server.app import create_app
from scpi_control.server.auth import DEFAULT_CONFIG_DIR, TokenStore
from scpi_control.server.gateway_url import read_base_url, write_base_url
from scpi_control.server.invitations import InvitationStore, format_code
from scpi_control.server.netpolicy import DEFAULT_ALLOWED_PORTS

# The host-only boundary. Not a flag, and deliberately so: the admin app has no
# authentication because the OS refuses non-local connections before it runs.
# A configurable host would turn that guarantee into a footgun.
# DEFAULT_ADMIN_PORT lives in admin/app.py, not here: the app itself needs it
# to build the Origin allowlist, and two copies could drift apart into a panel
# that refuses its own requests.
ADMIN_HOST = "127.0.0.1"


class _QuietServer(uvicorn.Server):
    """A server that leaves signal handling to the main one.

    Two uvicorn servers on one loop would otherwise both capture SIGINT, and
    the second registration wins -- so Ctrl+C would stop one server while the
    other kept the process alive. uvicorn 0.34.3 captures signals through this
    context manager rather than install_signal_handlers().
    """

    @contextlib.contextmanager
    def capture_signals(self):
        yield


def _run_servers(main_app, host: str, port: int, admin_app, admin_port: int) -> None:
    """Serve the gateway, and the admin app when there is one.

    Both run on one event loop in one process so they can share the token
    store, the invitation store and the session manager as live objects.

    Only the main server installs signal handlers -- it uses a plain
    uvicorn.Server, while the admin server uses _QuietServer so its
    capture_signals() is a no-op. The main server's shutdown sets should_exit
    on the admin server too, so Ctrl+C stops both.
    """
    main_server = uvicorn.Server(uvicorn.Config(main_app, host=host, port=port))
    if admin_app is None:
        main_server.run()
        return

    assert ipaddress.ip_address(ADMIN_HOST).is_loopback, "the admin listener must bind a loopback address"
    admin_config = uvicorn.Config(admin_app, host=ADMIN_HOST, port=admin_port)
    admin_server = _QuietServer(admin_config)

    main_serve = main_server.serve

    async def _serve_both(sockets=None) -> None:
        admin_task = asyncio.ensure_future(admin_server.serve())
        try:
            await main_serve(sockets=sockets)
        finally:
            admin_server.should_exit = True
            await admin_task

    # Both listeners are driven by the main server's own run(), rather than by
    # an asyncio.run() call here, because run() is what picks the event loop
    # implementation -- and it has done that through two incompatible private
    # Config APIs: setup_event_loop() up to uvicorn 0.35, a loop_factory handed
    # to asyncio.run from 0.36, where the old name became a method that raises
    # AttributeError on sight. Naming either one here would pin this module to
    # a slice of the uvicorn range pyproject.toml declares. Letting run() do it
    # means the two-server path gets exactly the loop the --no-admin path above
    # gets (uvloop by default on Linux/macOS with uvicorn[standard]) on every
    # version, with no version sniffing at all.
    #
    # Swapping serve() on the instance is how the pair reaches run(): run()
    # awaits self.serve(sockets=sockets), so _serve_both stands in for it and
    # calls the real one via main_serve, captured above. capture_signals() still
    # wraps only the main server, inside main_serve, exactly as before.
    main_server.serve = _serve_both
    main_server.run()


def _open_browser(url: str) -> bool:
    """Open ``url`` in the host's browser. False if that was not possible.

    Never raises: a headless box, an SSH session or a machine with no
    associated browser must still start a gateway. The caller prints the URL
    either way.
    """
    import webbrowser

    try:
        return bool(webbrowser.open(url))
    except Exception:
        return False


def _config_dir(args) -> Path:
    return Path(args.config_dir) if args.config_dir else DEFAULT_CONFIG_DIR


def _invitations(args) -> InvitationStore:
    return InvitationStore(str(_config_dir(args) / "invitations.json"))


def _store(args) -> TokenStore:
    return TokenStore(str(_config_dir(args) / "tokens.json"))


def _add_config_dir(parser, default=None) -> None:
    """Register --config-dir.

    Subparsers must use ``default=argparse.SUPPRESS`` rather than ``None``.
    argparse's subparsers action reparses the remaining argv into a fresh
    namespace and then unconditionally copies every attribute from it back
    over the outer namespace -- so if a subparser's own --config-dir has a
    concrete default, that default overwrites a value the top-level parser
    already parsed whenever the flag isn't repeated after the subcommand.
    SUPPRESS omits the attribute entirely when the flag is absent, so the
    outer namespace's value (whatever position it was given in) survives.
    """
    parser.add_argument("--config-dir", default=default, help="directory holding tokens.json (default: ~/.siglent)")


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(prog="scpi-web", description="SCPI Instrument Control web gateway")
    parser.add_argument("--host", default="127.0.0.1", help="bind address (use 0.0.0.0 to expose on the LAN)")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--admin-port", type=int, default=DEFAULT_ADMIN_PORT, help="port for the host-only admin panel (default: 8766)")
    parser.add_argument("--no-admin", action="store_true", help="do not start the admin panel listener")
    parser.add_argument("--abandon-after", type=float, default=300.0, help="seconds of owner inactivity before another user may claim a session")
    # Registered ONLY on the top-level parser -- see _add_config_dir's docstring
    # for why the same option on a subparser (default=None) would clobber a
    # value already parsed here. --allow-port has no subcommand use, so it is
    # simply never added to one.
    parser.add_argument("--allow-port", type=int, action="append", default=None, help="additional port the gateway may connect to (repeatable; 5025 is always allowed)")
    # Registered ONLY on the top-level parser -- same trap as --allow-port
    # above: a subparser's own --max-sessions with default=None would clobber
    # a value already parsed here whenever the flag isn't repeated after the
    # subcommand. --max-sessions has no subcommand use, so it is never added
    # to one.
    parser.add_argument("--max-sessions", type=int, default=8, help="maximum concurrent instrument sessions the gateway will hold open")
    parser.add_argument("--stream-max-points", type=int, default=DENSE_MAX_POINTS, help="samples per live waveform frame on the binary stream (default: 100000; the JSON stream stays capped at 2000)")
    parser.add_argument("--stream-max-fps", type=float, default=DEFAULT_STREAM_MAX_FPS, help="upper bound on live-view updates per second per scope session (default: 20; real instruments settle far below it)")
    _add_config_dir(parser)

    sub = parser.add_subparsers(dest="command")
    token = sub.add_parser("token", help="manage access tokens").add_subparsers(dest="token_command", required=True)
    add = token.add_parser("add", help="mint a token (printed once)")
    add.add_argument("name")
    _add_config_dir(add, default=argparse.SUPPRESS)
    listing = token.add_parser("list", help="list token names")
    _add_config_dir(listing, default=argparse.SUPPRESS)
    revoke = token.add_parser("revoke", help="revoke a token by name")
    revoke.add_argument("name")
    _add_config_dir(revoke, default=argparse.SUPPRESS)

    invite = sub.add_parser("invite", help="create a join link and code for someone")
    invite.add_argument("name")
    invite.add_argument("--url", default=None, help="base URL to print (default: the URL the gateway last recorded)")
    _add_config_dir(invite, default=argparse.SUPPRESS)

    references = sub.add_parser("references", help="reference file maintenance").add_subparsers(dest="references_command", required=True)
    migrate = references.add_parser("migrate", help="convert pre-5.0 pickled reference files")
    migrate.add_argument("--dir", default=None, help="reference storage directory (default: ~/.siglent/references)")

    args = parser.parse_args(argv)

    if args.command == "references":
        from scpi_control.server.migrate import migrate_references

        target = args.dir if args.dir else str(DEFAULT_CONFIG_DIR / "references")
        result = migrate_references(target)
        print("converted {converted}, skipped {skipped}, failed {failed} in {0}".format(target, **result))
        return

    if args.command == "invite":
        base = args.url or read_base_url(_config_dir(args))
        fallback = base is None
        if fallback:
            base = "http://{0}:{1}/".format(args.host, args.port)
        try:
            link, code = _invitations(args).create(args.name)
        except ValueError as exc:
            sys.exit(str(exc))
        print("\nInvitation for {0!r} — expires in 10 minutes.\n".format(args.name))
        print("  Send this link:          {0}?invite={1}".format(base, link))
        print("  Or read out this code:   {0}\n".format(format_code(code)))
        if fallback:
            print("(No gateway has started from this config directory yet, so that link assumes")
            print(" {0}. If the gateway runs elsewhere, pass --url.)\n".format(base))
        return

    if args.command == "token":
        store = _store(args)
        if args.token_command == "add":
            try:
                print("token {0!r} created. Copy it now, it is not stored:\n\n    {1}\n".format(args.name, store.mint(args.name)))
            except ValueError as exc:
                # mint() rejects an empty or whitespace-only name; exit cleanly
                # with the message rather than surfacing a traceback.
                sys.exit(str(exc))
        elif args.token_command == "list":
            rows = store.summary()
            if not rows:
                print("no tokens")
            else:
                for row in rows:
                    devices = "{0} device{1}".format(row["devices"], "" if row["devices"] == 1 else "s")
                    print("{0:<20} {1:<11} last used {2}".format(row["name"], devices, row["last_used"] or "never"))
        elif args.token_command == "revoke":
            if not store.revoke(args.name):
                sys.exit("no token named {0!r}".format(args.name))
            print("revoked {0!r}".format(args.name))
        return

    # Checked before anything else in the server-start path (ahead of minting
    # a token or touching the config dir): SessionManager itself rejects
    # max_sessions < 1, but that raw ValueError would surface after "Gateway
    # ready" has already printed and a token has already been minted, reading
    # like a crash rather than a configuration mistake. parser.error() prints
    # a clear message and exits before any of that happens.
    if args.max_sessions < 1:
        parser.error("--max-sessions must be at least 1 (got {0})".format(args.max_sessions))

    # Same reasoning as --max-sessions above: SessionManager itself rejects a
    # nonsense stream budget, but that ValueError would surface after
    # "Gateway ready" instead of before anything starts.
    if args.stream_max_points < 100:
        parser.error("--stream-max-points must be at least 100 (got {0})".format(args.stream_max_points))
    if not args.stream_max_fps > 0:
        parser.error("--stream-max-fps must be positive (got {0})".format(args.stream_max_fps))

    # Same reasoning as --max-sessions above: without this check, --port and
    # --admin-port colliding fails deep inside uvicorn's socket bind with a
    # bare traceback instead of a sentence explaining the mistake.
    if not args.no_admin and args.port == args.admin_port:
        parser.error("--port and --admin-port must differ (both are {0})".format(args.port))

    store = _store(args)
    # Built here, not inline in the create_app(...) call below, for the same
    # reason --max-sessions is checked above: InvitationStore.__init__ raises
    # ValueError on a corrupt invitations.json, and constructing it after the
    # mint meant the admin saw "Gateway ready. Open: ...?token=..." for a
    # server that then died -- leaving a live token in tokens.json that, since
    # the store is no longer empty, no later start would ever print again.
    try:
        invitations = _invitations(args)
    except ValueError as exc:
        sys.exit(str(exc))
    url = write_base_url(_config_dir(args), args.host, args.port)
    admin_url = "http://{0}:{1}/".format(ADMIN_HOST, args.admin_port)
    if store.is_empty():
        if args.no_admin:
            print("\nGateway ready at {0}\nNo one has access yet, and the admin panel is disabled (--no-admin).\nCreate the first identity with: scpi-web invite <name>\n".format(url))
        else:
            print("\nGateway ready at {0}\nNo one has access yet — finish setup at {1}\n".format(url, admin_url))
            try:
                _open_browser(admin_url)
            except Exception:
                # _open_browser already swallows what it can; this is the
                # belt-and-braces guard that a browser problem can never stop a
                # gateway starting.
                pass
    elif args.no_admin:
        print("\nGateway ready at {0}\nHand out access with: scpi-web invite <name>\n".format(url))
    else:
        print("\nGateway ready at {0}\nAdmin panel (this machine only) at {1}\nHand out access with: scpi-web invite <name>\n".format(url, admin_url))
    allowed_ports = frozenset(args.allow_port) | DEFAULT_ALLOWED_PORTS if args.allow_port else None
    main_app = create_app(
        token_store=store,
        invitation_store=invitations,
        abandon_after=args.abandon_after,
        allowed_ports=allowed_ports,
        max_sessions=args.max_sessions,
        stream_max_points=args.stream_max_points,
        stream_max_fps=args.stream_max_fps,
    )
    admin_app = (
        None
        if args.no_admin
        else create_admin_app(
            token_store=store,
            invitation_store=invitations,
            manager=main_app.state.manager,
            stream_registry=main_app.state.stream_registry,
            base_url=url,
            admin_port=args.admin_port,
        )
    )
    _run_servers(main_app, args.host, args.port, admin_app, args.admin_port)


if __name__ == "__main__":
    main()
