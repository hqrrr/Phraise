"""Tests for FloatingWindow.cleanup() (Task 13).

Verifies that the renamed ``cleanup()`` method:
  - Removes the i18n listener via ``remove_listener(self._retranslate_ui)``
  - Calls ``_save_geometry()``, ``hide()``, and ``super().deleteLater()``
  - Gracefully catches and logs exceptions during save/hide
"""

import unittest
from unittest.mock import ANY, MagicMock, call, patch

from PySide6.QtWidgets import QWidget

from phraise.floating_window import FloatingWindow


def _make_fw(**overrides) -> FloatingWindow:
    """Return a bare ``FloatingWindow`` whose ``__init__`` was skipped."""
    with patch.object(FloatingWindow, "__init__", return_value=None):
        fw = FloatingWindow.__new__(FloatingWindow)

    fw._retranslate_ui = MagicMock()
    fw._save_geometry = MagicMock()
    fw.hide = MagicMock()

    for k, v in overrides.items():
        setattr(fw, k, v)
    return fw


class TestFloatingWindowCleanup(unittest.TestCase):
    """Tests for the renamed ``cleanup()`` method."""

    @classmethod
    def setUpClass(cls):
        cls._delete_later_patcher = patch.object(QWidget, "deleteLater")
        cls._mock_delete_later = cls._delete_later_patcher.start()

    @classmethod
    def tearDownClass(cls):
        cls._delete_later_patcher.stop()

    def setUp(self):
        self._remove_patcher = patch("phraise.floating_window.remove_listener")
        self._mock_remove = self._remove_patcher.start()
        self._mock_delete_later.reset_mock()

    def tearDown(self):
        self._remove_patcher.stop()

    # ------------------------------------------------------------------
    # Happy path
    # ------------------------------------------------------------------

    def test_cleanup_removes_listener(self):
        fw = _make_fw()
        fw.cleanup()
        self._mock_remove.assert_called_once_with(fw._retranslate_ui)

    def test_cleanup_saves_geometry(self):
        fw = _make_fw()
        fw.cleanup()
        fw._save_geometry.assert_called_once()

    def test_cleanup_hides_window(self):
        fw = _make_fw()
        fw.cleanup()
        fw.hide.assert_called_once()

    def test_cleanup_calls_delete_later(self):
        fw = _make_fw()
        fw.cleanup()
        self._mock_delete_later.assert_called_once()

    def test_cleanup_call_order(self):
        """Verify listener is removed first, then save/hide/deleteLater."""
        fw = _make_fw()
        mgr = MagicMock()
        mgr.attach_mock(self._mock_remove, "remove_listener")
        mgr.attach_mock(fw._save_geometry, "_save_geometry")
        mgr.attach_mock(fw.hide, "hide")
        mgr.attach_mock(self._mock_delete_later, "deleteLater")

        fw.cleanup()

        mgr.assert_has_calls([
            call.remove_listener(ANY),
            call._save_geometry(),
            call.hide(),
            call.deleteLater(),
        ])

    # ------------------------------------------------------------------
    # Exception safety
    # ------------------------------------------------------------------

    @patch("phraise.floating_window.write_error")
    def test_cleanup_catches_save_geometry_error(self, mock_write: MagicMock):
        fw = _make_fw()
        fw._save_geometry.side_effect = RuntimeError("geometry save failed")
        fw.cleanup()
        mock_write.assert_called_once()
        fw.hide.assert_called_once()
        self._mock_delete_later.assert_called_once()

    @patch("phraise.floating_window.write_error")
    def test_cleanup_catches_hide_error(self, mock_write: MagicMock):
        fw = _make_fw()
        fw.hide.side_effect = RuntimeError("hide failed")
        fw.cleanup()
        mock_write.assert_called_once()
        self._mock_delete_later.assert_called_once()

    @patch("phraise.floating_window.write_error")
    def test_cleanup_both_errors_still_deletes(self, mock_write: MagicMock):
        """Both save and hide fail — deleteLater still called, both errors logged."""
        fw = _make_fw()
        fw._save_geometry.side_effect = RuntimeError("save err")
        fw.hide.side_effect = RuntimeError("hide err")
        fw.cleanup()
        self.assertEqual(mock_write.call_count, 2)
        self._mock_delete_later.assert_called_once()

    # ------------------------------------------------------------------
    # Regression — no shadowing
    # ------------------------------------------------------------------

    def test_cleanup_is_not_named_destroy(self):
        """Regression: the cleanup method is NOT named destroy().

        QWidget itself has destroy(), so we check that FloatingWindow does
        NOT define its own destroy() — the old shadowing method is gone.
        """
        self.assertTrue(hasattr(FloatingWindow, "cleanup"))
        self.assertNotIn("destroy", FloatingWindow.__dict__)
        self.assertEqual(FloatingWindow.cleanup.__name__, "cleanup")


if __name__ == "__main__":
    unittest.main()
