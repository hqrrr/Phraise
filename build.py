import os
import sys
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).parent.resolve()

HARPER_VERSION = "v2.4.0"
HARPER_URL = f"https://github.com/Automattic/harper/releases/download/{HARPER_VERSION}/harper-ls-x86_64-pc-windows-msvc.zip"
HARPER_DIR = ROOT / "phraise" / "lsp"
HARPER_EXE = HARPER_DIR / "harper-ls.exe"


def _ensure_harper_binary():
    """Download Harper grammar checker binary if not already present."""
    HARPER_DIR.mkdir(parents=True, exist_ok=True)

    if HARPER_EXE.exists() and HARPER_EXE.stat().st_size > 0:
        print(f"Harper binary already cached at {HARPER_EXE}")
        return True

    print(f"Downloading Harper {HARPER_VERSION}...")
    zip_path = HARPER_DIR / "harper-ls.zip"

    try:
        urllib.request.urlretrieve(HARPER_URL, zip_path)
        print(f"Downloaded to {zip_path}")

        with zipfile.ZipFile(zip_path, 'r') as zf:
            zf.extractall(HARPER_DIR)

        zip_path.unlink()

        if HARPER_EXE.exists():
            print(f"Harper binary ready: {HARPER_EXE} ({HARPER_EXE.stat().st_size} bytes)")
            return True
        else:
            print("WARNING: harper-ls.exe not found after extraction")
            return False
    except Exception as e:
        print(f"WARNING: Harper binary download failed: {e}")
        print("Build will continue but Harper won't be available in the bundled exe.")
        return False


def build():
    _ensure_harper_binary()

    entry = str(ROOT / "phraise" / "main.py")
    dist = str(ROOT / "dist")
    work = str(ROOT / "build")

    build_cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name=PhrAIse",
        "--onefile",
        "--windowed",
        "--noconsole",
        f"--distpath={dist}",
        f"--workpath={work}",
        f"--specpath={work}",
        "--hidden-import=pynput.keyboard._win32",
        "--hidden-import=pynput.mouse._win32",
        "--hidden-import=uiautomation",
        "--hidden-import=PySide6",
        f"--add-data={ROOT / 'phraise' / 'assets'};phraise/assets",
        "--collect-all", "PySide6",
        f"--add-binary={ROOT / 'phraise' / 'lsp' / 'harper-ls.exe'};phraise/lsp",
        entry,
    ]

    import subprocess
    subprocess.run(build_cmd, check=True)
    print("Build complete!")


if __name__ == "__main__":
    build()
