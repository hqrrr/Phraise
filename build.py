# PhrAIse - AI writing assistant
# License: GNU GPLv3
# GitHub: https://github.com/hqrrr/Phraise
# Author: hqrrr
#
# Description: PyInstaller build script for packaging PhrAIse into a standalone executable.

import os
import subprocess
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

    entry = str(ROOT / "run.py")
    dist = str(ROOT / "dist")
    work = str(ROOT / "build")

    sys.path.insert(0, str(ROOT))
    from phraise.__version__ import VERSION

    # PySide6 modules imported by the application.
    hiddenimports = [
        "PySide6.QtCore",
        "PySide6.QtGui",
        "PySide6.QtWidgets",
        "PySide6.QtSvg",
        "pynput.keyboard._win32",
        "pynput.mouse._win32",
        "uiautomation",
        "pythoncom",
    ]

    # Unused PySide6/Qt modules that should not be analysed or bundled.
    excludes = [
        # WebEngine
        "PySide6.QtWebEngineCore",
        "PySide6.QtWebEngineQuick",
        "PySide6.QtWebEngineWidgets",
        "PySide6.QtWebChannel",
        # QML / Quick
        "PySide6.QtQml",
        "PySide6.QtQuick",
        "PySide6.QtQuick3D",
        "PySide6.QtQuickWidgets",
        "PySide6.QtQuickControls2",
        "PySide6.QtQuickTemplates2",
        "PySide6.QtQuickLayouts",
        "PySide6.QtQuickDialogs2",
        "PySide6.QtQuickTest",
        "PySide6.QtQmlModels",
        "PySide6.QtQmlWorkerScript",
        # 3D
        "PySide6.Qt3DCore",
        "PySide6.Qt3DAnimation",
        "PySide6.Qt3DRender",
        "PySide6.Qt3DInput",
        "PySide6.Qt3DLogic",
        "PySide6.Qt3DExtras",
        # Charts / Graphs / Visualization
        "PySide6.QtCharts",
        "PySide6.QtChartsQml",
        "PySide6.QtDataVisualization",
        "PySide6.QtGraphs",
        "PySide6.QtGraphsWidgets",
        # Multimedia
        "PySide6.QtMultimedia",
        "PySide6.QtMultimediaWidgets",
        "PySide6.QtMultimediaQuick",
        "PySide6.QtSpatialAudio",
        # Positioning / Location / Sensors
        "PySide6.QtPositioning",
        "PySide6.QtLocation",
        "PySide6.QtSensors",
        # Serial / Bus / SQL
        "PySide6.QtSerialPort",
        "PySide6.QtSerialBus",
        "PySide6.QtSql",
        # Test / Designer / Help
        "PySide6.QtTest",
        "PySide6.QtDesigner",
        "PySide6.QtDesignerComponents",
        "PySide6.QtHelp",
        "PySide6.QtUiTools",
        # Networking extras (HTTP is done via httpx/openai, not QtNetwork)
        "PySide6.QtNetwork",
        "PySide6.QtNetworkAuth",
        "PySide6.QtRemoteObjects",
        # Other unused
        "PySide6.QtXml",
        "PySide6.QtXmlPatterns",
        "PySide6.QtConcurrent",
        "PySide6.QtDBus",
        "PySide6.QtPrintSupport",
        "PySide6.QtBluetooth",
        "PySide6.QtNfc",
        "PySide6.QtOpenGL",
        "PySide6.QtOpenGLWidgets",
        "PySide6.QtPdf",
        "PySide6.QtPdfWidgets",
        "PySide6.QtSvgWidgets",
        "PySide6.QtTextToSpeech",
        "PySide6.QtScxml",
        "PySide6.QtStateMachine",
        "PySide6.QtVirtualKeyboard",
        "PySide6.QtWebView",
        "PySide6.QtHttpServer",
        "PySide6.QtGrpc",
        "PySide6.QtProtobuf",
        "PySide6.QtShaderTools",
    ]

    build_cmd = [
        sys.executable, "-m", "PyInstaller",
        f"--name=PhrAIse_{VERSION}",
        "--onefile",
        "--windowed",
        "--noconsole",
        "--noupx",
        f"--distpath={dist}",
        f"--workpath={work}",
        f"--specpath={work}",
        f"--icon={ROOT / 'phraise' / 'assets' / 'phraise_logo.ico'}",
        f"--add-data={ROOT / 'phraise' / 'assets'};phraise/assets",
        f"--add-binary={ROOT / 'phraise' / 'lsp' / 'harper-ls.exe'};phraise/lsp",
    ]

    for mod in hiddenimports:
        build_cmd.extend(["--hidden-import", mod])

    for mod in excludes:
        build_cmd.extend(["--exclude-module", mod])

    build_cmd.append(entry)

    subprocess.run(build_cmd, check=True)
    print("Build complete!")


if __name__ == "__main__":
    build()
