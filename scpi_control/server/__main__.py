"""Lab gateway entry point: python -m scpi_control.server / scpi-web."""

import argparse

import uvicorn

from scpi_control.server.app import create_app


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(prog="scpi-web", description="SCPI Instrument Control web gateway")
    parser.add_argument("--host", default="127.0.0.1", help="bind address (use 0.0.0.0 to expose on the LAN)")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args(argv)
    uvicorn.run(create_app(), host=args.host, port=args.port)


if __name__ == "__main__":
    main()
