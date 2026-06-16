# PhrAIse - AI writing assistant
# License: GNU GPLv3
# GitHub: https://github.com/hqrrr/Phraise
# Author: hqrrr
#
# Description: Unit tests for error log env.
"""Test that phraise.error_log handles missing APPDATA env var without KeyError.

When `os.environ` lacks the ``APPDATA`` key (common in sandboxed / CI
environments), the module must fall back to ``Path.home() / "AppData" / "Roaming"``
instead of crashing with a ``KeyError``.
"""

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


class TestErrorLogEnv(unittest.TestCase):
    """Verify error_log module-level code tolerates a missing APPDATA env var."""

    def setUp(self):
        """Snapshot modules we may evict so tearDown can restore them."""
        self._saved = {
            k: v
            for k, v in sys.modules.items()
            if k in ("phraise", "phraise.error_log")
        }

    def tearDown(self):
        """Restore evicted modules so subsequent tests are unaffected."""
        for key in ("phraise", "phraise.error_log"):
            if key in self._saved:
                sys.modules[key] = self._saved[key]
            else:
                sys.modules.pop(key, None)

    def test_import_without_appdata_fallback_path(self):
        """Import error_log with APPDATA missing; must not raise KeyError."""
        # Evict cached versions so module-level code re-executes
        for key in list(sys.modules.keys()):
            if key in ("phraise", "phraise.error_log"):
                del sys.modules[key]

        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("APPDATA", None)

            # Re-import fresh — should not raise
            import phraise.error_log as mod  # noqa: F811

            expected = Path.home() / "AppData" / "Roaming" / "PhrAIse"
            self.assertEqual(mod.LOG_DIR, expected)

    def test_import_with_appdata_normal(self):
        """Import error_log with APPDATA set; must use the env var value."""
        for key in list(sys.modules.keys()):
            if key in ("phraise", "phraise.error_log"):
                del sys.modules[key]

        test_appdata = "C:\\TestAppData"
        with patch.dict(os.environ, {"APPDATA": test_appdata}, clear=False):
            import phraise.error_log as mod  # noqa: F811

            expected = Path(test_appdata) / "PhrAIse"
            self.assertEqual(mod.LOG_DIR, expected)
