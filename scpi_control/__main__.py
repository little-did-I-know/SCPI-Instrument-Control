"""`python -m scpi_control` runs the `scpi` command-line tool."""

import sys

from scpi_control.cli import main

if __name__ == "__main__":
    sys.exit(main())
