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
from PySide6.QtGui import QIcon
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QLabel, QPushButton, QSizePolicy, QTextEdit

from phraise.floating_window import FloatingWindow, NoScrollComboBox, _HoverTextEdit
from phraise.harper_client import LintResult
from phraise.harper_types import HarperIssue
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

    def test_combined_tab_text_boxes_fill_width_no_horizontal_scrollbar(self):
        """Combined tab rewrite and translation text boxes expand to fill the viewport width."""
        fw = self._make_fw()
        fw.show()
        fw.resize(350, 500)
        fw._tabs.setCurrentIndex(2)
        fw._on_tab_changed(2)

        text = "Hello world " * 20
        for he in fw._combined_rewrite_texts:
            he.text_edit.setPlainText(text)
        fw._combined_translation_text.setPlainText(text)
        QApplication.processEvents()

        scroll = fw._combined_scroll
        self.assertFalse(scroll.horizontalScrollBar().isVisible())
        viewport_width = scroll.viewport().width()
        for he in fw._combined_rewrite_texts:
            self.assertEqual(he.text_edit.sizePolicy().horizontalPolicy(), QSizePolicy.Expanding)
            self.assertEqual(he.sizePolicy().horizontalPolicy(), QSizePolicy.Expanding)
            self.assertLessEqual(he.width(), viewport_width)
        self.assertEqual(
            fw._combined_translation_text.sizePolicy().horizontalPolicy(), QSizePolicy.Expanding
        )
        self.assertLessEqual(fw._combined_translation_text.width(), viewport_width)

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

    # ------------------------------------------------------------------
    # load_text dispatches optimize_translate mode
    # ------------------------------------------------------------------

    def test_load_text_switches_tab(self):
        """load_text with optimize_translate switches to tab 2 and calls combined dispatch."""
        fw = self._make_fw()
        with patch.object(fw, "_do_optimize_translate") as mock_combined:
            fw.load_text("hello", "optimize_translate")
        self.assertEqual(fw._tabs.currentIndex(), 2)
        self.assertEqual(fw._current_mode, "optimize_translate")
        mock_combined.assert_called_once()

    def test_model_combo_hidden(self):
        """Model combo must be hidden when switching to combined tab."""
        fw = self._make_fw()
        fw.show()
        fw._on_tab_changed(2)
        self.assertFalse(fw._model_combo.isVisible())

    def test_model_combo_reappears(self):
        """Model combo must reappear when switching back from combined tab."""
        fw = self._make_fw()
        fw.show()
        fw._on_tab_changed(2)
        self.assertFalse(fw._model_combo.isVisible())
        fw._on_tab_changed(0)
        self.assertTrue(fw._model_combo.isVisible())

    # ------------------------------------------------------------------
    # Language switch propagation
    # ------------------------------------------------------------------

    def test_language_switch(self):
        """_retranslate_ui must update combined tab labels to Chinese."""
        fw = self._make_fw()

        cn_translations = {
            "fw.tab.optimize_translate": "优化+翻译",
            "fw.label.optimize_section": "优化结果：",
            "fw.label.translate_section": "翻译结果：",
            "fw.label.style": "风格：",
            "fw.label.grammar_expanded": "语法检查 ▼",
            "fw.label.rewrites": "改写版本：",
            "fw.label.source_lang": "源语言：",
            "fw.label.target_lang": "目标语言：",
            "fw.label.translation_result": "翻译结果：",
            "fw.btn.replace_original": "替换原文",
            "fw.btn.copy": "复制",
        }

        def mock_t(key, **kwargs):
            return cn_translations.get(key, key)

        with patch("phraise.floating_window.t", side_effect=mock_t):
            fw._retranslate_ui()

        self.assertEqual(fw._tabs.tabText(2), "优化+翻译")
        self.assertEqual(fw._combined_optimize_label.text(), "优化结果：")
        self.assertEqual(fw._combined_translate_label.text(), "翻译结果：")
        self.assertEqual(fw._combined_style_label.text(), "风格：")
        self.assertEqual(fw._combined_rewrite_label.text(), "改写版本：")
        self.assertEqual(fw._combined_source_lang_label.text(), "源语言：")
        self.assertEqual(fw._combined_target_lang_label.text(), "目标语言：")
        self.assertEqual(fw._combined_translation_result_label.text(), "翻译结果：")
        self.assertEqual(fw._combined_trans_replace_btn.text(), "替换原文")
        self.assertEqual(fw._combined_trans_copy_btn.text(), "复制")

    # ------------------------------------------------------------------
    # Theme switch propagation
    # ------------------------------------------------------------------

    def test_theme_switch(self):
        """_apply_theme must apply non-empty stylesheets to combined tab widgets."""
        fw = self._make_fw()
        fw._apply_theme("catppuccin_mocha")

        self.assertNotEqual(fw._combined_scroll.styleSheet(), "")
        self.assertNotEqual(fw._combined_source_lang.styleSheet(), "")
        self.assertNotEqual(fw._combined_target_lang.styleSheet(), "")
        self.assertNotEqual(fw._combined_translation_text.styleSheet(), "")
        self.assertNotEqual(fw._combined_trans_replace_btn.styleSheet(), "")
        self.assertNotEqual(fw._combined_trans_copy_btn.styleSheet(), "")
        self.assertNotEqual(fw._combined_optimize_label.styleSheet(), "")
        self.assertNotEqual(fw._combined_translate_label.styleSheet(), "")


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

    # ------------------------------------------------------------------
    # _on_regenerate dispatches to correct method
    # ------------------------------------------------------------------

    def test_regenerate(self):
        """_on_regenerate dispatches based on _current_mode to the correct method."""
        fw = self._make_fw()

        with (
            patch.object(fw, "_do_optimize") as mock_opt,
            patch.object(fw, "_do_translate") as mock_trans,
            patch.object(fw, "_do_optimize_translate") as mock_combined,
        ):
            fw._current_mode = "optimize"
            fw._on_regenerate()
            mock_opt.assert_called_once()
            mock_trans.assert_not_called()
            mock_combined.assert_not_called()

        with (
            patch.object(fw, "_do_optimize") as mock_opt,
            patch.object(fw, "_do_translate") as mock_trans,
            patch.object(fw, "_do_optimize_translate") as mock_combined,
        ):
            fw._current_mode = "translate"
            fw._on_regenerate()
            mock_opt.assert_not_called()
            mock_trans.assert_called_once()
            mock_combined.assert_not_called()

        with (
            patch.object(fw, "_do_optimize") as mock_opt,
            patch.object(fw, "_do_translate") as mock_trans,
            patch.object(fw, "_do_optimize_translate") as mock_combined,
        ):
            fw._current_mode = "optimize_translate"
            fw._on_regenerate()
            mock_opt.assert_not_called()
            mock_trans.assert_not_called()
            mock_combined.assert_called_once()

    # ------------------------------------------------------------------
    # Loading indicators (F1)
    # ------------------------------------------------------------------

    def test_no_central_loading_overlay_during_combined_load(self):
        """Combined tab must not show central _loading_overlay during load."""
        fw = self._make_fw()
        self._set_text_and_style(fw)
        fw._loading_overlay.show = MagicMock()

        def mock_opt(original_text, style, style_label, model_type, on_done):
            on_done({"rewrites": [{"text": "A"}], "grammar_issues": []}, None)

        def mock_trans(original_text, source_lang, target_lang, model_type, on_done):
            on_done({"translation": "B"}, None)

        with (
            patch("phraise.floating_window.optimize_text", side_effect=mock_opt),
            patch("phraise.floating_window.translate_text", side_effect=mock_trans),
        ):
            fw._do_optimize_translate()

        fw._loading_overlay.show.assert_not_called()
        self.assertFalse(fw._is_loading)

    def test_regenerate_button_spinner_during_combined_load(self):
        """Combined tab must set spinner icon on _regenerate_btn during load and reset after."""
        fw = self._make_fw()
        self._set_text_and_style(fw)

        def mock_opt(original_text, style, style_label, model_type, on_done):
            on_done({"rewrites": [{"text": "A"}], "grammar_issues": []}, None)

        def mock_trans(original_text, source_lang, target_lang, model_type, on_done):
            on_done({"translation": "B"}, None)

        with (
            patch("phraise.floating_window.optimize_text", side_effect=mock_opt),
            patch("phraise.floating_window.translate_text", side_effect=mock_trans),
            patch("phraise.floating_window.qta.icon", return_value=QIcon()) as mock_icon,
        ):
            fw._do_optimize_translate()

        spinner_calls = [c for c in mock_icon.call_args_list if c.args == ("fa5s.spinner",)]
        redo_calls = [c for c in mock_icon.call_args_list if c.args == ("fa5s.redo",)]
        self.assertEqual(len(spinner_calls), 1)
        self.assertEqual(spinner_calls[0].kwargs["color"], fw._theme_colors["yellow"])
        self.assertEqual(len(redo_calls), 1)
        self.assertEqual(redo_calls[0].kwargs["color"], fw._theme_colors["text_muted"])

    # ------------------------------------------------------------------
    # Style change in combined mode (F2)
    # ------------------------------------------------------------------

    def test_on_style_change_combined_mode(self):
        """_on_style_change in combined mode updates style buttons and re-runs optimize only."""
        fw = self._make_fw()
        fw._current_text = "hello"
        fw._current_mode = "optimize_translate"
        fw._current_style = "formal"

        with (
            patch("phraise.floating_window.config.set") as mock_config_set,
            patch("phraise.floating_window.style_btn_style", return_value="styled") as mock_style,
            patch.object(fw, "_redo_optimize_for_combined") as mock_redo,
        ):
            fw._on_style_change("concise")

        self.assertEqual(fw._current_style, "concise")
        mock_config_set.assert_called_once_with("floating_window", "last_style", value="concise")
        mock_redo.assert_called_once()
        normal_calls = [c for c in mock_style.call_args_list if c.args[0] is fw._theme_colors]
        self.assertEqual(len(normal_calls), 2)
        self.assertTrue(all(c.args[1] is True for c in normal_calls))

    def test_redo_optimize_for_combined_only_runs_optimize(self):
        """_redo_optimize_for_combined runs optimize_text, preserves existing translation."""
        fw = self._make_fw()
        self._set_text_and_style(fw)
        fw._combined_translation_text.setPlainText("keep me")

        def mock_opt(original_text, style, style_label, model_type, on_done):
            on_done({"rewrites": [{"text": "rewritten"}], "grammar_issues": []}, None)

        def mock_trans(original_text, source_lang, target_lang, model_type, on_done):
            on_done({"translation": "should not appear"}, None)

        with (
            patch("phraise.floating_window.optimize_text", side_effect=mock_opt) as mock_optimize,
            patch("phraise.floating_window.translate_text", side_effect=mock_trans) as mock_translate,
            patch("phraise.floating_window.check_output_fit", return_value=(True, 100, 4096, "")),
        ):
            fw._redo_optimize_for_combined()

        mock_optimize.assert_called_once()
        mock_translate.assert_not_called()
        self.assertEqual(fw._combined_rewrite_texts[0].text_edit.toPlainText(), "rewritten")
        self.assertEqual(fw._combined_translation_text.toPlainText(), "keep me")
        self.assertFalse(fw._is_loading)
        self.assertTrue(fw._combined_optimize_loading.isHidden())

    def test_redo_optimize_for_combined_harper_only(self):
        """_redo_optimize_for_combined with Harper runs only Harper optimize, preserves translation."""
        fw = self._make_fw(optimize_model="harper", translate_model="model_2")
        self._set_text_and_style(fw)
        fw._combined_translation_text.setPlainText("keep me")

        def mock_check_text(text):
            return [], "corrected"

        def cfg_get(*keys, default=None):
            key = tuple(keys)
            if key == ("general", "optimize_model"):
                return "harper"
            if key == ("general", "translate_model"):
                return "model_2"
            if key == ("translation", "source_lang"):
                return "auto"
            if key == ("translation", "target_lang"):
                return "zh-CN"
            return _mock_config_get(*keys, default=default)

        with (
            patch("phraise.floating_window.config.get", side_effect=cfg_get),
            patch("phraise.harper_client.HarperClient") as MockClient,
            patch("phraise.floating_window.translate_text") as mock_translate,
            patch("phraise.floating_window.check_output_fit", return_value=(True, 100, 4096, "")),
        ):
            client = MockClient.return_value
            client.is_available.return_value = True
            client.check_text.side_effect = mock_check_text
            fw._redo_optimize_for_combined()

        mock_translate.assert_not_called()
        self.assertEqual(fw._combined_rewrite_texts[0].text_edit.toPlainText(), "corrected")
        self.assertTrue(fw._combined_rewrite_texts[1].isHidden())
        self.assertTrue(fw._combined_rewrite_texts[2].isHidden())
        self.assertEqual(fw._combined_translation_text.toPlainText(), "keep me")
        self.assertFalse(fw._is_loading)
        self.assertTrue(fw._combined_optimize_loading.isHidden())



