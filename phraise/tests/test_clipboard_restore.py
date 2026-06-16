# PhrAIse - AI writing assistant
# License: GNU GPLv3
# GitHub: https://github.com/hqrrr/Phraise
# Author: hqrrr
#
# Description: Unit tests for clipboard restore.
"""Tests for clipboard save/restore with empty clipboard handling.

Verifies that _clipboard_saved boolean flag is used instead of
truthiness check on _original_clipboard, so empty clipboard content
is preserved after text replacement.
"""

from unittest.mock import patch, PropertyMock
import pyperclip

from phraise.text_grabber import TextGrabber


class TestClipboardRestore:
    def test_save_non_empty_restores(self):
        """Non-empty clipboard is saved and restored correctly."""
        grabber = TextGrabber()
        with patch("pyperclip.paste", return_value="original text"):
            grabber._save_clipboard()
        assert grabber._original_clipboard == "original text"
        assert grabber._clipboard_saved is True

        with patch("pyperclip.copy") as mock_copy:
            grabber._restore_clipboard()
        mock_copy.assert_called_once_with("original text")

    def test_save_empty_restores(self):
        """Empty clipboard is saved and restored correctly (the bug fix).

        Previously, `if self._original_clipboard:` would skip restoration
        when clipboard was "" (falsy), leaving the replaced text on the
        clipboard instead of restoring the original empty state.
        """
        grabber = TextGrabber()
        with patch("pyperclip.paste", return_value=""):
            grabber._save_clipboard()
        assert grabber._original_clipboard == ""
        assert grabber._clipboard_saved is True

        with patch("pyperclip.copy") as mock_copy:
            grabber._restore_clipboard()
        mock_copy.assert_called_once_with("")

    def test_restore_not_called_when_not_saved(self):
        """Restore is a no-op if no save was performed."""
        grabber = TextGrabber()
        assert grabber._clipboard_saved is False

        with patch("pyperclip.copy") as mock_copy:
            grabber._restore_clipboard()
        mock_copy.assert_not_called()

    def test_save_exception_sets_flag_false(self):
        """When _save_clipboard raises, _clipboard_saved is False."""
        grabber = TextGrabber()
        with patch("pyperclip.paste", side_effect=Exception("clipboard error")):
            grabber._save_clipboard()
        assert grabber._clipboard_saved is False

    def test_replace_via_clipboard_empty_original(self, monkeypatch):
        """Full replacement flow preserves empty clipboard.

        After _replace_via_clipboard, the clipboard should be restored
        to its original empty state.
        """
        grabber = TextGrabber()

        # Mock clipboard: paste returns "" (empty clipboard)
        paste_calls = []
        def fake_paste():
            paste_calls.append(1)
            return ""

        # Track what gets copied to clipboard
        copied = []
        def fake_copy(text):
            copied.append(text)

        monkeypatch.setattr(pyperclip, "paste", fake_paste)
        monkeypatch.setattr(pyperclip, "copy", fake_copy)

        # Mock _send_paste to be a no-op
        monkeypatch.setattr(grabber, "_send_paste", lambda: None)

        result = grabber._replace_via_clipboard("replacement text")
        assert result is True

        # The last copy should restore the original empty clipboard
        assert copied[-1] == "", f"Expected empty restore, got {copied[-1]!r}"
