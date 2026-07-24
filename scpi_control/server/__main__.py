"""Lab gateway entry point: python -m scpi_control.server / scpi-web."""

import argparse
import sys
from pathlib import Path

import uvicorn

from scpi_control.server.app import create_app
from scpi_control.server.auth import DEFAULT_CONFIG_DIR, DuplicateTokenName, TokenStore
from scpi_control.server.netpolicy import DEFAULT_ALLOWED_PORTS


def _store(args) -> TokenStore:
    config_dir = Path(args.config_dir) if args.config_dir else DEFAULT_CONFIG_DIR
    return TokenStore(str(config_dir / "tokens.json"))


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

    if args.command == "token":
        store = _store(args)
        if args.token_command == "add":
            try:
                print("token {0!r} created. Copy it now, it is not stored:\n\n    {1}\n".format(args.name, store.mint(args.name)))
            except DuplicateTokenName as exc:
                sys.exit(str(exc))
        elif args.token_command == "list":
            names = store.names()
            print("\n".join(names) if names else "no tokens")
        elif args.token_command == "revoke":
            if not store.revoke(args.name):
                sys.exit("no token named {0!r}".format(args.name))
            print("revoked {0!r}".format(args.name))
        return

    store = _store(args)
    if store.is_empty():
        raw = store.mint("default")
        print("\nGateway ready. Open:\n\n    http://{0}:{1}/?token={2}\n".format(args.host, args.port, raw))
    allowed_ports = frozenset(args.allow_port) | DEFAULT_ALLOWED_PORTS if args.allow_port else None
    uvicorn.run(create_app(token_store=store, abandon_after=args.abandon_after, allowed_ports=allowed_ports), host=args.host, port=args.port)


if __name__ == "__main__":
    main()
