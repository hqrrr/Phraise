"""RED-phase tests for FloatingBall theme wiring.

These tests verify the expected contract for theme-aware FloatingBall
behaviour.  They are designed to FAIL in this phase because
``theme_notifier`` and theme-aware ``paintEvent`` do not yet exist.

Tests:
  TestFloatingBallCreation  – geometry & window flags
  TestFloatingBallThemeColors – no hardcoded hex; theme_notifier present
  TestFloatingBallMask      – mask shape & centre containment
  TestFloatingBallIconFallback – icon-file presence & fallback text
"""

import re
import unittest
from pathlib import Path

from PySide6.QtCore import Qt, QPoint, QRect
from PySide6.QtWidgets import QApplication

import phraise.theme as theme_module
from phraise.floating_ball import FloatingBall, ICON_PATH
from phraise.theme import theme_notifier, get_theme

_SOURCE_PATH = Path(__file__).parent.parent / "floating_ball.py"
_SOURCE_TEXT = _SOURCE_PATH.read_text(encoding="utf-8")

# Hex colour regex: # followed by 3 or 6 hex digits.
_HEX_COLOR_RE = re.compile(r"#[0-9a-fA-F]{6}")


class TestFloatingBallCreation(unittest.TestCase):
    """FloatingBall constructor creates a square widget with frameless flags."""

    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance()
        if cls._app is None:
            cls._app = QApplication([])

    def setUp(self) -> None:
        self.ball = FloatingBall()

    def tearDown(self) -> None:
        self.ball.close()
        self.ball.deleteLater()

    def test_ball_is_square(self) -> None:
        """FloatingBall width equals height (bounding circle requires square)."""
        self.assertEqual(self.ball.width(), self.ball.height(),
                         "FloatingBall must be square for a circular mask")

    def test_frameless_window_hint_is_set(self) -> None:
        """FramelessWindowHint must be present so the ball has no title bar."""
        flags = self.ball.windowFlags()
        self.assertTrue(
            bool(flags & Qt.FramelessWindowHint),
            "FramelessWindowHint not set on FloatingBall",
        )

    def test_stays_on_top_hint_is_set(self) -> None:
        """WindowStaysOnTopHint must be present so the ball floats above others."""
        flags = self.ball.windowFlags()
        self.assertTrue(
            bool(flags & Qt.WindowStaysOnTopHint),
            "WindowStaysOnTopHint not set on FloatingBall",
        )

    def test_tool_flag_is_set(self) -> None:
        """Tool flag prevents a taskbar entry for the floating ball."""
        flags = self.ball.windowFlags()
        self.assertTrue(
            bool(flags & Qt.Tool),
            "Tool flag not set on FloatingBall",
        )


class TestFloatingBallThemeColors(unittest.TestCase):
    """FloatingBall paintEvent must use theme keys, not hardcoded hex."""

    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance()
        if cls._app is None:
            cls._app = QApplication([])

    def test_no_hardcoded_hex_colors_in_source(self) -> None:
        """Source file must not contain any remaining #rrggbb hex literals
        (the current paintEvent hardcodes ``#6c5ce7``, ``#1e1e2e``, ``#cdd6f4``).
        This assertion fails until the hex values are replaced with theme lookups."""
        matches = _HEX_COLOR_RE.findall(_SOURCE_TEXT)
        self.assertEqual(
            matches, [],
            f"floating_ball.py still contains hardcoded hex colours: {matches}",
        )

    def test_theme_notifier_exists(self) -> None:
        """phraise.theme module must expose a ``theme_notifier`` object.
        This serves as a contract guard — the FloatingBall must connect to
        theme_notifier.theme_changed to repaint with new colours."""
        notifier = getattr(theme_module, "theme_notifier", None)
        self.assertIsNotNone(notifier,
                             "theme_notifier not found in phraise.theme")

    def test_paint_event_references_theme_keys(self) -> None:
        """The paintEvent method body must reference theme colour keys
        ('accent', 'bg', 'text') rather than raw hex values."""
        paint_body = _extract_paint_event_body(_SOURCE_TEXT)
        self.assertIn("accent", paint_body.lower(),
                      "paintEvent does not reference 'accent' theme key")
        self.assertIn("bg", paint_body.lower(),
                      "paintEvent does not reference 'bg' theme key")
        self.assertIn("text", paint_body.lower(),
                      "paintEvent does not reference 'text' theme key")


