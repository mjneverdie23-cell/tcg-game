"""`python -m footypred` opens the web app; `python -m footypred <command>`
runs any `footy` command."""

import sys

from footypred.cli import main

if __name__ == "__main__":
    main(sys.argv[1:] or ["app"])
