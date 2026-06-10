"""TDD tests for FloatingWindow._close() mouse grab release during drag.

When the FloatingWindow is closed (Esc key, close button, programmatic _close())
while the DragBar is in the middle of a mouse-drag operation, _close() must
release the DragBar's mouse grab BEFORE hiding the window. Without this guard,
the mouse stays captured system-wide until the application exits.
"""

import unittest
from unittest.mock import Mock, patch

from PySide6.QtCore import Qt, QEvent, QPoint
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication


# ---- helpers -----------------------------------------------------------

def _mouse_press_event(button=Qt.LeftButton):
    p = QPoint(0, 0)
    return QMouseEvent(QEvent.MouseButtonPress, p, p, button, button, Qt.NoModifier)


def _make_window():
    """Create a minimal FloatingWindow suitable for unit-testing the grab-release
    logic in _close().

    We bypass the full TextGrabber and LLM wiring and only set up the
    parts that _close() depends on.
    """
    from phraise.floating_window import FloatingWindow, _DragBar

    grabber = Mock()
    grabber.restore_clipboard = Mock()
    grabber.text_before_replace = ""
    grabber.control_type_before_replace = ""

    on_close_stub = Mock()

    # Monkey-patch _build_ui / _setup_window to avoid heavy UI setup
    with (patch.object(FloatingWindow, '_setup_window', lambda s: None),
          patch.object(FloatingWindow, '_build_ui', lambda s: None)):
        win = FloatingWindow(grabber, on_close=on_close_stub)

    # _setup_window was patched out, so set attributes it normally creates
    win._titlebar_height = 36
    win.setMouseTracking(True)
    win._radius = 12

    # Simulate what _build_titlebar normally does
    win._drag_bar = _DragBar(win, win._titlebar_height)
    win._save_geometry = Mock()
    win._on_close = on_close_stub
    return win


# ---- tests -------------------------------------------------------------


class TestFloatingWindowCloseDuringDrag(unittest.TestCase):
    """_close() must release DragBar mouse grab if a drag is in progress."""

    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.win = _make_window()

    def tearDown(self):
        try:
            self.win.deleteLater()
        except Exception:
            pass

    # --- _close() releases grab ---

    def test_close_releases_dragbar_grab_when_dragging(self):
        """_close() must call releaseMouse() on the DragBar when mid-drag."""
        bar = self.win._drag_bar
        bar.mousePressEvent(_mouse_press_event())
        self.assertTrue(bar._dragging)

        with patch.object(bar, 'releaseMouse', wraps=bar.releaseMouse) as spy:
            self.win._close()

        spy.assert_called_once()
        self.assertFalse(bar._dragging,
                         "_close() must reset _dragging after releasing grab")

    def test_close_noop_when_not_dragging(self):
        """_close() must not call releaseMouse() if no drag is active."""
        bar = self.win._drag_bar
        self.assertFalse(bar._dragging)

        with patch.object(bar, 'releaseMouse') as spy:
            self.win._close()

        spy.assert_not_called()

    def test_close_still_saves_geometry_and_calls_on_close(self):
        """_close() must still save geometry and call on_close callback."""
        self.win._close()

        self.win._save_geometry.assert_called_once()
        self.win._on_close.assert_called_once()

    # --- close during drag + hide ---

    def test_close_during_drag_hides_window(self):
        """After _close() during a drag, the window should be hidden."""
        bar = self.win._drag_bar
        bar.mousePressEvent(_mouse_press_event())

        with patch.object(self.win, 'hide') as hide_spy:
            self.win._close()

        hide_spy.assert_called_once()
        self.assertFalse(bar._dragging)

    # --- _close() runs even when _drag_bar is missing ---

    def test_close_without_drag_bar_is_safe(self):
        """_close() must not raise AttributeError when _drag_bar is absent."""
        del self.win._drag_bar
        self.win._close()  # must not raise

        self.win._save_geometry.assert_called_once()
        self.win._on_close.assert_called_once()
