# PhrAIse - AI writing assistant
# License: GNU GPLv3
# GitHub: https://github.com/hqrrr/Phraise
# Author: hqrrr
#
# Description: Unit tests for toast lifecycle.
"""Tests for toast lifecycle — prevent double-delete crash (Task 12).

Verifies:
  - ``WA_DeleteOnClose`` is set on toast QLabel so Qt handles deletion
    when the parent window is destroyed.
  - Timer callback is guarded with ``shiboken6.isValid`` so that
    closing the window while a toast is active does not cause a crash.
"""

import time
import unittest
from unittest.mock import MagicMock, patch

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QLabel

from phraise.floating_window import FloatingWindow


# ---------------------------------------------------------------------------
# QApplication singleton for the test class
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Mocked config.get — returns sensible defaults for all keys
# ---------------------------------------------------------------------------

_CONFIG_DEFAULTS = {
    # FloatingWindow geometry
    ("floating_window", "opacity"): 0.95,
    ("floating_window", "width"): 400,
    ("floating_window", "height"): 500,
    ("floating_window", "position_x"): 1400,
    ("floating_window", "position_y"): 600,
    ("floating_window", "last_style"): "concise",
    # Theme colors (needed by _build_ui)
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
    # Styles
    ("styles",): [{"id": "concise", "label": "Concise"}],
}

def _mock_config_get(*keys, default=None):
    """Return sensible defaults for config keys used during FloatingWindow init."""
    key = tuple(keys)
    if key in _CONFIG_DEFAULTS:
        return _CONFIG_DEFAULTS[key]
    # For any unknown key, return based on the default
    if default is not None:
        return default
    # Fallback for keys without default
    return "concise"


class TestToastLifecycle(unittest.TestCase):
    """Verify toast creation, timer and destruction edge cases."""

    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance()
        if cls._app is None:
            cls._app = QApplication([])

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _make_fw(self) -> FloatingWindow:
        """Create a minimal ``FloatingWindow`` with mocked dependencies."""
        grabber = MagicMock()
        # suppress real config reads / i18n listeners during __init__
        with (
            patch("phraise.floating_window.add_listener", return_value=None),
            patch("phraise.floating_window.config.update_section", return_value=None),
            patch("phraise.i18n.add_listener", return_value=None),
            patch("phraise.floating_window.config.get", side_effect=_mock_config_get),
        ):
            fw = FloatingWindow(grabber, on_close=MagicMock())
        return fw

    @staticmethod
    def _pump_events(seconds: float):
        """Process Qt events for ``seconds``."""
        steps = max(1, int(seconds * 20))
        for _ in range(steps):
            QApplication.processEvents()
            time.sleep(seconds / steps)

    # ------------------------------------------------------------------
    # Tests
    # ------------------------------------------------------------------

    def test_toast_has_delete_on_close_attribute(self):
        """Toast QLabel carries ``Qt.WA_DeleteOnClose`` after creation."""
        fw = self._make_fw()
        try:
            fw.show()
            QApplication.processEvents()

            # Count QLabel children before toast
            labels_before = set(fw.findChildren(QLabel))
            fw._show_toast("WA_DeleteOnClose check")
            QApplication.processEvents()

            labels_after = set(fw.findChildren(QLabel))
            new_labels = labels_after - labels_before

            # At least one toast label should have been created
            self.assertGreater(len(new_labels), 0, "No toast QLabel was created")
            for label in new_labels:
                self.assertTrue(
                    label.testAttribute(Qt.WA_DeleteOnClose),
                    f"Toast QLabel {label.text()!r} missing WA_DeleteOnClose",
                )
        finally:
            fw.close()
            QApplication.processEvents()

    def test_toast_close_window_before_timer_no_crash(self):
        """Close window while toast is active — timer callback must not crash."""
        fw = self._make_fw()
        fw.show()
        QApplication.processEvents()

        fw._show_toast("will be interrupted")
        QApplication.processEvents()

        fw.close()
        QApplication.processEvents()

        self._pump_events(2.0)
        self.assertTrue(True)

    def test_toast_timer_fires_normally(self):
        """Timer fires on a still-alive window — toast closes without crash."""
        fw = self._make_fw()
        fw.show()
        QApplication.processEvents()

        fw._show_toast("normal toast")
        QApplication.processEvents()

        self._pump_events(2.0)
        self.assertTrue(True)

    def test_destroy_window_during_toast_no_crash(self):
        """Call destroy() while toast is active — no double-delete crash."""
        fw = self._make_fw()
        fw.show()
        QApplication.processEvents()

        fw._show_toast("destroy toast")
        QApplication.processEvents()

        fw.destroy()
        QApplication.processEvents()

        self._pump_events(2.0)
        self.assertTrue(True)

    def test_multiple_toasts_no_crash(self):
        """Rapid successive toast calls — no crash from overlapping timers."""
        fw = self._make_fw()
        fw.show()
        QApplication.processEvents()

        for i in range(5):
            fw._show_toast(f"toast {i}")
            QApplication.processEvents()
            time.sleep(0.05)

        self._pump_events(2.5)
        self.assertTrue(True)
