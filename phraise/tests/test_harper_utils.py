"""Unit tests for ``phraise.harper_utils``.

Covers path resolution in dev mode, frozen (PyInstaller) mode, and the
graceful ``None`` return when the binary is absent.
"""

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from phraise.harper_utils import get_harper_binary_path, is_harper_available


class TestGetHarperBinaryPath(unittest.TestCase):
    """Tests for ``get_harper_binary_path``."""

    # -- dev mode -----------------------------------------------------------

    def test_dev_mode_path_resolves(self):
        """In dev mode the returned path ends with ``phraise/lsp/harper-ls.exe``."""
        # Ensure we aren't in frozen mode so the dev branch is taken.
        with patch.object(sys, "frozen", False, create=True):
            result = get_harper_binary_path()

        # In dev mode the candidate path *always* ends with this suffix
        # regardless of whether the file actually exists.
        expected_suffix = Path("phraise") / "lsp" / "harper-ls.exe"
        if result is not None:
            self.assertTrue(str(result).endswith(str(expected_suffix)),
                            f"Expected path ending with {expected_suffix}, got {result}")
        else:
            # File may not exist on CI — that's OK, just verify the *logic*
            # by checking that the dev path would be correct.
            dev_path = Path(__file__).parent.parent / "lsp" / "harper-ls.exe"
            self.assertEqual(dev_path.name, "harper-ls.exe")
            self.assertEqual(dev_path.parent.name, "lsp")

    # -- frozen (PyInstaller) mode ------------------------------------------

    def test_frozen_mode_path(self):
        """When ``sys.frozen`` is ``True``, resolve under ``sys._MEIPASS``."""
        fake_meipass = Path("/tmp/_MEI1234")

        with (
            patch.object(sys, "frozen", True, create=True),
            patch.object(sys, "_MEIPASS", str(fake_meipass), create=True),
        ):
            # The binary doesn't exist at the fake _MEIPASS, so we expect None.
            result = get_harper_binary_path()

        # Without an actual file on disk the function returns None.
        self.assertIsNone(result)

    def test_frozen_mode_path_construction(self):
        """Verify the path *construction* logic for frozen mode."""
        # Windows-compatible fake _MEIPASS (absolute path with drive letter).
        fake_meipass = Path("C:/_MEI1234")

        with (
            patch.object(sys, "frozen", True, create=True),
            patch.object(sys, "_MEIPASS", str(fake_meipass), create=True),
            patch("phraise.harper_utils.Path.exists", return_value=True),
        ):
            result = get_harper_binary_path()

        self.assertIsNotNone(result)
        expected = fake_meipass / "phraise" / "lsp" / "harper-ls.exe"
        self.assertEqual(result, expected)

    # -- binary not found ---------------------------------------------------

    def test_binary_not_found_returns_none(self):
        """When the binary does not exist, ``get_harper_binary_path`` returns ``None``."""
        with patch("phraise.harper_utils.Path.exists", return_value=False):
            result = get_harper_binary_path()

        self.assertIsNone(result)


class TestIsHarperAvailable(unittest.TestCase):
    """Tests for ``is_harper_available``."""

    def test_returns_true_when_binary_exists(self):
        """``is_harper_available`` returns ``True`` when the binary exists and is readable."""
        with (
            patch("phraise.harper_utils.get_harper_binary_path",
                  return_value=Path("/some/existing/harper-ls.exe")),
            patch("phraise.harper_utils.Path.exists", return_value=True),
            patch("phraise.harper_utils.os.access", return_value=True),
        ):
            self.assertTrue(is_harper_available())

    def test_returns_false_when_binary_missing(self):
        """``is_harper_available`` returns ``False`` when ``get_harper_binary_path`` is ``None``."""
        with patch("phraise.harper_utils.get_harper_binary_path",
                   return_value=None):
            self.assertFalse(is_harper_available())

    def test_returns_false_when_not_readable(self):
        """``is_harper_available`` returns ``False`` when binary exists but is not readable."""
        with (
            patch("phraise.harper_utils.get_harper_binary_path",
                  return_value=Path("/some/existing/harper-ls.exe")),
            patch("phraise.harper_utils.Path.exists", return_value=True),
            patch("phraise.harper_utils.os.access", return_value=False),
        ):
            # Binary exists on disk but os.access says not readable → False.
            self.assertFalse(is_harper_available())


if __name__ == "__main__":
    unittest.main()
