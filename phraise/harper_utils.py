"""Utility functions for resolving the Harper LSP binary path.

Supports both development (source) and frozen (PyInstaller) environments.
"""

import os
import sys
from pathlib import Path


def get_harper_binary_path() -> Path | None:
    """Resolve the path to the ``harper-ls`` binary.

    Resolution strategy
    -------------------
    1. If the process is frozen (PyInstaller ``--onefile``), look under
       ``sys._MEIPASS / "phraise" / "lsp" / "harper-ls.exe"``.
    2. Otherwise, assume a development / source layout and look at
       ``Path(__file__).parent / "lsp" / "harper-ls.exe"``.

    Returns
    -------
    Path | None
        The resolved path if the binary exists, ``None`` otherwise.
    """
    base: Path

    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        # PyInstaller one-file mode — files are extracted to _MEIPASS.
        base = Path(sys._MEIPASS)  # type: ignore[arg-type]
        candidate = base / "phraise" / "lsp" / "harper-ls.exe"
    else:
        # Development / source mode.
        candidate = Path(__file__).parent / "lsp" / "harper-ls.exe"

    if candidate.exists():
        return candidate.resolve()

    return None


def is_harper_available() -> bool:
    """Check whether the Harper LSP binary is available on this system.

    Returns ``True`` only when :func:`get_harper_binary_path` returns a
    path **and** the file at that path exists and is readable.
    """
    path = get_harper_binary_path()
    if path is None:
        return False
    # ``path`` is already verified to exist inside ``get_harper_binary_path``,
    # but we guard against the edge case where the file was removed between
    # the check and this call.
    return path.exists() and os.access(str(path), os.R_OK)
