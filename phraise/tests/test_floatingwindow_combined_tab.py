# PhrAIse - AI writing assistant
# License: GNU GPLv3
# GitHub: https://github.com/hqrrr/Phraise
# Author: hqrrr
#
# Description: Unit tests for FloatingWindow MODE_INDEX constant and third tab infrastructure.
"""Tests for MODE_INDEX constant and combined tab (index 2) preparation.

Verifies:
- ``MODE_INDEX`` class constant exists with correct mapping
- ``load_text()`` uses ``MODE_INDEX[mode]`` instead of hardcoded indices
- ``_on_tab_changed()`` maps any index via reverse lookup (including index 2)
- ``_on_regenerate()`` has a branch for ``"optimize_translate"``
"""

import unittest
from unittest.mock import MagicMock, patch

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QLabel, QPushButton, QTextEdit

from phraise.floating_window import FloatingWindow, NoScrollComboBox, _HoverTextEdit
from phraise.i18n import t


def _inspect_signal_source():
    """Inspect _build_optimize_translate_tab source for expected clicked.connect calls."""
    import inspect
    source = inspect.getsource(FloatingWindow._build_optimize_translate_tab)
    return source


def _qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


# ---------------------------------------------------------------------------
# Mocked config.get  --  same defaults as test_floatingwindow_init.py
# ---------------------------------------------------------------------------

_CONFIG_DEFAULTS = {
    ("floating_window", "opacity"): 0.95,
    ("floating_window", "width"): 400,
    ("floating_window", "height"): 500,
    ("floating_window", "position_x"): 1400,
    ("floating_window", "position_y"): 600,
    ("floating_window", "last_style"): "concise",
    ("floating_window", "bg"): "#1e1e2e",
    ("floating_window", "bg_darker"): "#181825",
    ("floating_window", "border"): "#313244",
    ("floating_window", "surface"): "#313244",
    ("floating_window", "text"): "#cdd6f4",
    ("floating_window", "text_muted"): "#6c7086",
    ("floating_window", "primary"): "#89b4fa",
    ("floating_window", "yellow"): "#f9e2af",
    ("floating_window", "red"): "#f38ba8",
    ("floating_window", "green"): "#a6e3a1",
    ("styles",): [{"id": "concise", "label": "Concise"}],
}


def _mock_config_get(*keys, default=None):
    """Return sensible defaults for config keys used during FloatingWindow init."""
    key = tuple(keys)
    if key in _CONFIG_DEFAULTS:
        return _CONFIG_DEFAULTS[key]
    if default is not None:
        return default
    return "concise"


