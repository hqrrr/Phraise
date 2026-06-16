# PhrAIse - AI writing assistant
# License: GNU GPLv3
# GitHub: https://github.com/hqrrr/Phraise
# Author: hqrrr
#
# Description: Unit tests for config bad types.
"""Integration tests: malformed settings.json does not crash downstream.

Writes a corrupted settings.json, loads it via Config, and verifies
that:
  1. Type validation in _load() applies per-field fallbacks.
  2. Downstream code (e.g. _get_model_config()) does NOT crash.
"""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import phraise.config as cfg_module
import phraise.llm_client as llm_module
from phraise.config import Config, CONFIG_DIR, CONFIG_FILE
from phraise.llm_client import _get_model_config


class TestConfigBadTypesLoad(unittest.TestCase):
    """Load corrupted settings.json → validation fixes, no crash."""

    def setUp(self):
        Config._instance = None
        # Redirect CONFIG_DIR and CONFIG_FILE to a temp directory so
        # _load() reads/writes our test file, not the real one.
        self.tmp = Path(tempfile.mkdtemp(prefix="phraise_test_"))
        self.patch_dir = patch.object(
            CONFIG_DIR.__class__, "parent",
            return_value=self.tmp.parent,
        )
        # Simpler: patch the module-level variables directly
        self.patches = [
            patch("phraise.config.CONFIG_DIR", self.tmp),
            patch("phraise.config.CONFIG_FILE", self.tmp / "settings.json"),
        ]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        Config._instance = None
        import shutil
        shutil.rmtree(str(self.tmp), ignore_errors=True)

    # -- helpers ---------------------------------------------------------

    def _write_settings(self, data: dict):
        """Write a settings.json with *data* into the temp directory."""
        (self.tmp / "settings.json").write_text(
            json.dumps(data, indent=2), encoding="utf-8"
        )

    def _fresh_config(self) -> Config:
        """Return a fresh Config instance (forces _load from disk)."""
        Config._instance = None
        cfg = Config()
        # Update module-level config references so downstream code
        # (e.g. _get_model_config) reads from our test instance.
        cfg_module.config = cfg
        llm_module.config = cfg
        return cfg

    # -- max_tokens ------------------------------------------------------

    def test_max_tokens_string_does_not_crash(self):
        """settings.json with max_tokens='abc' → loaded safely."""
        self._write_settings({"max_tokens": "abc"})
        cfg = self._fresh_config()
        # After validation, max_tokens should be the int default
        self.assertIsInstance(cfg._data.get("max_tokens"), int)

    def test_max_tokens_null_does_not_crash(self):
        """settings.json with max_tokens=null → loaded safely."""
        self._write_settings({"max_tokens": None})
        cfg = self._fresh_config()
        self.assertIsInstance(cfg._data.get("max_tokens"), int)

    # -- models ----------------------------------------------------------

    def test_models_string_does_not_crash(self):
        """settings.json with models='bad' → models is a dict."""
        self._write_settings({"models": "bad"})
        cfg = self._fresh_config()
        self.assertIsInstance(cfg._data.get("models"), dict)

    def test_models_null_does_not_crash(self):
        """settings.json with models=null → models is a dict."""
        self._write_settings({"models": None})
        cfg = self._fresh_config()
        self.assertIsInstance(cfg._data.get("models"), dict)

    def test_models_list_does_not_crash(self):
        """settings.json with models=[...] → models is a dict."""
        self._write_settings({"models": ["a", "b"]})
        cfg = self._fresh_config()
        self.assertIsInstance(cfg._data.get("models"), dict)

    # -- downstream protection -------------------------------------------

    def test_get_model_config_does_not_crash_with_bad_models(self):
        """models=null in settings.json → _get_model_config() returns None (safe)."""
        self._write_settings({"models": None})
        cfg = self._fresh_config()
        # _get_model_config accesses models.model_1 — should not crash
        result = _get_model_config("model_1")
        # After validation, models is {} so _get_model_config returns None
        self.assertIsNone(result)

    def test_get_model_config_does_not_crash_with_missing_models(self):
        """No models key → _get_model_config returns None."""
        self._write_settings({"some_other_key": True})
        cfg = self._fresh_config()
        result = _get_model_config("model_1")
        self.assertIsNotNone(result)  # DEFAULT_CONFIG has models

    # -- valid config unchanged ------------------------------------------

    def test_valid_settings_json_unchanged(self):
        """A clean settings.json passes through type validation unchanged."""
        valid = {
            "models": {
                "model_1": {
                    "provider": "gemini",
                    "api_key": "test-key",
                    "model_name": "gemini-2.0-flash",
                    "max_tokens": 4096,
                }
            }
        }
        self._write_settings(valid)
        cfg = self._fresh_config()
        self.assertEqual(
            cfg._data["models"]["model_1"]["max_tokens"], 4096
        )


if __name__ == "__main__":
    unittest.main()
