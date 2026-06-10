"""TDD tests for _DragBar.hideEvent() mouse grab release guarantee.

When _DragBar is hidden during an active drag operation (e.g., FloatingWindow
is closed while the user is dragging), hideEvent() must release the mouse grab
to prevent a permanent global cursor capture.
"""

import unittest
from unittest.mock import Mock, patch

from PySide6.QtCore import Qt, QEvent, QPoint
from PySide6.QtGui import QMouseEvent, QHideEvent
from PySide6.QtWidgets import QApplication, QWidget


# ---- helpers -----------------------------------------------------------

def _mouse_press_event(button=Qt.LeftButton):
    """Build a minimal mouse-press QMouseEvent.

    Uses the 6-arg signature:
      QMouseEvent(type, localPos, globalPos, button, buttons, modifiers)
    """
    p = QPoint(0, 0)
    return QMouseEvent(QEvent.MouseButtonPress, p, p, button, button, Qt.NoModifier)


def _mouse_release_event(button=Qt.LeftButton):
    p = QPoint(0, 0)
    return QMouseEvent(QEvent.MouseButtonRelease, p, p, button, Qt.NoButton, Qt.NoModifier)


# ---- tests -------------------------------------------------------------


class TestDragBarHideEvent(unittest.TestCase):
    """hideEvent() must release mouse grab when the widget is hidden mid-drag."""

    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self):
        from phraise.floating_window import _DragBar
        self.window = QWidget()
        self.window._save_geometry = Mock()
        self.bar = _DragBar(self.window)

    def tearDown(self):
        self.window.deleteLater()

    # --- hideEvent during active drag ---

    def test_hide_event_releases_grab_when_dragging(self):
        """hideEvent() calls releaseMouse() and clears _dragging during active drag."""
        self.bar.mousePressEvent(_mouse_press_event())
        self.assertTrue(self.bar._dragging)

        with patch.object(self.bar, 'releaseMouse', wraps=self.bar.releaseMouse) as spy:
            self.bar.hideEvent(QHideEvent())

        spy.assert_called_once()
        self.assertFalse(self.bar._dragging,
                         "hideEvent must reset _dragging flag")

    def test_hide_event_noop_when_not_dragging(self):
        """hideEvent() must NOT call releaseMouse() when no drag is active."""
        self.assertFalse(self.bar._dragging)

        with patch.object(self.bar, 'releaseMouse') as spy:
            self.bar.hideEvent(QHideEvent())

        spy.assert_not_called()

    def test_hide_event_calls_super(self):
        """hideEvent() must call super().hideEvent() so Qt sees the event."""
        self.bar.mousePressEvent(_mouse_press_event())
        # Patch __class__.hideEvent on QWidget to spy on the unbound method
        orig_hide = QWidget.hideEvent
        super_called = False

        def _spy_hide(instance, event):
            nonlocal super_called
            super_called = True
            orig_hide(instance, event)

        QWidget.hideEvent = _spy_hide
        try:
            self.bar.hideEvent(QHideEvent())
        finally:
            QWidget.hideEvent = orig_hide

        self.assertTrue(super_called, "super().hideEvent() was not called")
        self.assertFalse(self.bar._dragging)

    # --- normal drag completion still releases ---

    def test_normal_release_event_releases_mouse(self):
        """mouseReleaseEvent() still releases grab after a complete drag."""
        self.bar.mousePressEvent(_mouse_press_event())
        self.assertTrue(self.bar._dragging)

        with patch.object(self.bar, 'releaseMouse', wraps=self.bar.releaseMouse) as spy:
            self.bar.mouseReleaseEvent(_mouse_release_event())

        spy.assert_called_once()
        self.assertFalse(self.bar._dragging)

    def test_double_hide_is_idempotent(self):
        """Calling hideEvent twice after a drag start must be safe."""
        self.bar.mousePressEvent(_mouse_press_event())
        self.bar.hideEvent(QHideEvent())
        # Second hide — must not raise or call releaseMouse again
        with patch.object(self.bar, 'releaseMouse') as spy:
            self.bar.hideEvent(QHideEvent())
        spy.assert_not_called()
        self.assertFalse(self.bar._dragging)

    # --- right-click does not start a drag ---

    def test_right_click_does_not_grab(self):
        """Right-click must not trigger grabMouse or start dragging."""
        self.bar.mousePressEvent(_mouse_press_event(Qt.RightButton))
        self.assertFalse(self.bar._dragging)
        with patch.object(self.bar, 'releaseMouse') as spy:
            self.bar.hideEvent(QHideEvent())
        spy.assert_not_called()
