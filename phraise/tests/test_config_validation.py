"""Unit tests for Config._validate() type checking.

These test the validation logic in isolation: set bad values on
_data, call _validate(), verify per-field fallbacks are applied.
"""

import unittest
from pathlib import Path
from unittest.mock import patch

from phraise.config import Config


class TestConfigValidation(unittest.TestCase):
    """Direct unit tests of the _validate() method."""

    def setUp(self):
        Config._instance = None
        # Patch Path.exists globally so _load() skips reading the real file
        self.patch_path = patch.object(Path, "exists", return_value=False)
        self.mock_path_exists = self.patch_path.start()
        self.config = Config()

    def tearDown(self):
        self.patch_path.stop()
        Config._instance = None

    # -- helpers ---------------------------------------------------------

    def assert_field_fixed(self, key: str, bad_value, expected_fix):
        """Set *key* to *bad_value*, call _validate(), assert fix."""
        self.config._data[key] = bad_value
        self.config._validate()
        self.assertEqual(self.config._data[key], expected_fix)

    # -- max_tokens ------------------------------------------------------

    def test_max_tokens_string_replaced(self):
        """max_tokens='abc' (str) -> replaced with 1024."""
        self.assert_field_fixed("max_tokens", "abc", 1024)

    def test_max_tokens_float_replaced(self):
        """max_tokens=3.14 (float) -> replaced with 1024."""
        self.assert_field_fixed("max_tokens", 3.14, 1024)

    def test_max_tokens_none_replaced(self):
        """max_tokens=None -> replaced with 1024."""
        self.assert_field_fixed("max_tokens", None, 1024)

    def test_max_tokens_list_replaced(self):
        """max_tokens=[1,2,3] (list) -> replaced with 1024."""
        self.assert_field_fixed("max_tokens", [1, 2, 3], 1024)

    def test_max_tokens_int_kept(self):
        """max_tokens=2048 (int) -> kept unchanged."""
        self.assert_field_fixed("max_tokens", 2048, 2048)

    def test_max_tokens_zero_kept(self):
        """max_tokens=0 (int) -> kept (0 is valid int)."""
        self.assert_field_fixed("max_tokens", 0, 0)

    def test_max_tokens_absent_untouched(self):
        """max_tokens not present -> no key added."""
        self.config._data.pop("max_tokens", None)
        self.config._validate()
        self.assertNotIn("max_tokens", self.config._data)

    # -- models ----------------------------------------------------------

    def test_models_string_replaced(self):
        """models='bad' (str) -> replaced with empty dict."""
        self.assert_field_fixed("models", "bad", {})

    def test_models_none_replaced(self):
        """models=None -> replaced with empty dict."""
        self.assert_field_fixed("models", None, {})

    def test_models_list_replaced(self):
        """models=[...] (list) -> replaced with empty dict."""
        self.assert_field_fixed("models", ["a", "b"], {})

    def test_models_int_replaced(self):
        """models=42 (int) -> replaced with empty dict."""
        self.assert_field_fixed("models", 42, {})

    def test_models_dict_kept(self):
        """models={...} (dict) -> kept unchanged."""
        original = {"model_1": {"provider": "test"}}
        self.config._data["models"] = original
        self.config._validate()
        self.assertIs(self.config._data["models"], original)

    def test_models_empty_dict_kept(self):
        """models={} -> kept (empty dict is still a dict)."""
        self.assert_field_fixed("models", {}, {})

    # -- both bad simultaneously -----------------------------------------

    def test_both_bad_fields_fixed(self):
        """Both max_tokens and models wrong -> both fixed."""
        self.config._data["max_tokens"] = "bad"
        self.config._data["models"] = None
        self.config._validate()
        self.assertEqual(self.config._data["max_tokens"], 1024)
        self.assertEqual(self.config._data["models"], {})

    # -- write_error is called -------------------------------------------

    @patch("phraise.config.write_error")
    def test_write_error_called_for_bad_max_tokens(self, mock_we):
        """Bad max_tokens triggers write_error call."""
        self.config._data["max_tokens"] = "abc"
        self.config._validate()
        mock_we.assert_called_once()
        args, _ = mock_we.call_args
        self.assertIn("max_tokens", args[1])

    @patch("phraise.config.write_error")
    def test_write_error_called_for_bad_models(self, mock_we):
        """Bad models triggers write_error call."""
        self.config._data["models"] = None
        self.config._validate()
        mock_we.assert_called_once()
        args, _ = mock_we.call_args
        self.assertIn("models", args[1])

    @patch("phraise.config.write_error")
    def test_write_error_not_called_for_valid(self, mock_we):
        """Valid config does NOT trigger write_error."""
        self.config._data["max_tokens"] = 2048
        self.config._data["models"] = {"m1": {}}
        self.config._validate()
        mock_we.assert_not_called()

    # -- valid config survives unchanged ---------------------------------

    def test_valid_config_unchanged(self):
        """A config matching DEFAULT_CONFIG types passes through unchanged."""
        before = dict(self.config._data)
        self.config._validate()
        self.assertEqual(self.config._data, before)


if __name__ == "__main__":
    unittest.main()
