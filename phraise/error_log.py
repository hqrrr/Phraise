import os
import traceback
from datetime import datetime
from pathlib import Path

APP_NAME = "PhrAIse"
LOG_DIR = Path(os.environ["APPDATA"]) / APP_NAME
LOG_FILE = LOG_DIR / "error.log"


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