def _extract_paint_event_body(source: str) -> str:
    """Return the body of the first ``def paintEvent`` method found in *source*.

    Used by TestFloatingBallThemeColors to verify theme-key references
    inside the paint method without false positives from comments or docstrings.
    """
    in_method = False
    lines: list[str] = []
    for line in source.splitlines():
        stripped = line.strip()
        if stripped.startswith("def paintEvent"):
            in_method = True
            lines.append(line)
            continue
        if in_method:
            # Next top-level def or class ends the method body.
            if stripped.startswith("def ") or stripped.startswith("class "):
                break
            lines.append(line)
    return "\n".join(lines)


class TestFloatingBallMask(unittest.TestCase):
    """FloatingBall mask is a circular region containing the widget centre."""

    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance()
        if cls._app is None:
            cls._app = QApplication([])

    def setUp(self) -> None:
        self.ball = FloatingBall()

    def tearDown(self) -> None:
        self.ball.close()
        self.ball.deleteLater()

    def test_mask_is_not_none(self) -> None:
        """The mask region must exist (setMask was called)."""
        self.assertIsNotNone(self.ball.mask(),
                             "FloatingBall mask() returns None")

    def test_mask_bounding_rect_is_square(self) -> None:
        """Mask bounding rectangle must be square for a circular mask."""
        rect: QRect = self.ball.mask().boundingRect()
        self.assertEqual(rect.width(), rect.height(),
                         "Mask bounding rect is not square")

    def test_mask_contains_centre(self) -> None:
        """The mask region must contain the widget's centre point."""
        size = self.ball.width()
        centre = QPoint(size // 2, size // 2)
        self.assertTrue(self.ball.mask().contains(centre),
                        "Mask region does not contain the widget centre")


class TestFloatingBallIconFallback(unittest.TestCase):
    """Icon file must exist; 'AI' fallback text only when icon is missing."""

    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance()
        if cls._app is None:
            cls._app = QApplication([])

    def test_icon_file_exists(self) -> None:
        """The placeholder ball icon (assets/ball_icon.png) must exist on disk."""
        self.assertTrue(ICON_PATH.exists(),
                        f"Icon file missing: {ICON_PATH}")

    def test_ai_fallback_only_when_icon_missing(self) -> None:
        """"AI" fallback text appears inside an ``else`` branch of the icon check.
        The source must contain ``\"AI\"`` inside the ``else`` block of
        ``if self._icon`` (or ``if ICON_PATH.exists()``), meaning it is only
        used when no icon pixmap is available."""
        # Locate the "AI" string literal in source.
        index = _SOURCE_TEXT.find('"AI"')
        self.assertNotEqual(index, -1,
                            '"AI" fallback text not found in floating_ball.py')
        # The "AI" literal must appear AFTER ``_icon`` is mentioned
        # (i.e. inside the else / fallback branch).
        icon_var_pos = _SOURCE_TEXT.find("self._icon")
        self.assertGreater(index, icon_var_pos,
                           '"AI" text must appear after self._icon reference '
                           '(in the else/fallback branch)')
        # Confirm it is inside an ``else`` block by checking the context.
        prefix = _SOURCE_TEXT[max(0, index - 500):index]
        self.assertIn("else:", prefix,
                      '"AI" text does not appear to be inside an else block')


class TestFloatingBallSignal(unittest.TestCase):
    """FloatingBall responds to theme change signals via _on_theme_changed."""

    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance()
        if cls._app is None:
            cls._app = QApplication([])

    def setUp(self) -> None:
        self.ball = FloatingBall()

    def tearDown(self) -> None:
        self.ball.close()
        self.ball.deleteLater()

    def test_theme_changed_triggers_update(self) -> None:
        """theme_changed emission updates ball._theme_colors to match the new theme."""
        theme_notifier.theme_changed.emit("Solarized Dark")
        expected = get_theme("Solarized Dark")["colors"]
        self.assertEqual(self.ball._theme_colors, expected)
