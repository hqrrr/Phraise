"""Test that phraise.config handles missing APPDATA env var without KeyError.

``config.py`` imports from ``error_log`` and shares the same ``_APPDATA``
module-level fallback logic.  The import chain must survive a missing
``APPDATA`` environment variable.
"""

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


class TestConfigEnv(unittest.TestCase):
    """Verify config module-level code tolerates a missing APPDATA env var."""

    def setUp(self):
        """Snapshot modules we may evict so tearDown can restore them."""
        self._saved = {
            k: v
            for k, v in sys.modules.items()
            if k in ("phraise", "phraise.error_log", "phraise.config")
        }

    def tearDown(self):
        """Restore evicted modules so subsequent tests are unaffected."""
        for key in ("phraise", "phraise.error_log", "phraise.config"):
            if key in self._saved:
                sys.modules[key] = self._saved[key]
            else:
                sys.modules.pop(key, None)

    def test_import_without_appdata_fallback_path(self):
        """Import config with APPDATA missing; must not raise KeyError."""
        # Evict cached versions so module-level code re-executes
        for key in list(sys.modules.keys()):
            if key in ("phraise", "phraise.error_log", "phraise.config"):
                del sys.modules[key]

        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("APPDATA", None)

            # Re-import fresh — must not raise (imports error_log internally)
            import phraise.config as mod  # noqa: F811

            expected = Path.home() / "AppData" / "Roaming" / "PhrAIse"
            self.assertEqual(mod.CONFIG_DIR, expected)

    def test_import_with_appdata_normal(self):
        """Import config with APPDATA set; must use the env var value."""
        for key in list(sys.modules.keys()):
            if key in ("phraise", "phraise.error_log", "phraise.config"):
                del sys.modules[key]

        test_appdata = "C:\\TestAppData"
        with patch.dict(os.environ, {"APPDATA": test_appdata}, clear=False):
            import phraise.config as mod  # noqa: F811

            expected = Path(test_appdata) / "PhrAIse"
            self.assertEqual(mod.CONFIG_DIR, expected)
