"""Tests for the searchable provider dropdown in SettingsPanel."""

import unittest
from unittest.mock import MagicMock, patch

from PySide6.QtWidgets import QApplication

from phraise.settings_panel import SettingsPanel
from phraise import provider_manager


# Singleton QApplication required for Qt widget tests.
_app = QApplication.instance() or QApplication([])


class _DeletedAttr:
    def __get__(self, obj, objtype=None):
        raise RuntimeError("Internal C++ object already deleted")

    def __set__(self, obj, value):
        pass


_MOCK_THEME_COLORS = {
    "surface": "#2e2e3e",
    "text": "#cdd6f4",
    "border": "#45475a",
    "accent": "#6c5ce7",
    "bg_darker": "#181825",
    "text_muted": "#a6adc8",
    "surface_hover": "#45475a",
}


def _make_sp(**overrides) -> SettingsPanel:
    with patch.object(SettingsPanel, "__init__", return_value=None):
        sp = SettingsPanel.__new__(SettingsPanel)
    sp._is_closing = False
    sp._provider_combos = []
    sp._theme_colors = _MOCK_THEME_COLORS
    for attr, val in overrides.items():
        setattr(sp, attr, val)
    return sp


class TestProviderDropdownBehavior(unittest.TestCase):
    """Behavior of _build_provider_row with dynamic provider list."""

    def setUp(self):
        self._patch_config = patch("phraise.settings_panel.config")
        self._patch_init = patch("phraise.settings_panel.init_providers")
        self._patch_config.start()
        self._patch_init.start()
        provider_manager.reset_providers()

    def tearDown(self):
        self._patch_config.stop()
        self._patch_init.stop()
        provider_manager.reset_providers()
        for attr in ("_provider_combos",):
            try:
                delattr(SettingsPanel, attr)
            except AttributeError:
                pass

    def _build_row(self, cfg):
        sp = _make_sp()
        layout = MagicMock()
        combo, api_base_entry = sp._build_provider_row(layout, cfg, "model_1")
        return sp, combo, api_base_entry, layout

    def test_custom_sentinel_is_last_item(self):
        _sp, combo, _api, _layout = self._build_row({})
        count = combo.count()
        self.assertGreater(count, 1)
        self.assertEqual(combo.itemData(count - 1), "custom")

    def test_select_preset_hides_api_base(self):
        _sp, combo, _api, layout = self._build_row({})
        idx = combo.findData("openai")
        self.assertGreaterEqual(idx, 0)
        combo.setCurrentIndex(idx)
        added_rows = [call.args[0] for call in layout.addWidget.call_args_list]
        api_base_row = added_rows[1]
        self.assertFalse(api_base_row.isVisible())

    def test_select_custom_shows_api_base(self):
        _sp, combo, _api, layout = self._build_row({})
        idx = combo.findData("custom")
        self.assertGreaterEqual(idx, 0)
        combo.setCurrentIndex(idx)
        added_rows = [call.args[0] for call in layout.addWidget.call_args_list]
        api_base_row = added_rows[1]
        self.assertTrue(api_base_row.isVisible())

    def test_preset_auto_fills_api_base(self):
        _sp, combo, api_base_entry, _layout = self._build_row({})
        idx = combo.findData("openai")
        combo.setCurrentIndex(idx)
        self.assertEqual(api_base_entry.text(), "https://api.openai.com/v1")

    def test_provider_restored_by_id(self):
        cfg = {"provider": "deepseek", "api_base": ""}
        _sp, combo, api_base_entry, _layout = self._build_row(cfg)
        self.assertEqual(combo.currentData(), "deepseek")
        self.assertEqual(api_base_entry.text(), "https://api.deepseek.com/v1")

    def test_provider_restored_by_api_base(self):
        cfg = {"provider": "", "api_base": "https://api.moonshot.cn/v1"}
        _sp, combo, api_base_entry, _layout = self._build_row(cfg)
        self.assertEqual(combo.currentData(), "kimi")
        self.assertEqual(api_base_entry.text(), "https://api.moonshot.cn/v1")

    def test_unknown_saved_provider_falls_back_to_custom(self):
        cfg = {"provider": "unknown-provider", "api_base": "https://custom.example.com"}
        _sp, combo, _api, _layout = self._build_row(cfg)
        self.assertEqual(combo.currentData(), "custom")

    def test_combo_is_editable_and_searchable(self):
        _sp, combo, _api, _layout = self._build_row({})
        self.assertTrue(combo.isEditable())
        self.assertIsNotNone(combo.completer())

    def test_on_providers_loaded_preserves_selection(self):
        sp = _make_sp()
        layout = MagicMock()
        combo, _api = sp._build_provider_row(layout, {}, "model_1")
        combo.setCurrentIndex(combo.findData("deepseek"))
        provider_manager._set_providers([
            {"id": "openai", "label": "OpenAI", "api_base": "https://api.openai.com/v1"},
            {"id": "deepseek", "label": "DeepSeek", "api_base": "https://api.deepseek.com/v1"},
        ])
        sp._on_providers_loaded()
        self.assertEqual(combo.currentData(), "deepseek")

    def test_on_providers_loaded_closing_returns_safely(self):
        sp = _make_sp(_is_closing=True)
        SettingsPanel._provider_combos = _DeletedAttr()
        try:
            sp._on_providers_loaded()
        except Exception as e:
            self.fail(f"_on_providers_loaded raised {type(e).__name__}: {e}")

    def test_apply_provider_selection_custom_shows_row(self):
        sp = _make_sp()
        combo = MagicMock()
        combo.currentData.return_value = "custom"
        api_base_entry = MagicMock()
        api_base_row = MagicMock()
        combo._api_base_entry = api_base_entry
        combo._api_base_row = api_base_row
        sp._apply_provider_selection(combo)
        api_base_row.setVisible.assert_called_once_with(True)


if __name__ == "__main__":
    unittest.main()