class TestCombinedHarper(unittest.TestCase):
    """Verify Harper optimize + LLM translate parallel path in combined tab."""

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

    def _make_fw(self, optimize_model="harper", translate_model="model_2"):
        """Create FloatingWindow with optimize_model set to Harper by default."""
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
        fw._current_text = text
        fw._current_style = style

    def _config_get(self, optimize_model="harper", translate_model="model_2"):
        """Build a config.get side effect for combined Harper tests."""
        def fn(*keys, default=None):
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
        return fn

    def test_harper_success_and_translation_success(self):
        """Harper succeeds in parallel with translation → corrected text + grammar + translation."""
        fw = self._make_fw()
        self._set_text_and_style(fw)
        issue = HarperIssue(
            original="world", suggestion="earth", reason="test reason", severity="warning"
        )
        corrected = "Hello earth"

        def mock_check_text(text):
            return [issue], corrected

        def mock_translate(original_text, source_lang, target_lang, model_type, on_done):
            on_done({"translation": "你好世界"}, None)

        with (
            patch("phraise.floating_window.config.get", side_effect=self._config_get()),
            patch("phraise.floating_window.check_output_fit", return_value=(True, 100, 4096, "")),
            patch("phraise.harper_client.HarperClient") as MockClient,
            patch("phraise.floating_window.translate_text", side_effect=mock_translate),
            patch("phraise.floating_window.optimize_text") as mock_optimize,
            patch.object(fw, "_show_toast") as mock_toast,
        ):
            client = MockClient.return_value
            client.is_available.return_value = True
            client.check_text.side_effect = mock_check_text
            fw._do_optimize_translate()

        mock_optimize.assert_not_called()
        mock_toast.assert_not_called()
        self.assertEqual(fw._combined_rewrite_texts[0].text_edit.toPlainText(), corrected)
        self.assertTrue(fw._combined_rewrite_texts[1].isHidden())
        self.assertTrue(fw._combined_rewrite_texts[2].isHidden())
        self.assertEqual(fw._combined_translation_text.toPlainText(), "你好世界")
        self.assertTrue(fw._combined_optimize_loading.isHidden())
        self.assertTrue(fw._combined_translate_loading.isHidden())
        self.assertFalse(fw._is_loading)
        self.assertEqual(fw._combined_grammar_layout.count(), 1)

    def test_harper_unavailable_falls_back_to_llm_optimize(self):
        """Harper unavailable → toast + LLM optimize + LLM translate fallback."""
        fw = self._make_fw()
        self._set_text_and_style(fw)

        def mock_optimize(original_text, style, style_label, model_type, on_done):
            on_done({"rewrites": [{"text": "LLM optimized"}], "grammar_issues": []}, None)

        def mock_translate(original_text, source_lang, target_lang, model_type, on_done):
            on_done({"translation": "translated"}, None)

        with (
            patch("phraise.floating_window.config.get", side_effect=self._config_get()),
            patch("phraise.floating_window.check_output_fit", return_value=(True, 100, 4096, "")),
            patch("phraise.harper_client.HarperClient") as MockClient,
            patch("phraise.floating_window.translate_text", side_effect=mock_translate),
            patch("phraise.floating_window.optimize_text", side_effect=mock_optimize),
            patch.object(fw, "_show_toast") as mock_toast,
        ):
            client = MockClient.return_value
            client.is_available.return_value = False
            expected_toast = t("harper.error.binary_not_found")
            fw._do_optimize_translate()

        client.check_text.assert_not_called()
        mock_toast.assert_called_once_with(expected_toast)
        self.assertEqual(fw._combined_rewrite_texts[0].text_edit.toPlainText(), "LLM optimized")
        self.assertEqual(fw._combined_translation_text.toPlainText(), "translated")
        self.assertFalse(fw._is_loading)

    def test_harper_failure_falls_back_to_llm_optimize(self):
        """Harper raises an exception → toast + LLM optimize + LLM translate fallback."""
        fw = self._make_fw()
        self._set_text_and_style(fw)

        def mock_check_text(text):
            raise RuntimeError("harper crashed")

        def mock_optimize(original_text, style, style_label, model_type, on_done):
            on_done({"rewrites": [{"text": "Fallback optimized"}], "grammar_issues": []}, None)

        def mock_translate(original_text, source_lang, target_lang, model_type, on_done):
            on_done({"translation": "fallback translated"}, None)

        with (
            patch("phraise.floating_window.config.get", side_effect=self._config_get()),
            patch("phraise.floating_window.check_output_fit", return_value=(True, 100, 4096, "")),
            patch("phraise.harper_client.HarperClient") as MockClient,
            patch("phraise.floating_window.translate_text", side_effect=mock_translate),
            patch("phraise.floating_window.optimize_text", side_effect=mock_optimize),
            patch.object(fw, "_show_toast") as mock_toast,
        ):
            client = MockClient.return_value
            client.is_available.return_value = True
            client.check_text.side_effect = mock_check_text
            expected_toast = t("harper.error.process_crash")
            fw._do_optimize_translate()

        mock_toast.assert_called_once_with(expected_toast)
        self.assertEqual(fw._combined_rewrite_texts[0].text_edit.toPlainText(), "Fallback optimized")
        self.assertEqual(fw._combined_translation_text.toPlainText(), "fallback translated")
        self.assertFalse(fw._is_loading)




