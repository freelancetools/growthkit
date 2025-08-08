"""
Helper block to ensure the locally-generated `config/` package is importable
when this module is invoked via the `gk-slack` console entry-point.

When the package is installed, the entry-point lives inside the virtualenv's
`bin/` directory, meaning Python's default import search path does **not**
include the directory from which the user runs the command.

The workspace configuration lives in a plain `config/` package that sits next
to the repo's root. Inserting the CWD early guarantees that
`import config.slack.workspace` succeeds regardless of where the package
itself resides.
"""

import sys
from pathlib import Path as _Path

_cwd = _Path.cwd()
if str(_cwd) not in sys.path:
    sys.path.insert(0, str(_cwd))

# Clean up the helpers from the public namespace
del _Path, _cwd
