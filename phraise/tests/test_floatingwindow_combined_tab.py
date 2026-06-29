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

from PySide6.QtWidgets import QApplication

from phraise.floating_window import FloatingWindow


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


if __name__ == "__main__":
    unittest.main()