def _model_config_get(optimize_model="model_1", translate_model="model_2"):
    """Return a config.get side effect with configured optimize/translate models."""
    def fn(*keys, default=None):
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
    return fn


def _make_floating_window_with_models(optimize_model="model_1", translate_model="model_2"):
    """Create a FloatingWindow with mocked listeners and model config."""
    grabber = MagicMock()
    with (
        patch("phraise.floating_window.add_listener", return_value=None),
        patch("phraise.floating_window.config.update_section", return_value=None),
        patch("phraise.i18n.add_listener", return_value=None),
        patch("phraise.floating_window.config.get", side_effect=_model_config_get(optimize_model, translate_model)),
        patch("phraise.floating_window.check_output_fit", return_value=(True, 100, 4096, "")),
        patch("phraise.floating_window.run_on_main", side_effect=lambda fn: fn()),
    ):
        return FloatingWindow(grabber, on_close=MagicMock())


class TestCombinedIntegration(unittest.TestCase):
    """End-to-end combined tab flow through load_text() and regenerate."""

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

    def _make_fw(self) -> FloatingWindow:
        """Create a FloatingWindow with both models configured."""
        return _make_floating_window_with_models()

    def _success_opt_result(self):
        return {
            "rewrites": [
                {"text": "Version A"},
                {"text": "Version B"},
                {"text": "Version C"},
            ],
            "grammar_issues": [],
        }

    def _success_trans_result(self):
        return {"translation": "translated"}

    def test_full_flow_both_succeed(self):
        """load_text optimize_translate → both calls succeed → results + regenerate re-runs."""
        fw = self._make_fw()
        opt_result = self._success_opt_result()
        trans_result = self._success_trans_result()
        opt_calls = 0
        trans_calls = 0

        def mock_opt(original_text, style, style_label, model_type, on_done):
            nonlocal opt_calls
            opt_calls += 1
            on_done(opt_result, None)

        def mock_trans(original_text, source_lang, target_lang, model_type, on_done):
            nonlocal trans_calls
            trans_calls += 1
            on_done(trans_result, None)

        with (
            patch("phraise.floating_window.optimize_text", side_effect=mock_opt),
            patch("phraise.floating_window.translate_text", side_effect=mock_trans),
            patch("phraise.floating_window.check_output_fit", return_value=(True, 100, 4096, "")),
            patch("phraise.floating_window.config.get", side_effect=_model_config_get()),
        ):
            fw.load_text("source", "optimize_translate")

        self.assertEqual(fw._tabs.currentIndex(), 2)
        self.assertEqual(fw._current_mode, "optimize_translate")
        self.assertEqual(opt_calls, 1)
        self.assertEqual(trans_calls, 1)
        self.assertFalse(fw._is_loading)
        self.assertEqual(
            fw._combined_rewrite_texts[0].text_edit.toPlainText(), "Version A")
        self.assertEqual(
            fw._combined_rewrite_texts[1].text_edit.toPlainText(), "Version B")
        self.assertEqual(
            fw._combined_rewrite_texts[2].text_edit.toPlainText(), "Version C")
        self.assertEqual(
            fw._combined_translation_text.toPlainText(), "translated")

        with (
            patch("phraise.floating_window.optimize_text", side_effect=mock_opt),
            patch("phraise.floating_window.translate_text", side_effect=mock_trans),
            patch("phraise.floating_window.check_output_fit", return_value=(True, 100, 4096, "")),
            patch("phraise.floating_window.config.get", side_effect=_model_config_get()),
        ):
            fw._on_regenerate()

        self.assertEqual(opt_calls, 2)
        self.assertEqual(trans_calls, 2)
        self.assertFalse(fw._is_loading)

    def test_full_flow_partial_failure_then_regenerate(self):
        """First run optimize fails + translate succeeds; regenerate with both succeed."""
        fw = self._make_fw()
        opt_result = self._success_opt_result()
        trans_result = self._success_trans_result()
        opt_calls = 0
        trans_calls = 0

        def mock_opt(original_text, style, style_label, model_type, on_done):
            nonlocal opt_calls
            opt_calls += 1
            if opt_calls == 1:
                on_done(None, "Optimize API error")
            else:
                on_done(opt_result, None)

        def mock_trans(original_text, source_lang, target_lang, model_type, on_done):
            nonlocal trans_calls
            trans_calls += 1
            on_done(trans_result, None)

        with (
            patch("phraise.floating_window.optimize_text", side_effect=mock_opt),
            patch("phraise.floating_window.translate_text", side_effect=mock_trans),
            patch("phraise.floating_window.check_output_fit", return_value=(True, 100, 4096, "")),
            patch("phraise.floating_window.config.get", side_effect=_model_config_get()),
        ):
            fw.load_text("source", "optimize_translate")

        self.assertEqual(fw._tabs.currentIndex(), 2)
        self.assertEqual(opt_calls, 1)
        self.assertEqual(trans_calls, 1)
        self.assertFalse(fw._is_loading)
        self.assertEqual(
            fw._combined_rewrite_texts[0].text_edit.toPlainText(), "Optimize API error")
        self.assertEqual(
            fw._combined_translation_text.toPlainText(), "translated")

        with (
            patch("phraise.floating_window.optimize_text", side_effect=mock_opt),
            patch("phraise.floating_window.translate_text", side_effect=mock_trans),
            patch("phraise.floating_window.check_output_fit", return_value=(True, 100, 4096, "")),
            patch("phraise.floating_window.config.get", side_effect=_model_config_get()),
        ):
            fw._on_regenerate()

        self.assertEqual(opt_calls, 2)
        self.assertEqual(trans_calls, 2)
        self.assertFalse(fw._is_loading)
        self.assertEqual(
            fw._combined_rewrite_texts[0].text_edit.toPlainText(), "Version A")
        self.assertEqual(
            fw._combined_rewrite_texts[1].text_edit.toPlainText(), "Version B")
        self.assertEqual(
            fw._combined_rewrite_texts[2].text_edit.toPlainText(), "Version C")
        self.assertEqual(
            fw._combined_translation_text.toPlainText(), "translated")