class TestModeIndex(unittest.TestCase):
    """Verify MODE_INDEX constant and its usage throughout FloatingWindow."""

    @classmethod
    def setUpClass(cls) -> None:
        cls._app = _qapp()

    def setUp(self) -> None:
        for attr in ("_rewrite_texts", "_translation_text"):
            try:
                delattr(FloatingWindow, attr)
            except AttributeError:
                pass

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _make_fw(self) -> FloatingWindow:
        """Create a minimal FloatingWindow with mocked dependencies."""
        grabber = MagicMock()
        with (
            patch("phraise.floating_window.add_listener", return_value=None),
            patch("phraise.floating_window.config.update_section", return_value=None),
            patch("phraise.i18n.add_listener", return_value=None),
            patch("phraise.floating_window.config.get", side_effect=_mock_config_get),
        ):
            fw = FloatingWindow(grabber, on_close=MagicMock())
        return fw

    # ------------------------------------------------------------------
    # MODE_INDEX constant
    # ------------------------------------------------------------------

    def test_mode_index_exists(self):
        """MODE_INDEX must be a class-level dict on FloatingWindow."""
        self.assertTrue(hasattr(FloatingWindow, "MODE_INDEX"))
        self.assertIsInstance(FloatingWindow.MODE_INDEX, dict)

    def test_mode_index_keys(self):
        """MODE_INDEX must contain optimize, translate, and optimize_translate."""
        expected_keys = {"optimize", "translate", "optimize_translate"}
        self.assertEqual(set(FloatingWindow.MODE_INDEX.keys()), expected_keys)

    def test_mode_index_values(self):
        """MODE_INDEX must map optimize→0, translate→1, optimize_translate→2."""
        self.assertEqual(FloatingWindow.MODE_INDEX["optimize"], 0)
        self.assertEqual(FloatingWindow.MODE_INDEX["translate"], 1)
        self.assertEqual(FloatingWindow.MODE_INDEX["optimize_translate"], 2)

    # ------------------------------------------------------------------
    # load_text uses MODE_INDEX
    # ------------------------------------------------------------------

    def test_load_text_uses_mode_index(self):
        """load_text must call setCurrentIndex with MODE_INDEX[mode]."""
        fw = self._make_fw()
        fw._tabs = MagicMock()
        fw._do_optimize = MagicMock()
        fw._do_translate = MagicMock()

        fw.load_text("hello", mode="optimize")
        fw._tabs.setCurrentIndex.assert_called_once_with(0)

        fw._tabs.setCurrentIndex.reset_mock()
        fw.load_text("hola", mode="translate")
        fw._tabs.setCurrentIndex.assert_called_once_with(1)

    def test_load_text_does_not_call_hardcoded_zero_one(self):
        """load_text should not have bare 0/1 literals for tab switching."""
        import inspect
        source = inspect.getsource(FloatingWindow.load_text)
        # It's OK to have MODE_INDEX references; forbid bare setCurrentIndex(0) or setCurrentIndex(1)
        self.assertNotIn("setCurrentIndex(0)", source,
                         "load_text should use MODE_INDEX[mode], not hardcoded 0")
        self.assertNotIn("setCurrentIndex(1)", source,
                         "load_text should use MODE_INDEX[mode], not hardcoded 1")

    # ------------------------------------------------------------------
    # _on_tab_changed uses reverse lookup
    # ------------------------------------------------------------------

    def test_on_tab_changed_index_0_sets_optimize(self):
        """_on_tab_changed(0) must set _current_mode to 'optimize'."""
        fw = self._make_fw()
        fw._refresh_model_combo = MagicMock()
        fw._on_tab_changed(0)
        self.assertEqual(fw._current_mode, "optimize")

    def test_on_tab_changed_index_1_sets_translate(self):
        """_on_tab_changed(1) must set _current_mode to 'translate'."""
        fw = self._make_fw()
        fw._refresh_model_combo = MagicMock()
        fw._on_tab_changed(1)
        self.assertEqual(fw._current_mode, "translate")

    def test_on_tab_changed_index_2_sets_optimize_translate(self):
        """_on_tab_changed(2) must set _current_mode to 'optimize_translate'."""
        fw = self._make_fw()
        fw._refresh_model_combo = MagicMock()
        fw._on_tab_changed(2)
        self.assertEqual(fw._current_mode, "optimize_translate")

    def test_on_tab_changed_no_hardcoded_compare(self):
        """_on_tab_changed must not contain 'idx == 0' or 'idx == 1' literals."""
        import inspect
        source = inspect.getsource(FloatingWindow._on_tab_changed)
        self.assertNotIn("idx == 0", source,
                         "_on_tab_changed should use reverse lookup, not hardcoded compare")
        self.assertNotIn("idx == 1", source,
                         "_on_tab_changed should use reverse lookup, not hardcoded compare")

    # ------------------------------------------------------------------
    # _on_regenerate handles optimize_translate
    # ------------------------------------------------------------------

    def test_on_regenerate_has_optimize_translate_branch(self):
        """_on_regenerate must have a branch for 'optimize_translate' mode."""
        import inspect
        source = inspect.getsource(FloatingWindow._on_regenerate)
        self.assertIn("optimize_translate", source,
                      "_on_regenerate must reference optimize_translate mode")
        self.assertIn("_do_optimize_translate", source,
                      "_on_regenerate must call _do_optimize_translate()")


