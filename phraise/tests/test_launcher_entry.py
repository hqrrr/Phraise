# PhrAIse - AI writing assistant
# License: GNU GPLv3
# GitHub: https://github.com/hqrrr/Phraise
# Author: hqrrr
#
# Description: Unit tests for launcher entry.
"""Contract tests for the PyInstaller launcher fix.

The app currently uses ``python -m phraise.main`` as entry point, which relies on
relative imports and fails when PyInstaller bundles it (``ImportError: attempted
relative import with no known parent package``).

The fix introduces a root-level ``run.py`` that performs absolute imports and
serves as the PyInstaller entry point.

Each test verifies a necessary property of the fix without creating or modifying
``run.py`` itself.
"""

import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class TestLauncherContract(unittest.TestCase):
    """Verifies the contract the ``run.py`` launcher must satisfy."""

    def test_absolute_import_main_callable(self):
        """``from phraise.main import main`` succeeds and ``main`` is callable."""
        from phraise.main import main

        self.assertTrue(callable(main))

    def test_launcher_script_exists_and_imports_main(self):
        """A root-level ``run.py`` exists and imports ``main`` from ``phraise.main``.

        This test is expected to **FAIL (RED)** until ``run.py`` is created.
        """
        run_py = PROJECT_ROOT / "run.py"
        self.assertTrue(
            run_py.exists(),
            f"Expected {run_py} to exist",
        )
        text = run_py.read_text(encoding="utf-8")
        self.assertIn(
            "from phraise.main import main",
            text,
            f"{run_py} must contain the absolute import line",
        )

    def test_main_module_guard_intact(self):
        """``phraise/main.py`` still has the ``if __name__ == "__main__"`` guard."""
        main_py = PROJECT_ROOT / "phraise" / "main.py"
        self.assertTrue(main_py.exists())
        text = main_py.read_text(encoding="utf-8")
        self.assertIn('if __name__ == "__main__":', text)