class TestCombinedRegression(unittest.TestCase):
    """Regression tests guarding existing Optimize, Translate, Harper, and theme behavior."""

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

    def _make_fw(self, optimize_model="model_1", translate_model="model_2") -> FloatingWindow:
        """Create a FloatingWindow with configurable model assignments."""
        return _make_floating_window_with_models(optimize_model, translate_model)

    def test_optimize_tab_regression(self):
        """Switch to optimize tab and verify three rewrites are displayed."""
        fw = self._make_fw()
        opt_result = {
            "rewrites": [
                {"text": "Rewrite 1"},
                {"text": "Rewrite 2"},
                {"text": "Rewrite 3"},
            ],
            "grammar_issues": [],
        }

        def mock_opt(original_text, style, style_label, model_type, on_done):
            on_done(opt_result, None)

        with (
            patch("phraise.floating_window.optimize_text", side_effect=mock_opt),
            patch("phraise.floating_window.check_output_fit", return_value=(True, 100, 4096, "")),
            patch("phraise.floating_window.config.get", side_effect=_model_config_get()),
        ):
            fw.load_text("Hello world", "optimize")

        self.assertEqual(fw._tabs.currentIndex(), 0)
        self.assertEqual(fw._current_mode, "optimize")
        self.assertEqual(fw._rewrite_texts[0].text_edit.toPlainText(), "Rewrite 1")
        self.assertEqual(fw._rewrite_texts[1].text_edit.toPlainText(), "Rewrite 2")
        self.assertEqual(fw._rewrite_texts[2].text_edit.toPlainText(), "Rewrite 3")

    def test_translate_tab_regression(self):
        """Switch to translate tab and verify translation is displayed."""
        fw = self._make_fw()

        def mock_trans(original_text, source_lang, target_lang, model_type, on_done):
            on_done({"translation": "Hola mundo"}, None)

        with (
            patch("phraise.floating_window.translate_text", side_effect=mock_trans),
            patch("phraise.floating_window.check_output_fit", return_value=(True, 100, 4096, "")),
            patch("phraise.floating_window.config.get", side_effect=_model_config_get()),
        ):
            fw.load_text("Hello world", "translate")

        self.assertEqual(fw._tabs.currentIndex(), 1)
        self.assertEqual(fw._current_mode, "translate")
        self.assertEqual(fw._translation_text.toPlainText(), "Hola mundo")

    def test_harper_optimize_tab_regression(self):
        """Optimize tab with optimize_model='harper' shows corrected text + grammar issues."""
        fw = self._make_fw(optimize_model="harper", translate_model="model_2")
        issue = HarperIssue(
            original="world", suggestion="earth", reason="test reason", severity="warning"
        )
        corrected = "Hello earth"

        def mock_check_text(text):
            return [issue], corrected

        with (
            patch("phraise.harper_client.HarperClient") as MockClient,
            patch("phraise.floating_window.config.get", side_effect=_model_config_get("harper", "model_2")),
        ):
            client = MockClient.return_value
            client.is_available.return_value = True
            client.check_text.side_effect = mock_check_text
            fw.load_text("Hello world", "optimize")

        self.assertEqual(fw._tabs.currentIndex(), 0)
        self.assertEqual(fw._current_mode, "optimize")
        self.assertEqual(fw._rewrite_texts[0].text_edit.toPlainText(), corrected)
        self.assertEqual(fw._grammar_layout.count(), 1)

    def test_theme_regression_existing_and_combined_widgets(self):
        """Switching theme updates stylesheets on existing and combined tab widgets."""
        fw = self._make_fw()
        fw._apply_theme("catppuccin_mocha")

        self.assertNotEqual(fw._optimize_scroll.styleSheet(), "")
        self.assertNotEqual(fw._rewrite_texts[0].text_edit.styleSheet(), "")
        self.assertNotEqual(fw._custom_entry.styleSheet(), "")
        self.assertNotEqual(fw._custom_btn.styleSheet(), "")
        self.assertNotEqual(fw._style_buttons["concise"].styleSheet(), "")

        self.assertNotEqual(fw._translate_scroll.styleSheet(), "")
        self.assertNotEqual(fw._source_lang.styleSheet(), "")
        self.assertNotEqual(fw._target_lang.styleSheet(), "")
        self.assertNotEqual(fw._translation_text.styleSheet(), "")
        self.assertNotEqual(fw._trans_replace_btn.styleSheet(), "")
        self.assertNotEqual(fw._trans_copy_btn.styleSheet(), "")

        self.assertNotEqual(fw._combined_scroll.styleSheet(), "")
        self.assertNotEqual(fw._combined_rewrite_texts[0].text_edit.styleSheet(), "")
        self.assertNotEqual(fw._combined_style_buttons["concise"].styleSheet(), "")
        self.assertNotEqual(fw._combined_source_lang.styleSheet(), "")
        self.assertNotEqual(fw._combined_target_lang.styleSheet(), "")
        self.assertNotEqual(fw._combined_translation_text.styleSheet(), "")
        self.assertNotEqual(fw._combined_trans_replace_btn.styleSheet(), "")
        self.assertNotEqual(fw._combined_trans_copy_btn.styleSheet(), "")


if __name__ == "__main__":
    unittest.main()
