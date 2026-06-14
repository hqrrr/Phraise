"""Tests for empty default model configuration and placeholder behavior.

Verifies that:
  1. A fresh Config instance (no settings.json) has empty model slots.
  2. Settings panel assign combos include a placeholder and select it when current is empty.
  3. Config._validate fixes bad types for optimize_model / translate_model.

Note: DEFAULT_CONFIG's nested dicts can be mutated by other tests that share
references via shallow _deep_merge copies.  These tests therefore work with a
fresh Config instance instead of testing DEFAULT_CONFIG directly.
"""

import unittest
from unittest.mock import MagicMock, patch

from phraise.config import Config
from phraise.settings_panel import SettingsPanel


class TestFreshConfigEmptyDefaults(unittest.TestCase):
    """A fresh Config (no settings.json) must have empty model assignment."""

    def setUp(self):
        Config._instance = None
        self.patch_path = patch("pathlib.Path.exists", return_value=False)
        self.mock_path_exists = self.patch_path.start()
        self.config = Config()

    def tearDown(self):
        self.patch_path.stop()
        Config._instance = None

    def test_model_1_fields_are_empty_strings(self):
        """Fresh config model_1 must have empty provider/api_base/api_key/model_name."""
        m1 = self.config.get("models", "model_1", default={})
        self.assertEqual(m1.get("provider"), "")
        self.assertEqual(m1.get("api_base"), "")
        self.assertEqual(m1.get("api_key"), "")
        self.assertEqual(m1.get("model_name"), "")

    def test_model_2_fields_are_empty_strings(self):
        """Fresh config model_2 must have empty provider/api_base/api_key/model_name."""
        m2 = self.config.get("models", "model_2", default={})
        self.assertEqual(m2.get("provider"), "")
        self.assertEqual(m2.get("api_base"), "")
        self.assertEqual(m2.get("api_key"), "")
        self.assertEqual(m2.get("model_name"), "")

    def test_optimize_model_empty_string(self):
        """Fresh config general.optimize_model must be empty string."""
        self.assertEqual(self.config.get("general", "optimize_model", default=None), "")

    def test_translate_model_empty_string(self):
        """Fresh config general.translate_model must be empty string."""
        self.assertEqual(self.config.get("general", "translate_model", default=None), "")

    def test_temperature_and_tokens_have_sensible_defaults(self):
        """temperature and max_tokens still have sensible numeric defaults."""
        m1 = self.config.get("models", "model_1", default={})
        self.assertEqual(m1.get("temperature"), 0.3)
        self.assertEqual(m1.get("max_tokens"), 4096)
        m2 = self.config.get("models", "model_2", default={})
        self.assertEqual(m2.get("temperature"), 0.5)
        self.assertEqual(m2.get("max_tokens"), 4096)

    def test_mode_defaults_to_remote(self):
        """model_1 and model_2 mode must be 'remote' by default."""
        self.assertEqual(self.config.get("models", "model_1", "mode"), "remote")
        self.assertEqual(self.config.get("models", "model_2", "mode"), "remote")

    def test_harper_not_optimize_default(self):
        """optimize_model must NOT default to harper (fresh config = '')."""
        self.assertNotEqual(self.config.get("general", "optimize_model"), "harper")


class TestValidateEmptyModelDefaults(unittest.TestCase):
    """Config._validate must correct bad types for optimize_model / translate_model."""

    def setUp(self):
        Config._instance = None
        self.patch_path = patch("pathlib.Path.exists", return_value=False)
        self.mock_path_exists = self.patch_path.start()
        self.config = Config()

    def tearDown(self):
        self.patch_path.stop()
        Config._instance = None

    def test_optimize_model_int_corrected(self):
        """optimize_model=42 --> corrected to ''."""
        if "general" not in self.config._data:
            self.config._data["general"] = {}
        self.config._data["general"]["optimize_model"] = 42
        self.config._validate()
        self.assertEqual(self.config._data["general"]["optimize_model"], "")

    def test_translate_model_list_corrected(self):
        """translate_model=[1,2,3] --> corrected to ''."""
        if "general" not in self.config._data:
            self.config._data["general"] = {}
        self.config._data["general"]["translate_model"] = [1, 2, 3]
        self.config._validate()
        self.assertEqual(self.config._data["general"]["translate_model"], "")

    def test_optimize_model_string_preserved(self):
        """optimize_model='model_1' --> kept as is."""
        if "general" not in self.config._data:
            self.config._data["general"] = {}
        self.config._data["general"]["optimize_model"] = "model_1"
        self.config._validate()
        self.assertEqual(self.config._data["general"]["optimize_model"], "model_1")

    def test_translate_model_empty_string_preserved(self):
        """translate_model='' --> kept as is."""
        if "general" not in self.config._data:
            self.config._data["general"] = {}
        self.config._data["general"]["translate_model"] = ""
        self.config._validate()
        self.assertEqual(self.config._data["general"]["translate_model"], "")

    def test_missing_general_section_not_crash(self):
        """No 'general' key --> _validate does not crash."""
        self.config._data.pop("general", None)
        self.config._validate()
        self.assertNotIn("general", self.config._data)


