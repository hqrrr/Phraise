"""Tests for settings_panel _on_save numeric input validation.

Verifies that int() and float() casts in _on_save are wrapped in
try/except ValueError and show a field-specific warning instead of crashing.
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


def _build_mock_dialog(**kwargs) -> MagicMock:
    """Build a mocked SettingsPanel with all attributes _on_save needs.

    The returned object can be passed as ``self`` to
    ``SettingsPanel._on_save(mock)`` since Python duck-types on ``self``.
    """
    dialog = MagicMock(spec=SettingsPanel)

    # Model entries — both model_1 and model_2
    max_tokens_val = kwargs.get("max_tokens", "1024")
    dialog._model_entries = {}
    for key in ("model_1", "model_2"):
        dialog._model_entries[key] = {
            "provider_combo": _make_combo("openai", "OpenAI"),
            "api_base": _make_line_edit(""),
            "api_key": _make_line_edit("sk-xxx"),
            "model_combo": _make_combo("gpt-4", "GPT-4"),
            "temperature_slider": MagicMock(**{"value.return_value": 70}),
            "max_tokens": _make_line_edit(max_tokens_val),
            "extra_params": _make_line_edit(""),
        }

    # Assign-model combos (use "none" to skip harper/local paths)
    dialog._assign_optimize_model = _make_combo("none")
    dialog._assign_translate_model = _make_combo("none")

    # Styles (empty list so loop is a no-op)
    dialog._style_entries = []

    # Hotkeys
    dialog._hk_trigger = _make_line_edit("Ctrl+C,C")
    dialog._hk_toggle = _make_line_edit("Ctrl+Shift+B")
    dialog._validate_trigger_hotkey = MagicMock(return_value=True)
    dialog._validate_hotkey = MagicMock(return_value=True)

    # General / theme
    dialog._theme_combo = _make_combo("system")
    dialog._startup_cb = MagicMock(**{"isChecked.return_value": False})
    dialog._start_min_cb = MagicMock(**{"isChecked.return_value": False})
    dialog._auto_close_cb = MagicMock(**{"isChecked.return_value": True})

    # Appearance
    dialog._custom_css_editor = MagicMock(**{"toPlainText.return_value": ""})

    # Floating ball
    dialog._ball_opacity = _make_line_edit(kwargs.get("ball_opacity", "0.85"))
    dialog._ball_size = _make_line_edit(kwargs.get("ball_size", "52"))

    # __init__ conditionals: spec prevents auto-creation of _harper_dialect
    # so hasattr(self, '_harper_dialect') returns False  — correct for mock.

    return dialog


# ── tests ────────────────────────────────────────────────────────────────────


class TestOnSaveNumericValidation(unittest.TestCase):
    """Verify _on_save wraps int()/float() casts with try/except ValueError."""

    def setUp(self):
        self.config_patcher = patch("phraise.settings_panel.config")
        self.qmb_patcher = patch("phraise.settings_panel.QMessageBox")

        self.mock_config = self.config_patcher.start()
        self.mock_qmb = self.qmb_patcher.start()

        # Provide a mutable dict for config.data
        self.mock_config.data = {
            "models": {},
            "general": {},
            "trigger": {},
            "floating_ball": {},
        }

    def tearDown(self):
        self.qmb_patcher.stop()
        self.config_patcher.stop()

    # -- internal helper ---------------------------------------------------

    def _run_on_save(self, dialog: MagicMock) -> None:
        """Invoke SettingsPanel._on_save with *dialog* as ``self``."""
        SettingsPanel._on_save(dialog)

    # -- max_tokens --------------------------------------------------------

    def test_max_tokens_valid_int_passes(self):
        """max_tokens='2048' → no warning, save called."""
        dialog = _build_mock_dialog(max_tokens="2048")
        self._run_on_save(dialog)
        self.mock_qmb.warning.assert_not_called()
        self.mock_config.save.assert_called_once()

    def test_max_tokens_invalid_shows_warning(self):
        """max_tokens='abc' → warning shown, save NOT called."""
        dialog = _build_mock_dialog(max_tokens="abc")
        self._run_on_save(dialog)
        self.mock_qmb.warning.assert_called_once()
        self.mock_config.save.assert_not_called()

    def test_max_tokens_empty_falls_back(self):
        """max_tokens='' → falls back to '1024', no warning."""
        dialog = _build_mock_dialog(max_tokens="")
        self._run_on_save(dialog)
        self.mock_qmb.warning.assert_not_called()
        self.mock_config.save.assert_called_once()

    # -- ball_opacity ------------------------------------------------------

    def test_ball_opacity_valid_float_passes(self):
        """ball_opacity='0.5' → no warning, save called."""
        dialog = _build_mock_dialog(ball_opacity="0.5")
        self._run_on_save(dialog)
        self.mock_qmb.warning.assert_not_called()
        self.mock_config.save.assert_called_once()

    def test_ball_opacity_invalid_shows_warning(self):
        """ball_opacity='1.2.3' → warning shown, save NOT called."""
        dialog = _build_mock_dialog(ball_opacity="1.2.3")
        self._run_on_save(dialog)
        self.mock_qmb.warning.assert_called_once()
        self.mock_config.save.assert_not_called()

    def test_ball_opacity_empty_falls_back(self):
        """ball_opacity='' → falls back to '0.85', no warning."""
        dialog = _build_mock_dialog(ball_opacity="")
        self._run_on_save(dialog)
        self.mock_qmb.warning.assert_not_called()
        self.mock_config.save.assert_called_once()

    # -- ball_size ---------------------------------------------------------

    def test_ball_size_valid_int_passes(self):
        """ball_size='100' → no warning, save called."""
        dialog = _build_mock_dialog(ball_size="100")
        self._run_on_save(dialog)
        self.mock_qmb.warning.assert_not_called()
        self.mock_config.save.assert_called_once()

    def test_ball_size_invalid_shows_warning(self):
        """ball_size='abc' → warning shown, save NOT called."""
        dialog = _build_mock_dialog(ball_size="abc")
        self._run_on_save(dialog)
        self.mock_qmb.warning.assert_called_once()
        self.mock_config.save.assert_not_called()

    def test_ball_size_empty_falls_back(self):
        """ball_size='' → falls back to '52', no warning."""
        dialog = _build_mock_dialog(ball_size="")
        self._run_on_save(dialog)
        self.mock_qmb.warning.assert_not_called()
        self.mock_config.save.assert_called_once()


if __name__ == "__main__":
    unittest.main()
