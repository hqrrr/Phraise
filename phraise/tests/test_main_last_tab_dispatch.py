# PhrAIse - AI writing assistant
# License: GNU GPLv3
# GitHub: https://github.com/hqrrr/Phraise
# Author: hqrrr
#
# Description: Unit tests for _on_trigger_dispatch last_tab persistence.
"""Tests that _on_trigger_dispatch reads last_tab from config when window is closed.

Task 1: When the floating window is closed and the user presses the hotkey,
the code must read ``config.get("floating_window", "last_tab", default="optimize")``
instead of hardcoding ``mode = "optimize"``.

Verifies:
1. ``last_tab = "translate"`` and window closed → ``_expand_window(text, "translate")``.
2. ``last_tab = "optimize_translate"`` and window closed → ``_expand_window(text, "optimize_translate")``.
3. ``last_tab`` missing in config → defaults to ``"optimize"``.
"""

import unittest
from unittest.mock import MagicMock, patch


class TestLastTabDispatch(unittest.TestCase):
    """_on_trigger_dispatch must read last_tab from config when window is hidden."""

    def setUp(self):
        # Patch QApplication.instance so PhrAIseApp can be instantiated
        self.qapp_mock = MagicMock()
        qapp_patcher = patch(
            "phraise.main.QApplication.instance", return_value=self.qapp_mock
        )
        self.addCleanup(qapp_patcher.stop)
        qapp_patcher.start()

        # Silence write_error
        self.we_patcher = patch("phraise.main.write_error")
        self.addCleanup(self.we_patcher.stop)
        self.we_patcher.start()

        from phraise.main import PhrAIseApp

        self.app = PhrAIseApp()

        # Mock _grabber so capture_foreground() is a no-op
        self.app._grabber = MagicMock()

        # Mock _expand_window so we can verify calls without Qt
        self.app._expand_window = MagicMock()

        # Window is closed (not visible) — the bug scenario
        self.app._window = MagicMock()
        self.app._window.isVisible.return_value = False

    def test_last_tab_translate(self):
        """Window closed, last_tab='translate' -> _expand_window(text, 'translate')."""
        with patch("phraise.main.config") as mock_config:
            mock_config.get.return_value = "translate"
            self.app._on_trigger_dispatch("selected text")
            self.app._expand_window.assert_called_with("selected text", "translate")

    def test_last_tab_optimize_translate(self):
        """Window closed, last_tab='optimize_translate' -> _expand_window(text, 'optimize_translate')."""
        with patch("phraise.main.config") as mock_config:
            mock_config.get.return_value = "optimize_translate"
            self.app._on_trigger_dispatch("selected text")
            self.app._expand_window.assert_called_with(
                "selected text", "optimize_translate"
            )

    def test_last_tab_default(self):
        """last_tab missing in config -> _expand_window(text, 'optimize')."""
        with patch("phraise.main.config") as mock_config:
            # Simulate real config.get: returns the 'default' kwarg when key not found
            mock_config.get.side_effect = lambda *args, **kw: kw.get("default", None)
            self.app._on_trigger_dispatch("selected text")
            self.app._expand_window.assert_called_with("selected text", "optimize")

    def test_window_visible_still_uses_current_mode(self):
        """When window IS visible, current_mode is used regardless of last_tab."""
        self.app._window.isVisible.return_value = True
        self.app._window.current_mode = "translate"
        with patch("phraise.main.config") as mock_config:
            mock_config.get.return_value = "optimize"  # would win if bug persisted
            self.app._on_trigger_dispatch("selected text")
            # Must use window.current_mode, NOT config.get
            self.app._expand_window.assert_called_with("selected text", "translate")
