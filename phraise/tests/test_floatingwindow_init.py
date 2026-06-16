# PhrAIse - AI writing assistant
# License: GNU GPLv3
# GitHub: https://github.com/hqrrr/Phraise
# Author: hqrrr
#
# Description: Unit tests for floatingwindow init.
"""Regression test: FloatingWindow.__init__ must call _setup_window / _build_ui.

The current ``__init__`` (line ~240) sets basic attributes but does **not**
call ``_setup_window()`` or ``_build_ui()``.  This means ``_radius``,
``_bg_color``, ``_drag_bar`` and other UI attributes are never initialized,
causing an ``AttributeError`` on the first paint event.

This test locks the expected contract:

* ``_setup_window()`` must be called during ``__init__`` so that:
  - ``_radius == 12``
  - ``_bg_color`` is a ``QColor``
* ``_build_ui()`` must be called during ``__init__`` so that:
  - ``_drag_bar`` is a ``_DragBar`` instance

Remove these assertions **only** after the production bug is fixed.
"""

import unittest
from unittest.mock import MagicMock, patch

from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication

from phraise.floating_window import FloatingWindow


# ---------------------------------------------------------------------------
# Mocked config.get  --  same defaults as test_toast_lifecycle.py
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
    if default is not None:
        return default
    return "concise"


class TestFloatingWindowInit(unittest.TestCase):
    """FloatingWindow must initialise ``_radius`` and core UI attrs in ``__init__``."""

    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance()
        if cls._app is None:
            cls._app = QApplication([])

    def setUp(self) -> None:
        """Clean up descriptors leaked by `test_callback_after_destroy.py`."""
        for attr in ("_rewrite_texts", "_translation_text"):
            try:
                delattr(FloatingWindow, attr)
            except AttributeError:
                pass

    # ------------------------------------------------------------------
    # Helper
    # ------------------------------------------------------------------

    def _make_fw(self) -> FloatingWindow:
        """Create a minimal ``FloatingWindow`` with mocked dependencies."""
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
    # Tests
    # ------------------------------------------------------------------

    def test_radius_initialised(self):
        """``_radius`` must be set to 12 after construction."""
        fw = self._make_fw()
        self.assertEqual(fw._radius, 12)

    def test_bg_color_initialised(self):
        """``_bg_color`` must be a ``QColor`` after construction."""
        fw = self._make_fw()
        self.assertIsInstance(fw._bg_color, QColor)

    def test_drag_bar_exists(self):
        """``_drag_bar`` must be a ``_DragBar`` instance after construction."""
        fw = self._make_fw()
        self.assertIsNotNone(fw._drag_bar)
        from phraise.floating_window import _DragBar
        self.assertIsInstance(fw._drag_bar, _DragBar)

    def test_paint_event_no_attribute_error(self):
        """Calling ``paintEvent(None)`` must not raise ``AttributeError``.

        If ``_radius`` / ``_bg_color`` / ``_border_color`` are missing,
        ``paintEvent`` will crash with ``AttributeError``.
        """
        fw = self._make_fw()
        try:
            fw.paintEvent(None)
        except AttributeError:
            self.fail("paintEvent(None) raised AttributeError — _setup_window() not called during __init__")
        except Exception:
            # A TypeError about None event is fine; we only care
            # that _radius / _bg_color / _border_color are present.
            pass
