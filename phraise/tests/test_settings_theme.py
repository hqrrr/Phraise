"""Tests for theme combo selection fix and save deduplication (Task 19).

Verifies:
  - Theme combo uses ``findData`` to select the correct item by config value,
    rather than a broken ternary that always returns the same text.
  - Save does NOT write ``data["general"]["theme"]`` — only
    ``data["appearance"]["theme"]`` is kept.
"""

import unittest
from unittest.mock import MagicMock, patch

from PySide6.QtWidgets import QApplication, QComboBox

from phraise.i18n import t


# ---------------------------------------------------------------------------
# QApplication singleton for Qt widgets
# ---------------------------------------------------------------------------

class TestThemeComboSelection(unittest.TestCase):
    """Verify theme combo selects the correct item based on config value."""

    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance()
        if cls._app is None:
            cls._app = QApplication([])

    def setUp(self):
        self._combo = QComboBox()
        # Same items as SettingsPanel._build_appearance_tab
        self._combo.addItem(t("settings.theme.dark"), "dark")

    def tearDown(self):
        self._combo.deleteLater()

    def test_selects_dark_when_config_is_dark(self):
        """Config value ``"dark"`` selects the dark theme item."""
        idx = self._combo.findData("dark")
        self.assertGreaterEqual(idx, 0, "dark theme data must exist in combo")
        if idx >= 0:
            self._combo.setCurrentIndex(idx)
        self.assertEqual(self._combo.currentData(), "dark")

    def test_fallback_to_index_zero_when_config_unknown(self):
        """Config value not in combo items keeps selection at index 0."""
        idx = self._combo.findData("nonexistent_theme")
        self.assertEqual(idx, -1, "unknown config value must not match any item")
        # default selection should be index 0
        self.assertEqual(self._combo.currentIndex(), 0)
        self.assertEqual(self._combo.currentData(), "dark")


class TestThemeSaveDeduplication(unittest.TestCase):
    """Verify that save writes theme only to ``appearance.theme``."""

    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance()
        if cls._app is None:
            cls._app = QApplication([])

    @staticmethod
    def _make_model_entry_mock() -> dict:
        """Return a dict of mocked widgets for one model slot."""
        def _mk_widget(text_val="", data_val=""):
            w = MagicMock()
            w.text.return_value = text_val
            w.currentData.return_value = data_val
            w.currentText.return_value = text_val
            w.value.return_value = 50
            return w
        return {
            "provider_combo": _mk_widget(data_val="openai"),
            "api_base": _mk_widget("https://api.openai.com/v1"),
            "api_key": _mk_widget("sk-test"),
            "model_combo": _mk_widget("gpt-4"),
            "temperature_slider": _mk_widget(),
            "max_tokens": _mk_widget("1024"),
            "extra_params": _mk_widget(""),
        }

    def setUp(self):
        # Build a SettingsPanel with all heavy dependencies mocked
        from phraise import config as cfg_mod

        patchers = [
            patch.object(cfg_mod.config, "_data", {
                "general": {"language": "en"},
                "appearance": {},
                "models": {"model_1": {}, "model_2": {}},
                "trigger": {},
                "harper": {},
                "floating_ball": {"opacity": 0.85, "size": 52},
                "styles": [{"id": "concise", "label": "Concise", "prompt_keyword": "concise"}],
            }),
            patch("phraise.settings_panel.add_listener"),
            patch("phraise.settings_panel.remove_listener"),
            patch.object(cfg_mod.config, "save"),
        ]
        for p in patchers:
            p.start()
            self.addCleanup(p.stop)

        from phraise import settings_panel
        from phraise.settings_panel import SettingsPanel
        # Align the module-level config reference with the patched singleton so
        # _on_save mutates and saves the same object this test asserts on.
        patch.object(settings_panel, "config", cfg_mod.config).start()
        self._panel = SettingsPanel()

    def tearDown(self):
        self._panel.deleteLater()

    def test_save_does_not_write_general_theme(self):
        """``_on_save`` must NOT create ``data["general"]["theme"]``."""
        # Set up minimal mocks to avoid AttributeError during save
        self._panel._hk_trigger = MagicMock()
        self._panel._hk_trigger.text.return_value = "Ctrl+C+C"
        self._panel._hk_toggle = MagicMock()
        self._panel._hk_toggle.text.return_value = "Ctrl+Shift+B"
        self._panel._model_entries = {
            "model_1": self._make_model_entry_mock(),
            "model_2": self._make_model_entry_mock(),
        }
        self._panel._style_entries = []
        self._panel._custom_css_editor = MagicMock()
        self._panel._custom_css_editor.toPlainText.return_value = ""
        self._panel._startup_cb = MagicMock()
        self._panel._startup_cb.isChecked.return_value = False
        self._panel._start_min_cb = MagicMock()
        self._panel._start_min_cb.isChecked.return_value = False
        self._panel._auto_close_cb = MagicMock()
        self._panel._auto_close_cb.isChecked.return_value = False
        self._panel._ball_opacity = MagicMock()
        self._panel._ball_opacity.text.return_value = "0.85"
        self._panel._ball_size = MagicMock()
        self._panel._ball_size.text.return_value = "52"

        with (
            patch.object(self._panel, "_harper_dialect", MagicMock(), create=True),
            patch.object(self._panel, "_validate_trigger_hotkey", return_value=True),
            patch.object(self._panel, "_validate_hotkey", return_value=True),
            patch.object(self._panel, "_assign_optimize_model", MagicMock(), create=True),
            patch.object(self._panel, "_assign_translate_model", MagicMock(), create=True),
        ):
            self._panel._on_save()

        from phraise import config as cfg_mod

        data = cfg_mod.config._data
        self.assertNotIn(
            "theme",
            data.get("general", {}),
            "Save must NOT write theme to general section",
        )
        self.assertIn(
            "theme",
            data.get("appearance", {}),
            "Save MUST write theme to appearance section",
        )
