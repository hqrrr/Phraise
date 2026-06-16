# PhrAIse - AI writing assistant
# License: GNU GPLv3
# GitHub: https://github.com/hqrrr/Phraise
# Author: hqrrr
#
# Description: Error logging utilities with daily rotation.
import os
import tempfile
import traceback
from datetime import datetime
from pathlib import Path

APP_NAME = "PhrAIse"
_APPDATA = os.environ.get("APPDATA")
if _APPDATA is None:
    try:
        _APPDATA = str(Path.home() / "AppData" / "Roaming")
    except RuntimeError:
        _APPDATA = tempfile.gettempdir()
LOG_DIR = Path(_APPDATA) / APP_NAME
LOG_FILE = LOG_DIR / "error.log"


def _log_file_is_today() -> bool:
    """Return True if LOG_FILE exists and was last modified today."""
    if not LOG_FILE.exists():
        return False
    try:
        mtime = datetime.fromtimestamp(LOG_FILE.stat().st_mtime)
        return mtime.date() == datetime.now().date()
    except OSError:
        return False


def rotate_log():
    """Rotate error.log by date.

    On each application start, keep the current day's error.log so crashes
    and errors from today are still inspectable. If the file belongs to a
    previous day, truncate it to prevent unbounded growth over time.
    """
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    if LOG_FILE.exists() and not _log_file_is_today():
        try:
            LOG_FILE.write_text("", encoding="utf-8")
        except OSError:
            pass


def write_error(exc: Exception, context: str = ""):
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines = [f"[{now}] {context}", traceback.format_exc()]
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write("\n".join(lines))


def log_info(message: str, context: str = ""):
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{now}] {context}: {message}"
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def read_last_error() -> str | None:
    if LOG_FILE.exists():
        try:
            return LOG_FILE.read_text(encoding="utf-8")
        except OSError:
            return None
    return None
