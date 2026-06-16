# PhrAIse - AI writing assistant
# License: GNU GPLv3
# GitHub: https://github.com/hqrrr/Phraise
# Author: hqrrr
#
# Description: Unit tests for floatingwindow resize.
"""Regression tests for FloatingWindow resize behaviour.

The frameless window's resize margins are covered by child widgets
(drag bar, tabs, footer, scroll area). Mouse events on those children
near the window edges must be forwarded to the window's resize logic.
"""

import unittest
from unittest.mock import MagicMock, patch

from PySide6.QtCore import Qt, QEvent, QPoint
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication


_CONFIG_DEFAULTS = {
    ("floating_window", "opacity"): 0.95,
    ("floating_window", "width"): 400,
    ("floating_window", "height"): 500,
    ("floating_window", "position_x"): 100,
    ("floating_window", "position_y"): 100,
    ("floating_window", "last_style"): "concise",
    ("floating_window", "last_tab"): "optimize",
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


class TestFloatingWindowResizeFromChildren(unittest.TestCase):
    """Resize must work when the cursor is over child widgets."""

    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication([])

    def _make_window(self):
        """Create a real FloatingWindow with mocked external deps."""
        from phraise.floating_window import FloatingWindow

        grabber = MagicMock()
        grabber.restore_clipboard = MagicMock()
        grabber.text_before_replace = ""
        grabber.control_type_before_replace = ""

        on_close_stub = MagicMock()

        with (
            patch("phraise.floating_window.add_listener", return_value=None),
            patch("phraise.floating_window.config.update_section", return_value=None),
            patch("phraise.i18n.add_listener", return_value=None),
            patch("phraise.floating_window.config.get", side_effect=_mock_config_get),
        ):
            win = FloatingWindow(grabber, on_close=on_close_stub)
            win._save_geometry = MagicMock()
            return win

    def _mouse_event(self, etype, local_pos, global_pos, button=Qt.LeftButton, buttons=Qt.LeftButton):
        return QMouseEvent(etype, local_pos, global_pos, button, buttons, Qt.NoModifier)

    def test_resize_starts_from_child_widget_right_edge(self):
        """Pressing the right-edge resize margin on a child widget starts resize."""
        win = self._make_window()
        win.show()
        try:
            # Find a child widget that covers the right edge (the tab widget).
            child = win._tabs
            self.assertIsNotNone(child)

            # Position near the right edge of the window, mapped to child coords.
            win_geo = win.geometry()
            edge_pos_global = QPoint(win_geo.right() - 2, win_geo.center().y())
            child_local = child.mapFromGlobal(edge_pos_global)

            # Sanity: in window coords this is within the east resize margin.
            window_local = child.mapTo(win, child_local)
            self.assertGreaterEqual(window_local.x(), win.width() - win._resize_margin)

            press = self._mouse_event(
                QEvent.MouseButtonPress,
                child_local,
                edge_pos_global,
            )
            handled = win.eventFilter(child, press)

            self.assertTrue(handled, "eventFilter should consume edge press")
            self.assertTrue(win._resizing)
            self.assertEqual(win._resize_edge, "e")

            # Drag 20 px to the right.
            drag_global = edge_pos_global + QPoint(20, 0)
            move = self._mouse_event(
                QEvent.MouseMove,
                child.mapFromGlobal(drag_global),
                drag_global,
                buttons=Qt.LeftButton,
            )
            win.eventFilter(child, move)

            self.assertEqual(win.width(), win_geo.width() + 20)
        finally:
            win.close()
            win.deleteLater()

    def test_non_edge_click_on_child_is_not_consumed(self):
        """Clicking away from the resize margin should let the child handle it."""
        win = self._make_window()
        win.show()
        try:
            child = win._tabs
            center_global = child.mapToGlobal(QPoint(child.width() // 2, child.height() // 2))
            press = self._mouse_event(
                QEvent.MouseButtonPress,
                QPoint(child.width() // 2, child.height() // 2),
                center_global,
            )
            handled = win.eventFilter(child, press)
            self.assertFalse(handled)
            self.assertFalse(win._resizing)
        finally:
            win.close()
            win.deleteLater()

    def test_drag_bar_still_drags_when_not_on_edge(self):
        """The drag bar should not start resize when clicked away from edges."""
        win = self._make_window()
        win.show()
        try:
            bar = win._drag_bar
            center_local = QPoint(bar.width() // 2, bar.height() // 2)
            center_global = bar.mapToGlobal(center_local)
            press = self._mouse_event(
                QEvent.MouseButtonPress,
                center_local,
                center_global,
            )
            handled = win.eventFilter(bar, press)
            self.assertFalse(handled)
            self.assertFalse(win._resizing)
        finally:
            win.close()
            win.deleteLater()

    def test_combo_box_edge_click_not_consumed(self):
        """Click on source-lang combo near window's right edge must NOT start resize."""
        win = self._make_window()
        win.show()
        try:
            combo = win._source_lang
            self.assertIsNotNone(combo)

            # Compute a position on the combo box that falls within the
            # window's right-edge resize margin (in window coordinates).
            combo_tl = combo.mapTo(win, QPoint(0, 0))
            center_y = combo_tl.y() + combo.height() // 2
            window_local = QPoint(win.width() - 2, center_y)
            global_pos = win.mapToGlobal(window_local)
            combo_local = combo.mapFromGlobal(global_pos)

            # Sanity: the window-local X is within the east resize margin.
            computed_window_local = combo.mapTo(win, combo_local)
            self.assertGreaterEqual(
                computed_window_local.x(), win.width() - win._resize_margin
            )

            press = self._mouse_event(
                QEvent.MouseButtonPress, combo_local, global_pos
            )
            handled = win.eventFilter(combo, press)

            self.assertFalse(handled, "combo edge click should NOT be consumed")
            self.assertFalse(win._resizing, "resize should NOT start")
        finally:
            win.close()
            win.deleteLater()

    def test_combo_box_mouse_move_near_edge_no_resize(self):
        """Mouse move on combo near window's right edge must NOT be consumed."""
        win = self._make_window()
        win.show()
        try:
            combo = win._source_lang
            self.assertFalse(win._resizing)

            # Same position computation as above.
            combo_tl = combo.mapTo(win, QPoint(0, 0))
            center_y = combo_tl.y() + combo.height() // 2
            window_local = QPoint(win.width() - 2, center_y)
            global_pos = win.mapToGlobal(window_local)
            combo_local = combo.mapFromGlobal(global_pos)

            move = self._mouse_event(
                QEvent.MouseMove, combo_local, global_pos
            )
            handled = win.eventFilter(combo, move)

            self.assertFalse(handled, "combo edge mouse move should NOT be consumed")
            self.assertFalse(win._resizing, "resizing should remain False")
        finally:
            win.close()
            win.deleteLater()


if __name__ == "__main__":
    unittest.main()
