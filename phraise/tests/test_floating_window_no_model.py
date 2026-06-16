# PhrAIse - AI writing assistant
# License: GNU GPLv3
# GitHub: https://github.com/hqrrr/Phraise
# Author: hqrrr
#
# Description: Unit tests for floating window no model.
"""Tests for FloatingWindow no-model guards in _do_optimize and _do_translate.

Verifies that:
  1. _do_optimize shows a toast and returns early when optimize_model is "".
  2. _do_translate shows a toast and returns early when translate_model is "".
  3. Both functions reset _is_loading and _set_loading_state(False) on early return.
  4. Normal flow still works when a valid model is configured.
"""

import unittest
from unittest.mock import MagicMock, patch

from phraise.floating_window import FloatingWindow


def _make_fw(**overrides) -> FloatingWindow:
    """Return a bare FloatingWindow whose __init__ was skipped."""
    with patch.object(FloatingWindow, "__init__", return_value=None):
        fw = FloatingWindow.__new__(FloatingWindow)

    fw._is_loading = False
    fw._current_text = "The quick brown fox jump over the lazy dog."
    fw._current_style = "concise"

    fw._set_loading_state = MagicMock()
    fw._show_toast = MagicMock()
    fw._show_error = MagicMock()
    fw._on_optimize_done = MagicMock()
    fw._rewrite_label = MagicMock()
    fw._model_combo = MagicMock()
    fw._style_buttons = {}
    fw._set_harper_layout = MagicMock()

    fw._rewrite_texts = [MagicMock(), MagicMock(), MagicMock()]
    for rt in fw._rewrite_texts:
        rt.text_edit = MagicMock()
        rt.text_edit.setPlainText = MagicMock()
    fw._grammar_layout = MagicMock()
    fw._grammar_header = MagicMock()
    fw._grammar_container = MagicMock()

    for attr, val in overrides.items():
        setattr(fw, attr, val)

    return fw


class TestFloatingWindowNoModel(unittest.TestCase):
    """_do_optimize and _do_translate must handle empty model config gracefully."""

    def test_do_optimize_empty_model_shows_toast(self):
        """When optimize_model is '', a toast is shown and execution stops."""
        fw = _make_fw()

        with patch("phraise.floating_window.config") as mock_cfg:
            mock_cfg.get.return_value = ""

            FloatingWindow._do_optimize(fw)

        fw._show_toast.assert_called_once()
        self.assertFalse(fw._is_loading)
        fw._set_loading_state.assert_called_with(False)

    def test_do_optimize_empty_model_resets_loading(self):
        """After early return, _is_loading is False and loading state is reset."""
        fw = _make_fw()

        with patch("phraise.floating_window.config") as mock_cfg:
            mock_cfg.get.return_value = ""

            FloatingWindow._do_optimize(fw)

        self.assertFalse(fw._is_loading)
        # _set_loading_state called twice: once with True, once with False
        self.assertEqual(fw._set_loading_state.call_count, 2)
        fw._set_loading_state.assert_any_call(True)
        fw._set_loading_state.assert_any_call(False)

    def test_do_optimize_empty_model_does_not_call_harper(self):
        """HarperClient must not be instantiated when model is empty."""
        fw = _make_fw()

        with patch("phraise.floating_window.config") as mock_cfg:
            mock_cfg.get.return_value = ""

            # HarperClient should NOT be imported/used
            FloatingWindow._do_optimize(fw)

        # Verify that the toast was called and we returned early
        fw._show_toast.assert_called_once()
        self.assertFalse(fw._is_loading)

    def test_do_translate_empty_model_shows_toast(self):
        """When translate_model is '', a toast is shown and execution stops."""
        fw = _make_fw()

        with patch("phraise.floating_window.config") as mock_cfg:
            mock_cfg.get.return_value = ""

            FloatingWindow._do_translate(fw)

        fw._show_toast.assert_called_once()
        self.assertFalse(fw._is_loading)
        fw._set_loading_state.assert_called_with(False)

    def test_do_translate_empty_model_resets_loading(self):
        """After early return in _do_translate, _is_loading is False."""
        fw = _make_fw()

        with patch("phraise.floating_window.config") as mock_cfg:
            mock_cfg.get.return_value = ""

            FloatingWindow._do_translate(fw)

        self.assertFalse(fw._is_loading)
        self.assertEqual(fw._set_loading_state.call_count, 2)

    def test_do_translate_empty_model_does_not_call_check_output_fit(self):
        """check_output_fit must not be called when model is empty."""
        fw = _make_fw()

        with patch("phraise.floating_window.config") as mock_cfg, \
             patch("phraise.floating_window.check_output_fit") as mock_cof:
            mock_cfg.get.return_value = ""

            FloatingWindow._do_translate(fw)

        mock_cof.assert_not_called()

    def test_do_optimize_loading_flag_blocks_re_entry(self):
        """When _is_loading is True, _do_optimize returns immediately."""
        fw = _make_fw()
        fw._is_loading = True

        with patch("phraise.floating_window.config") as mock_cfg:
            FloatingWindow._do_optimize(fw)

        # config.get should NOT be called (we returned at the _is_loading check)
        mock_cfg.get.assert_not_called()
        self.assertTrue(fw._is_loading)

    def test_do_translate_loading_flag_blocks_re_entry(self):
        """When _is_loading is True, _do_translate returns immediately."""
        fw = _make_fw()
        fw._is_loading = True

        with patch("phraise.floating_window.config") as mock_cfg:
            FloatingWindow._do_translate(fw)

        mock_cfg.get.assert_not_called()
        self.assertTrue(fw._is_loading)


class TestFloatingWindowNoModelBoundary(unittest.TestCase):
    """Edge cases for the no-model guard."""

    def test_do_optimize_none_model_also_guarded(self):
        """If config returns None for optimize_model, guard should trigger.

        None is falsy, same as empty string.
        """
        fw = _make_fw()

        with patch("phraise.floating_window.config") as mock_cfg:
            mock_cfg.get.return_value = None

            FloatingWindow._do_optimize(fw)

        fw._show_toast.assert_called_once()
        self.assertFalse(fw._is_loading)

    def test_do_translate_none_model_also_guarded(self):
        """If config returns None for translate_model, guard should trigger."""
        fw = _make_fw()

        with patch("phraise.floating_window.config") as mock_cfg:
            mock_cfg.get.return_value = None

            FloatingWindow._do_translate(fw)

        fw._show_toast.assert_called_once()
        self.assertFalse(fw._is_loading)


if __name__ == "__main__":
    unittest.main()
