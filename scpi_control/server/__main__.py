"""Lab gateway entry point: python -m scpi_control.server / scpi-web."""

import argparse
import sys
from pathlib import Path

import uvicorn

from scpi_control.server.app import create_app
from scpi_control.server.auth import DEFAULT_CONFIG_DIR, TokenStore
from scpi_control.server.gateway_url import read_base_url, write_base_url
from scpi_control.server.invitations import InvitationStore, format_code
from scpi_control.server.netpolicy import DEFAULT_ALLOWED_PORTS


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

    store = _store(args)
    url = write_base_url(_config_dir(args), args.host, args.port)
    if store.is_empty():
        raw = store.mint("default")
        print("\nGateway ready. Open:\n\n    {0}?token={1}\n".format(url, raw))
    else:
        print("\nGateway ready at {0}\nHand out access with: scpi-web invite <name>\n".format(url))
    allowed_ports = frozenset(args.allow_port) | DEFAULT_ALLOWED_PORTS if args.allow_port else None
    uvicorn.run(
        create_app(token_store=store, invitation_store=_invitations(args), abandon_after=args.abandon_after, allowed_ports=allowed_ports, max_sessions=args.max_sessions),
        host=args.host,
        port=args.port,
    )


if __name__ == "__main__":
    main()
