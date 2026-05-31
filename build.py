import os
import sys
from pathlib import Path

ROOT = Path(__file__).parent.resolve()


def build():
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
        entry,
    ]

    import subprocess
    subprocess.run(build_cmd, check=True)
    print("Build complete!")


if __name__ == "__main__":
    build()
