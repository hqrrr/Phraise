# PhrAIse - AI writing assistant
# License: GNU GPLv3
# GitHub: https://github.com/hqrrr/Phraise
# Author: hqrrr
#
# Description: Unit tests for settings preserve.
"""Tests for SettingsPanel._on_save preserving existing API keys and styles.

The user reported that ``settings.json`` is overwritten without API key and
styles after saving settings.  ``_on_save`` replaces ``data["models"][model_key]``
with a new dict containing only the fields it explicitly sets, and only writes
``data["styles"]`` when the local styles list is non-empty.

These tests lock the preservation contract: if the dialog fields are populated
with the existing values, the resulting ``config.data`` must still contain them.
"""

import unittest
from unittest.mock import MagicMock, patch

from phraise.settings_panel import SettingsPanel


# ── helpers ──────────────────────────────────────────────────────────────────


def _make_line_edit(text: str = "") -> MagicMock:
    m = MagicMock()
    m.text.return_value = text
    return m


def _make_combo(current_data: str = "", current_text: str = "") -> MagicMock:
    m = MagicMock()
    m.currentData.return_value = current_data
    m.currentText.return_value = current_text or current_data
    return m


def _make_slider(value: int = 50) -> MagicMock:
    m = MagicMock()
    m.value.return_value = value
    return m


def _make_style_entry(id_val: str = "", label_val: str = "", keyword_val: str = "") -> dict:
    """Return a mocked style entry dict matching ``_build_style_tab`` structure."""
    return {
        "id": _make_line_edit(id_val),
        "label": _make_line_edit(label_val),
        "keyword": _make_line_edit(keyword_val),
    }


def _build_mock_dialog(
    optimize_model: str = "model_1",
    translate_model: str = "model_2",
    styles: list | None = None,
) -> MagicMock:
    """Build a mocked SettingsPanel with all attributes ``_on_save`` needs.

    The returned object can be passed as ``self`` to
    ``SettingsPanel._on_save(mock)`` since Python duck-types on ``self``.
    """
    dialog = MagicMock(spec=SettingsPanel)

    # Model entries — both slots with realistic values
    dialog._model_entries = {}
    for key, api_key, provider, api_base, model_name, max_tokens in [
        ("model_1", "sk-abc123", "openai", "https://api.openai.com/v1", "gpt-4o", "4096"),
        ("model_2", "sk-xyz789", "deepseek", "https://api.deepseek.com/v1", "deepseek-chat", "8192"),
    ]:
        dialog._model_entries[key] = {
            "provider_combo": _make_combo(provider, provider),
            "api_base": _make_line_edit(api_base),
            "api_key": _make_line_edit(api_key),
            "model_combo": _make_combo(model_name, model_name),
            "temperature_slider": _make_slider(30),
            "max_tokens": _make_line_edit(max_tokens),
            "extra_params": _make_line_edit(""),
        }

    # Assign-model combos
    dialog._assign_optimize_model = _make_combo(optimize_model)
    dialog._assign_translate_model = _make_combo(translate_model)

    # Style entries
    dialog._style_entries = styles if styles is not None else []

    # Hotkeys
    dialog._hk_trigger = _make_line_edit("Ctrl+C,C")
    dialog._hk_toggle = _make_line_edit("Ctrl+Shift+B")
    dialog._validate_trigger_hotkey = MagicMock(return_value=True)
    dialog._validate_hotkey = MagicMock(return_value=True)

    # General / theme
    dialog._theme_combo = _make_combo("dark")
    dialog._start_min_cb = MagicMock(**{"isChecked.return_value": False})
    dialog._auto_close_cb = MagicMock(**{"isChecked.return_value": False})

    # Appearance
    dialog._custom_css_editor = MagicMock(**{"toPlainText.return_value": ""})

    # Floating ball
    dialog._ball_opacity = _make_line_edit("0.85")
    dialog._ball_size = _make_line_edit("52")

    # ``hasattr(self, '_harper_dialect')`` — not set, so ``hasattr``
    # returns False (correct for non-Harper code paths).
    # spec=SettingsPanel prevents auto-creation of ``_harper_dialect``.

    return dialog


# ── tests ────────────────────────────────────────────────────────────────────


