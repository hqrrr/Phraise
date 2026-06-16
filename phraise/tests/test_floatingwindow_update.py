# PhrAIse - AI writing assistant
# License: GNU GPLv3
# GitHub: https://github.com/hqrrr/Phraise
# Author: hqrrr
#
# Description: Unit tests for floatingwindow update.
"""Tests for FloatingWindow.update() rename (Task 14).

``def update(self)`` was renamed to ``def process_events(self)`` to stop
shadowing ``QWidget.update()`` (which schedules a paint event).

Verifies:
- ``process_events()`` calls ``QApplication.processEvents()``
- ``QWidget.update()`` (repaint scheduling) is no longer shadowed
- tkinter compat behavior (process events) is preserved under new name
"""

import unittest
from unittest.mock import MagicMock, patch

from phraise.floating_window import FloatingWindow


def _qapp():
    """Return (or create) a QApplication singleton."""
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def _make_window():
    """Create a FloatingWindow with a mock TextGrabber."""
    grabber = MagicMock()
    return FloatingWindow(grabber=grabber)


class TestFloatingWindowUpdateRename(unittest.TestCase):
    """Verify the update→process_events rename is correct."""

    @classmethod
    def setUpClass(cls) -> None:
        cls._app = _qapp()

    def setUp(self) -> None:
        # Clean up any _DeletedAttr descriptors left by
        # test_callback_after_destroy.py on the FloatingWindow class.
        # Those tests set class-level descriptors (_rewrite_texts,
        # _translation_text) that raise RuntimeError on access.
        for _leaked_attr in ("_rewrite_texts", "_translation_text",):
            try:
                delattr(FloatingWindow, _leaked_attr)
            except AttributeError:
                pass
        self.window = _make_window()

    def tearDown(self) -> None:
        self.window.deleteLater()
        del self.window

    # ------------------------------------------------------------------
    # process_events() still works (tkinter compat preserved)
    # ------------------------------------------------------------------

    @patch("phraise.floating_window.QApplication.processEvents")
    def test_process_events_calls_qapplication_processevents(self, mock_process):
        """process_events() should delegate to QApplication.processEvents()."""
        self.window.process_events()
        mock_process.assert_called_once()

    # ------------------------------------------------------------------
    # QWidget.update() no longer shadowed
    # ------------------------------------------------------------------

    def test_qwidget_update_is_not_shadowed(self):
        """Calling .update() should now invoke QWidget.update() (no error)."""
        # Before the rename, window.update() would call processEvents().
        # After rename, it should be the original QWidget.update() which
        # schedules a paint event and should not raise.
        try:
            self.window.update()
        except Exception as e:
            self.fail(f"QWidget.update() raised unexpectedly: {e}")

    def test_update_is_qwidget_update_not_processevents(self):
        """Verify .update() is NOT the old processEvents alias."""
        with patch.object(self.window, "update") as mock_update:
            self.window.process_events()
            # process_events should NOT trigger update()
            mock_update.assert_not_called()

    # ------------------------------------------------------------------
    # No method named 'update' that shadows QWidget
    # ------------------------------------------------------------------

    def test_no_method_named_update_on_window(self):
        """FloatingWindow should not have its own 'update' method anymore."""
        mro = type(self.window).__mro__
        # Walk MRO to find where 'update' is defined
        for cls in mro:
            if "update" in cls.__dict__:
                # It should only be found on QWidget or above, not on FloatingWindow
                self.assertNotEqual(
                    cls,
                    FloatingWindow,
                    f"FloatingWindow still shadows QWidget.update()",
                )
                break
        else:
            self.fail("update() not found anywhere in MRO")


if __name__ == "__main__":
    unittest.main()
