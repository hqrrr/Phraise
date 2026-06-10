"""Test multi-line range extraction in ``_extract_text_at_range``.

Verifies that the helper correctly handles ranges spanning multiple lines
(line offsets) — not just character offsets on line 0.
"""

import unittest

from phraise.harper_types import LspPosition, LspRange, _extract_text_at_range


class TestExtractTextAtRangeMultiLine(unittest.TestCase):
    """Multi-line range support for ``_extract_text_at_range``."""

    def test_two_lines_partial(self):
        """Range spanning middle of line 1 to middle of line 2."""
        text = "line0\nline1\nline2"
        r = LspRange(LspPosition(1, 2), LspPosition(2, 4))
        result = _extract_text_at_range(text, r)
        self.assertEqual(result, "ne1\nline")

    def test_two_lines_start_of_line1_to_end_of_line2(self):
        """Range from start of line 1 to end of line 2."""
        text = "aaa\nbbb\nccc"
        r = LspRange(LspPosition(1, 0), LspPosition(2, 3))
        result = _extract_text_at_range(text, r)
        self.assertEqual(result, "bbb\nccc")

    def test_three_lines_middle(self):
        """Range spanning middle of line 0 to middle of line 2 (one full middle line)."""
        text = "hello\nworld\nfoo"
        r = LspRange(LspPosition(0, 1), LspPosition(2, 2))
        result = _extract_text_at_range(text, r)
        self.assertEqual(result, "ello\nworld\nfo")

    def test_single_line_still_works(self):
        """Backward compatibility: single-line (line=0) ranges still work."""
        text = "helo wrld"
        r = LspRange(LspPosition(0, 0), LspPosition(0, 4))
        self.assertEqual(_extract_text_at_range(text, r), "helo")

    def test_single_line_nonzero_line(self):
        """Single-line range on a non-zero line."""
        text = "aaa\nbbb\nccc"
        r = LspRange(LspPosition(1, 0), LspPosition(1, 3))
        self.assertEqual(_extract_text_at_range(text, r), "bbb")

    def test_empty_range_multi_line(self):
        """Empty range where start == end on a non-zero line."""
        text = "aaa\nbbb\nccc"
        r = LspRange(LspPosition(1, 2), LspPosition(1, 2))
        self.assertEqual(_extract_text_at_range(text, r), "")

    def test_full_content(self):
        """Range covering entire multi-line text."""
        text = "abc\ndef\nghi"
        r = LspRange(LspPosition(0, 0), LspPosition(2, 3))
        self.assertEqual(_extract_text_at_range(text, r), "abc\ndef\nghi")

    def test_range_end_of_line0_to_start_of_line1(self):
        """Range from end of line 0 to start of line 1 — zero-width middle."""
        text = "abc\ndef"
        r = LspRange(LspPosition(0, 3), LspPosition(1, 0))
        result = _extract_text_at_range(text, r)
        self.assertEqual(result, "\n")


if __name__ == "__main__":
    unittest.main()
