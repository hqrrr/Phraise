# PhrAIse - AI writing assistant
# License: GNU GPLv3
# GitHub: https://github.com/hqrrr/Phraise
# Author: hqrrr
#
# Description: Unit tests for uia via hotkey.
"""Tests for UIA operations working correctly on MTA COM threads.

Verifies that text grab UIA operations succeed when the calling thread
initializes COM with COINIT_MULTITHREADED (MTA), and that the hotkey
trigger + detector threads use MTA so uiautomation calls work properly.

Uses source-code inspection to avoid importing Qt-dependent modules.
"""

import sys
import unittest
from unittest.mock import MagicMock, patch


def _win_only(test_fn):
    return unittest.skipUnless(
        sys.platform == "win32",
        "UIA COM apartment test requires Windows",
    )(test_fn)


# ---------------------------------------------------------------------------
# Tests: UIA text grab with MTA COM
# ---------------------------------------------------------------------------

class TestUIATextGrabMTA(unittest.TestCase):
    """UIA operations succeed when COM is initialized as MTA."""

    @_win_only
    def test_uia_get_selected_text_with_mta_com(self):
        pythoncom_mock = MagicMock()
        pythoncom_mock.COINIT_MULTITHREADED = 0

        uia_mock = MagicMock()
        control_mock = MagicMock()
        uia_mock.GetFocusedControl.return_value = control_mock

        tp_mock = MagicMock()
        control_mock.GetTextPattern.return_value = tp_mock

        range_mock = MagicMock()
        range_mock.GetText.return_value = "Hello World"
        tp_mock.GetSelection.return_value = [range_mock]

        with patch.dict("sys.modules", pythoncom=pythoncom_mock, uiautomation=uia_mock):
            pythoncom_mock.CoInitializeEx(pythoncom_mock.COINIT_MULTITHREADED)

            from phraise.text_grabber import TextGrabber

            grabber = TextGrabber()
            grabber._foreground_control = control_mock
            result = grabber._get_selected_via_uia()

            self.assertEqual(result, "Hello World")

            pythoncom_mock.CoUninitialize()

    @_win_only
    def test_uia_replace_text_with_mta_com(self):
        pythoncom_mock = MagicMock()
        pythoncom_mock.COINIT_MULTITHREADED = 0

        uia_mock = MagicMock()
        control_mock = MagicMock()
        uia_mock.GetFocusedControl.return_value = control_mock

        vp_mock = MagicMock()
        control_mock.GetValuePattern.return_value = vp_mock
        control_mock.GetTextPattern.side_effect = AttributeError("no TextPattern")

        with patch.dict("sys.modules", pythoncom=pythoncom_mock, uiautomation=uia_mock):
            pythoncom_mock.CoInitializeEx(pythoncom_mock.COINIT_MULTITHREADED)

            from phraise.text_grabber import TextGrabber

            grabber = TextGrabber()
            grabber._foreground_control = control_mock
            result = grabber._replace_via_uia("New Text")

            self.assertTrue(result)
            vp_mock.SetValue.assert_called_once_with("New Text")

            pythoncom_mock.CoUninitialize()

    @_win_only
    def test_uia_falls_through_on_com_failure(self):
        pythoncom_mock = MagicMock()
        pythoncom_mock.COINIT_MULTITHREADED = 0

        uia_mock = MagicMock()
        uia_mock.GetFocusedControl.side_effect = OSError("UIA not available")

        with patch.dict("sys.modules", pythoncom=pythoncom_mock, uiautomation=uia_mock):
            pythoncom_mock.CoInitializeEx(pythoncom_mock.COINIT_MULTITHREADED)

            from phraise.text_grabber import TextGrabber

            grabber = TextGrabber()
            result = grabber._get_selected_via_uia()
            self.assertEqual(result, "")

            result_replace = grabber._replace_via_uia("text")
            self.assertFalse(result_replace)

            pythoncom_mock.CoUninitialize()


# ---------------------------------------------------------------------------
# Tests: Hotkey trigger source confirms MTA pattern
# ---------------------------------------------------------------------------

class TestHotkeyUIAIntegration(unittest.TestCase):
    """Hotkey trigger initializes MTA COM, enabling UIA text grab."""

    @_win_only
    def test_detector_poll_loop_has_mta_call(self):
        with open("phraise/detector.py", encoding="utf-8") as f:
            source = f.read()

        lines = source.split("\n")
        in_poll = False
        coinit_found = False
        for line in lines:
            if "def _poll_loop" in line:
                in_poll = True
            elif in_poll and line.strip().startswith("def "):
                in_poll = False
            elif in_poll and "CoInitializeEx" in line and "COINIT_MULTITHREADED" in line:
                coinit_found = True

        self.assertTrue(
            coinit_found,
            "_poll_loop must call CoInitializeEx with COINIT_MULTITHREADED for UIA"
        )

    @_win_only
    def test_text_grabber_has_ensure_com_helper(self):
        with open("phraise/text_grabber.py", encoding="utf-8") as f:
            source = f.read()

        self.assertIn("def _ensure_com_initialized", source)
        self.assertIn("CoInitializeEx", source)