class TestCombinedTabUI(unittest.TestCase):
    """Verify the third Optimize + Translate tab contains the required widgets."""

    @classmethod
    def setUpClass(cls) -> None:
        cls._app = _qapp()

    def setUp(self) -> None:
        for attr in ("_rewrite_texts", "_translation_text"):
            try:
                delattr(FloatingWindow, attr)
            except AttributeError:
                pass

    def _make_fw(self) -> FloatingWindow:
        """Create a minimal FloatingWindow with mocked dependencies."""
        grabber = MagicMock()
        with (
            patch("phraise.floating_window.add_listener", return_value=None),
            patch("phraise.floating_window.config.update_section", return_value=None),
            patch("phraise.i18n.add_listener", return_value=None),
            patch("phraise.floating_window.config.get", side_effect=_mock_config_get),
        ):
            fw = FloatingWindow(grabber, on_close=MagicMock())
        return fw

    def test_combined_tab_exists_at_index_two(self):
        """Third tab at index 2 must exist with the optimize_translate label."""
        fw = self._make_fw()
        self.assertEqual(fw._tabs.count(), 3)
        with patch("phraise.floating_window.config.get", side_effect=_mock_config_get):
            self.assertEqual(fw._tabs.tabText(2), t("fw.tab.optimize_translate"))

    def test_combined_tab_has_three_rewrite_boxes(self):
        """Combined tab must expose three _HoverTextEdit rewrite boxes."""
        fw = self._make_fw()
        self.assertTrue(hasattr(fw, "_combined_rewrite_texts"))
        self.assertEqual(len(fw._combined_rewrite_texts), 3)
        for he in fw._combined_rewrite_texts:
            self.assertIsInstance(he, _HoverTextEdit)

    def test_combined_tab_has_language_combos(self):
        """Combined tab must have source and target language NoScrollComboBox widgets."""
        fw = self._make_fw()
        self.assertIsInstance(fw._combined_source_lang, NoScrollComboBox)
        self.assertIsInstance(fw._combined_target_lang, NoScrollComboBox)

    def test_combined_tab_has_translation_text(self):
        """Combined tab must have a read-only translation result QTextEdit."""
        fw = self._make_fw()
        self.assertIsInstance(fw._combined_translation_text, QTextEdit)
        self.assertTrue(fw._combined_translation_text.isReadOnly())

    def test_combined_tab_has_replace_and_copy_buttons(self):
        """Combined tab must have Replace and Copy buttons for translation."""
        fw = self._make_fw()
        self.assertIsInstance(fw._combined_trans_replace_btn, QPushButton)
        self.assertIsInstance(fw._combined_trans_copy_btn, QPushButton)

    def test_combined_tab_has_no_custom_instruction_widget(self):
        """Combined tab must omit the custom instruction entry used in the optimize tab."""
        fw = self._make_fw()
        self.assertFalse(hasattr(fw, "_combined_custom_entry"))
        self.assertFalse(hasattr(fw, "_combined_custom_btn"))

    def test_combined_tab_loading_indicators_exist_and_hidden(self):
        """Combined tab must have per-section loading indicators, hidden by default."""
        fw = self._make_fw()
        self.assertIsInstance(fw._combined_optimize_loading, QLabel)
        self.assertIsInstance(fw._combined_translate_loading, QLabel)
        self.assertTrue(fw._combined_optimize_loading.isHidden())
        self.assertTrue(fw._combined_translate_loading.isHidden())

    def test_combined_tab_has_grammar_section(self):
        """Combined tab must have a grammar issues collapsible section header."""
        fw = self._make_fw()
        self.assertIsInstance(fw._combined_grammar_header, QLabel)
        self.assertTrue(hasattr(fw, "_combined_grammar_container"))

    def test_combined_tab_style_buttons_connected(self):
        """Each combined tab style button must route clicks to _on_style_change."""
        fw = self._make_fw()
        self.assertTrue(fw._combined_style_buttons)
        source = _inspect_signal_source()
        self.assertIn("btn.clicked.connect(lambda checked, sid=sid: self._on_style_change(sid))", source)
        btn = next(iter(fw._combined_style_buttons.values()))
        QTest.mouseClick(btn, Qt.MouseButton.LeftButton)

    def test_combined_tab_replace_button_connected(self):
        """Combined tab Replace button must call _do_replace with combined translation text."""
        fw = self._make_fw()
        source = _inspect_signal_source()
        self.assertIn("_combined_translation_text.toPlainText()", source)
        self.assertIn("self._do_replace", source)
        QTest.mouseClick(fw._combined_trans_replace_btn, Qt.MouseButton.LeftButton)

    def test_combined_tab_copy_button_connected(self):
        """Combined tab Copy button must call _on_copy_text with combined translation text."""
        fw = self._make_fw()
        source = _inspect_signal_source()
        self.assertIn("self._on_copy_text(self._combined_translation_text)", source)
        QTest.mouseClick(fw._combined_trans_copy_btn, Qt.MouseButton.LeftButton)


