# PhrAIse - AI writing assistant
# License: GNU GPLv3
# GitHub: https://github.com/hqrrr/Phraise
# Author: hqrrr
#
# Description: Unit tests for com apartment.
"""Tests for COM apartment initialization — STA → MTA fix for UIA compatibility.

These tests verify that COM is initialized with COINIT_MULTITHREADED
rather than the default STA (Single-Threaded Apartment). The uiautomation
library requires MTA; STA causes UIA operations to silently fail.

Uses source-code inspection to avoid importing Qt-dependent modules.
"""

import sys
import unittest
from unittest.mock import MagicMock, patch


def _win_only(test_fn):
    return unittest.skipUnless(
        sys.platform == "win32",
        "COM apartment test requires Windows",
    )(test_fn)


# ---------------------------------------------------------------------------
# Tests: phraise.text_grabber._ensure_com_initialized()
# ---------------------------------------------------------------------------

class TestEnsureComInitialized(unittest.TestCase):
    """Unit tests for the _ensure_com_initialized() helper."""

    @_win_only
    def test_already_initialized_does_not_crash(self):
        pythoncom_mock = MagicMock()
        pythoncom_mock.COINIT_MULTITHREADED = 0
        pythoncom_mock.CoInitializeEx.side_effect = OSError("Already initialized")

        with patch.dict("sys.modules", pythoncom=pythoncom_mock):
            import importlib
            import phraise.text_grabber
            importlib.reload(phraise.text_grabber)

            from phraise.text_grabber import _ensure_com_initialized

            # Should not raise
            _ensure_com_initialized()

    def test_pythoncom_not_available_noop(self):
        with patch.dict("sys.modules", pythoncom=None):
            import importlib
            import phraise.text_grabber
            importlib.reload(phraise.text_grabber)

            from phraise.text_grabber import _ensure_com_initialized

            # Should not raise
            _ensure_com_initialized()

    def test_non_windows_is_noop(self):
        if sys.platform == "win32":
            self.skipTest("Windows — platform noop test irrelevant")
        from phraise.text_grabber import _ensure_com_initialized
        result = _ensure_com_initialized()
        self.assertIsNone(result)


# ---------------------------------------------------------------------------
# Tests: main._hotkey_trigger() uses MTA
# ---------------------------------------------------------------------------

class TestHotkeyTriggerComApartment(unittest.TestCase):
    """Verify _hotkey_trigger() uses CoInitializeEx, not CoInitialize()."""

    @_win_only
    def test_no_plain_coinitialize_in_hotkey_trigger(self):
        with open("phraise/main.py", encoding="utf-8") as f:
            source = f.read()

        lines = source.split("\n")
        in_hotkey = False
        hotkey_coinit_plain = False
        for line in lines:
            if "def _hotkey_trigger" in line:
                in_hotkey = True
            elif in_hotkey and line.strip().startswith("def "):
                in_hotkey = False
            elif in_hotkey and "pythoncom.CoInitialize()" == line.strip():
                hotkey_coinit_plain = True

        self.assertFalse(
            hotkey_coinit_plain,
            "_hotkey_trigger should use CoInitializeEx, not CoInitialize()"
        )


# ---------------------------------------------------------------------------
# Tests: detector._poll_loop() uses CoInitializeEx
# ---------------------------------------------------------------------------

class TestPollLoopComApartment(unittest.TestCase):
    """Verify _poll_loop() uses CoInitializeEx(MTA), not CoInitialize()."""

    @_win_only
    def test_source_uses_coinitializeex_mta(self):
        with open("phraise/detector.py", encoding="utf-8") as f:
            source = f.read()

        self.assertIn("CoInitializeEx", source)
        self.assertIn("COINIT_MULTITHREADED", source)

    @_win_only
    def test_no_plain_coinitialize_in_poll_loop(self):
        with open("phraise/detector.py", encoding="utf-8") as f:
            source = f.read()

        lines = source.split("\n")
        in_poll = False
        poll_coinit_plain = False
        for line in lines:
            if "def _poll_loop" in line:
                in_poll = True
            elif in_poll and line.strip().startswith("def "):
                in_poll = False
            elif in_poll and "pythoncom.CoInitialize()" == line.strip():
                poll_coinit_plain = True

        self.assertFalse(
            poll_coinit_plain,
            "_poll_loop should use CoInitializeEx(COINIT_MULTITHREADED), not CoInitialize()"
        )