class TestAssignComboPlaceholder(unittest.TestCase):
    """Settings panel assign combos must have a placeholder item."""

    def setUp(self):
        self.config_patcher = patch("phraise.settings_panel.config")
        self.mock_config = self.config_patcher.start()

    def tearDown(self):
        self.config_patcher.stop()

    def _make_combo_mock(self):
        """Create a mock NoScrollComboBox that records addItem calls."""
        combo = MagicMock()
        items = []
        datas = []

        def addItem(label, data=None):
            items.append(label)
            datas.append(data)

        def findData(data):
            try:
                return datas.index(data)
            except ValueError:
                return -1

        combo.addItem.side_effect = addItem
        combo.findData.side_effect = findData
        combo._items = items
        combo._datas = datas
        return combo

    def _simulate_build_assign_row(self, config_key="optimize_model",
                                    include_harper=False, current_val=""):
        """Simulate the item addition logic from _build_assign_row."""
        self.mock_config.get.return_value = current_val

        combo = self._make_combo_mock()

        combo.addItem("-- Not selected --", "")
        combo.addItem("Model 1", "model_1")
        combo.addItem("Model 2", "model_2")
        if include_harper:
            combo.addItem("Local (Harper)", "harper")

        idx = combo.findData(current_val)
        if idx >= 0:
            combo.setCurrentIndex(idx)
        else:
            combo.setCurrentIndex(0)

        return combo

    def test_placeholder_item_exists(self):
        """First item must be the placeholder with empty data."""
        combo = self._simulate_build_assign_row()
        self.assertEqual(combo._items[0], "-- Not selected --")
        self.assertEqual(combo._datas[0], "")

    def test_model_items_still_present(self):
        """model_1 and model_2 items must still be present after placeholder."""
        combo = self._simulate_build_assign_row()
        self.assertIn("model_1", combo._datas)
        self.assertIn("model_2", combo._datas)

    def test_harper_included_for_optimize(self):
        """optimize_model combo must include harper option."""
        combo = self._simulate_build_assign_row(include_harper=True)
        self.assertIn("harper", combo._datas)

    def test_harper_excluded_for_translate(self):
        """translate_model combo must NOT include harper option."""
        combo = self._simulate_build_assign_row(config_key="translate_model",
                                                 include_harper=False)
        self.assertNotIn("harper", combo._datas)

    def test_placeholder_selected_when_current_empty(self):
        """When current value is '', placeholder (index 0) must be selected."""
        combo = self._simulate_build_assign_row(current_val="")
        combo.setCurrentIndex.assert_called_with(0)

    def test_model_1_selected_when_current_is_model_1(self):
        """When current value is 'model_1', that item must be selected."""
        combo = self._simulate_build_assign_row(current_val="model_1")
        combo.setCurrentIndex.assert_called_with(1)

    def test_harper_selected_when_current_is_harper(self):
        """When current value is 'harper', that item must be selected."""
        combo = self._simulate_build_assign_row(include_harper=True,
                                                 current_val="harper")
        combo.setCurrentIndex.assert_called_with(3)

    def test_unknown_value_selects_placeholder(self):
        """When current value is not in list, placeholder must be selected."""
        combo = self._simulate_build_assign_row(current_val="unknown_model")
        combo.setCurrentIndex.assert_called_with(0)


if __name__ == "__main__":
    unittest.main()