class TestCombinedParallel(unittest.TestCase):
    """Verify parallel optimize + translate execution in the combined tab."""

    @classmethod
    def setUpClass(cls) -> None:
        cls._app = _qapp()

    def setUp(self) -> None:
        for attr in ("_rewrite_texts", "_translation_text", "_combined_rewrite_texts",
                      "_combined_translation_text"):
            try:
                delattr(FloatingWindow, attr)
            except AttributeError:
                pass

    def _make_fw(self, optimize_model="model_1", translate_model="model_2"):
        """Create FloatingWindow with mocked config and LLM calls."""
        def custom_config_get(*keys, default=None):
            key = tuple(keys)
            if key == ("general", "optimize_model"):
                return optimize_model
            if key == ("general", "translate_model"):
                return translate_model
            if key == ("translation", "source_lang"):
                return "auto"
            if key == ("translation", "target_lang"):
                return "zh-CN"
            return _mock_config_get(*keys, default=default)

        grabber = MagicMock()
        with (
            patch("phraise.floating_window.add_listener", return_value=None),
            patch("phraise.floating_window.config.update_section", return_value=None),
            patch("phraise.i18n.add_listener", return_value=None),
            patch("phraise.floating_window.config.get", side_effect=custom_config_get),
            patch("phraise.floating_window.check_output_fit", return_value=(True, 100, 4096, "")),
            patch("phraise.floating_window.run_on_main", side_effect=lambda fn: fn()),
        ):
            fw = FloatingWindow(grabber, on_close=MagicMock())
        return fw

    def _set_text_and_style(self, fw, text="Hello world", style="concise"):
        """Helper to set text and style for combined execution."""
        fw._current_text = text
        fw._current_style = style

    # ------------------------------------------------------------------
    # Both succeed
    # ------------------------------------------------------------------

    def test_both_succeed(self):
        """Both optimize and translate succeed → results in both sections."""
        fw = self._make_fw()
        self._set_text_and_style(fw)

        opt_result = {
            "rewrites": [
                {"text": "Version A - concise"},
                {"text": "Version B"},
                {"text": "Version C"},
            ],
            "grammar_issues": [],
        }
        trans_result = {"translation": "你好世界"}

        def mock_opt(original_text, style, style_label, model_type, on_done):
            on_done(opt_result, None)

        def mock_trans(original_text, source_lang, target_lang, model_type, on_done):
            on_done(trans_result, None)

        with (
            patch("phraise.floating_window.optimize_text", side_effect=mock_opt),
            patch("phraise.floating_window.translate_text", side_effect=mock_trans),
        ):
            fw._do_optimize_translate()

        self.assertFalse(fw._is_loading)
        self.assertEqual(
            fw._combined_rewrite_texts[0].text_edit.toPlainText(), "Version A - concise")
        self.assertEqual(
            fw._combined_rewrite_texts[1].text_edit.toPlainText(), "Version B")
        self.assertEqual(
            fw._combined_rewrite_texts[2].text_edit.toPlainText(), "Version C")
        self.assertEqual(
            fw._combined_translation_text.toPlainText(), "你好世界")
        self.assertTrue(fw._combined_optimize_loading.isHidden())
        self.assertTrue(fw._combined_translate_loading.isHidden())

    # ------------------------------------------------------------------
    # Optimize OK, translate fail
    # ------------------------------------------------------------------

    def test_optimize_ok_translate_fail(self):
        """Optimize succeeds, translate fails → partial result + error."""
        fw = self._make_fw()
        self._set_text_and_style(fw)

        opt_result = {
            "rewrites": [{"text": "Optimized text"}],
            "grammar_issues": [],
        }
        trans_error = "Translation API error"

        def mock_opt(original_text, style, style_label, model_type, on_done):
            on_done(opt_result, None)

        def mock_trans(original_text, source_lang, target_lang, model_type, on_done):
            on_done(None, trans_error)

        with (
            patch("phraise.floating_window.optimize_text", side_effect=mock_opt),
            patch("phraise.floating_window.translate_text", side_effect=mock_trans),
        ):
            fw._do_optimize_translate()

        self.assertFalse(fw._is_loading)
        self.assertEqual(
            fw._combined_rewrite_texts[0].text_edit.toPlainText(), "Optimized text")
        self.assertEqual(
            fw._combined_translation_text.toPlainText(), trans_error)
        self.assertTrue(fw._combined_optimize_loading.isHidden())
        self.assertTrue(fw._combined_translate_loading.isHidden())

    # ------------------------------------------------------------------
    # Optimize fail, translate OK
    # ------------------------------------------------------------------

    def test_optimize_fail_translate_ok(self):
        """Optimize fails, translate succeeds → error + partial result."""
        fw = self._make_fw()
        self._set_text_and_style(fw)

        opt_error = "Optimization API error"
        trans_result = {"translation": "Translated text"}

        def mock_opt(original_text, style, style_label, model_type, on_done):
            on_done(None, opt_error)

        def mock_trans(original_text, source_lang, target_lang, model_type, on_done):
            on_done(trans_result, None)

        with (
            patch("phraise.floating_window.optimize_text", side_effect=mock_opt),
            patch("phraise.floating_window.translate_text", side_effect=mock_trans),
        ):
            fw._do_optimize_translate()

        self.assertFalse(fw._is_loading)
        # Error shown in all three rewrite boxes (follows _show_error convention)
        self.assertEqual(
            fw._combined_rewrite_texts[0].text_edit.toPlainText(), opt_error)
        self.assertEqual(
            fw._combined_rewrite_texts[1].text_edit.toPlainText(), opt_error)
        self.assertEqual(
            fw._combined_rewrite_texts[2].text_edit.toPlainText(), opt_error)
        self.assertEqual(
            fw._combined_translation_text.toPlainText(), "Translated text")
        self.assertTrue(fw._combined_optimize_loading.isHidden())
        self.assertTrue(fw._combined_translate_loading.isHidden())

    # ------------------------------------------------------------------
    # Both fail
    # ------------------------------------------------------------------

    def test_both_fail(self):
        """Both optimize and translate fail → errors in both sections."""
        fw = self._make_fw()
        self._set_text_and_style(fw)

        opt_error = "Optimization failed"
        trans_error = "Translation failed"

        def mock_opt(original_text, style, style_label, model_type, on_done):
            on_done(None, opt_error)

        def mock_trans(original_text, source_lang, target_lang, model_type, on_done):
            on_done(None, trans_error)

        with (
            patch("phraise.floating_window.optimize_text", side_effect=mock_opt),
            patch("phraise.floating_window.translate_text", side_effect=mock_trans),
        ):
            fw._do_optimize_translate()

        self.assertFalse(fw._is_loading)
        self.assertEqual(
            fw._combined_rewrite_texts[0].text_edit.toPlainText(), opt_error)
        self.assertEqual(
            fw._combined_translation_text.toPlainText(), trans_error)
        self.assertTrue(fw._combined_optimize_loading.isHidden())
        self.assertTrue(fw._combined_translate_loading.isHidden())

    # ------------------------------------------------------------------
    # _is_loading guard
    # ------------------------------------------------------------------

    def test_is_loading_guard_prevents_concurrent_runs(self):
        """_is_loading True must prevent _do_optimize_translate from firing calls."""
        fw = self._make_fw()
        self._set_text_and_style(fw)
        fw._is_loading = True

        mock_opt = MagicMock()
        mock_trans = MagicMock()

        with (
            patch("phraise.floating_window.optimize_text", mock_opt),
            patch("phraise.floating_window.translate_text", mock_trans),
        ):
            fw._do_optimize_translate()

        mock_opt.assert_not_called()
        mock_trans.assert_not_called()


if __name__ == "__main__":
    unittest.main()