class TestSettingsPreserve(unittest.TestCase):
    """Verify ``_on_save`` does not drop existing API keys, styles, or config keys."""

    def setUp(self):
        self.config_patcher = patch("phraise.settings_panel.config")
        self.qmb_patcher = patch("phraise.settings_panel.QMessageBox")

        self.mock_config = self.config_patcher.start()
        self.mock_qmb = self.qmb_patcher.start()

        # Provide a mutable dict mimicking real persistent config data
        self.mock_config.data = {
            "models": {
                "model_1": {
                    "provider": "openai",
                    "api_base": "https://api.openai.com/v1",
                    "api_key": "sk-abc123",
                    "model_name": "gpt-4o",
                    "temperature": 0.3,
                    "max_tokens": 4096,
                    "extra_params": "",
                    "mode": "remote",
                },
                "model_2": {
                    "provider": "deepseek",
                    "api_base": "https://api.deepseek.com/v1",
                    "api_key": "sk-xyz789",
                    "model_name": "deepseek-chat",
                    "temperature": 0.5,
                    "max_tokens": 8192,
                    "extra_params": "",
                    "mode": "remote",
                },
            },
            "styles": [
                {"id": "concise", "label": "Concise", "prompt_keyword": "concise and brief"},
                {"id": "formal", "label": "Formal", "prompt_keyword": "formal and professional"},
                {"id": "custom1", "label": "My Style", "prompt_keyword": "custom instruction"},
            ],
            "general": {
                "language": "en",
                "optimize_model": "model_1",
                "translate_model": "model_2",
                "start_minimized": False,
                "replace_auto_close": False,
            },
            "trigger": {
                "hotkey_trigger": "ctrl+c+c",
                "hotkey_toggle_ball": "ctrl+shift+b",
            },
            "appearance": {
                "theme": "dark",
                "custom_css": "",
            },
            "harper": {
                "dialect": "American",
            },
            "floating_ball": {
                "opacity": 0.85,
                "size": 52,
            },
        }

    def tearDown(self):
        self.qmb_patcher.stop()
        self.config_patcher.stop()

    # -- internal helper -------------------------------------------------------

    def _run_on_save(self, dialog: MagicMock) -> None:
        """Invoke ``SettingsPanel._on_save`` with *dialog* as ``self``."""
        SettingsPanel._on_save(dialog)

    # -- api_key and styles preservation ---------------------------------------

    def test_save_preserves_api_key_and_styles(self):
        """Existing api_key and styles in config.data survive _on_save.

        Regression guard: ``_on_save`` must NOT overwrite model entries with
        a skeleton dict that drops the api_key, nor skip ``data["styles"]``
        when the styles widget list is populated.
        """
        dialog = _build_mock_dialog(
            styles=[
                _make_style_entry("concise", "Concise", "concise and brief"),
                _make_style_entry("formal", "Formal", "formal and professional"),
                _make_style_entry("custom1", "My Style", "custom instruction"),
            ]
        )
        self._run_on_save(dialog)

        data = self.mock_config.data

        # API keys preserved
        self.assertEqual(
            data["models"]["model_1"]["api_key"],
            "sk-abc123",
            "model_1 api_key must be preserved after save",
        )
        self.assertEqual(
            data["models"]["model_2"]["api_key"],
            "sk-xyz789",
            "model_2 api_key must be preserved after save",
        )

        # Styles preserved
        self.assertEqual(
            data["styles"],
            [
                {"id": "concise", "label": "Concise", "prompt_keyword": "concise and brief"},
                {"id": "formal", "label": "Formal", "prompt_keyword": "formal and professional"},
                {"id": "custom1", "label": "My Style", "prompt_keyword": "custom instruction"},
            ],
            "styles list must be preserved after save",
        )

        # general.optimize_model is set from the combo, not overwritten
        self.assertEqual(
            data["general"]["optimize_model"],
            "model_1",
            "optimize_model must be preserved after save",
        )

        # No validation warning and save() was actually called
        self.mock_qmb.warning.assert_not_called()
        self.mock_config.save.assert_called_once()

    # -- harper mode -----------------------------------------------------------

    def test_save_harper_sets_model_1_mode_local(self):
        """``_assign_optimize_model`` = ``"harper"`` ⇒ model_1.mode = ``"local"``.

        When the user selects Harper for the optimize slot, ``_on_save`` must
        set ``data["models"]["model_1"]["mode"]`` = ``"local"`` to switch the
        first model slot into local LSP mode.
        """
        dialog = _build_mock_dialog(optimize_model="harper")
        self._run_on_save(dialog)

        data = self.mock_config.data

        self.assertEqual(
            data["models"]["model_1"]["mode"],
            "local",
            "model_1.mode should be 'local' when optimize_model is 'harper'",
        )

        self.mock_qmb.warning.assert_not_called()
        self.mock_config.save.assert_called_once()


if __name__ == "__main__":
    unittest.main()
