# PhrAIse - AI writing assistant
# License: GNU GPLv3
# GitHub: https://github.com/hqrrr/Phraise
# Author: hqrrr
#
# Description: Unit tests for uia main thread.
"""TDD tests for main-thread COM initialization and UIA guard.

Ensures capture_foreground(), focus_foreground(), and replace_text()
work when called from the main Qt thread where COM may not yet be
initialized.  The module-level _ensure_com_initialized() function
acts as a guard — initializing COM MTA on first call, no-oping on
subsequent calls, and never calling CoUninitialize.
"""

import sys
import unittest
from unittest.mock import Mock, patch


# ---------------------------------------------------------------------------
# Imports
# ---------------------------------------------------------------------------

from phraise.text_grabber import TextGrabber, _ensure_com_initialized


# ====================================================================
# 1. _ensure_com_initialized() — unit behaviour
# ====================================================================

class TestEnsureComInitialized(unittest.TestCase):
    """Unit tests for the module-level COM guard."""

    @patch("phraise.text_grabber.sys")
    def test_noop_on_non_windows(self, mock_sys):
        """On non-Windows, _ensure_com_initialized is a no-op."""
        mock_sys.platform = "linux"
        # Should not raise, and should not import pythoncom
        _ensure_com_initialized()

    def test_initializes_com_mta_when_not_initialized(self):
        """On Windows with no COM, calls CoInitializeEx(MTA)."""
        if sys.platform != "win32":
            self.skipTest("Windows-only COM test")

        import pythoncom
        # Ensure we start clean — uninitialize if needed
        try:
            pythoncom.CoUninitialize()
        except Exception:
            pass

        _ensure_com_initialized()
        # Guard should have initialized.  A second call should be harmless.
        _ensure_com_initialized()

    def test_safe_when_already_initialized(self):
        """Calling _ensure_com_initialized twice is safe (no double-init error)."""
        if sys.platform != "win32":
            self.skipTest("Windows-only COM test")

        # Call twice — second call should not raise
        _ensure_com_initialized()
        _ensure_com_initialized()

    def test_safe_when_wrong_apartment_model(self):
        """If thread was already STA, guard should not crash."""
        if sys.platform != "win32":
            self.skipTest("Windows-only COM test")

        import pythoncom
        try:
            pythoncom.CoUninitialize()
        except Exception:
            pass

        # Initialize as STA first (hotkey thread pattern)
        pythoncom.CoInitialize()
        # Now try MTA guard — should not raise
        _ensure_com_initialized()
        pythoncom.CoUninitialize()

    @patch("phraise.text_grabber.sys")
    @patch.dict("sys.modules", {"pythoncom": Mock()})
    def test_calls_coinitializeex_mta(self, mock_sys):
        """On Windows, CoInitializeEx is called with COINIT_MULTITHREADED."""
        import pythoncom
        mock_sys.platform = "win32"
        _ensure_com_initialized()
        pythoncom.CoInitializeEx.assert_called_once_with(
            pythoncom.COINIT_MULTITHREADED
        )

    @patch("phraise.text_grabber.sys")
    @patch.dict("sys.modules", {"pythoncom": Mock()})
    def test_suppresses_already_initialized_error(self, mock_sys):
        """If CoInitializeEx raises, guard swallows the exception."""
        import pythoncom
        mock_sys.platform = "win32"
        pythoncom.CoInitializeEx.side_effect = Exception("already initialized")
        # Should not propagate
        _ensure_com_initialized()

    @patch("phraise.text_grabber.sys")
    def test_does_not_import_pythoncom_on_non_windows(self, mock_sys):
        """On non-Windows, pythoncom is never touched."""
        mock_sys.platform = "darwin"
        with patch("builtins.__import__") as mock_import:
            _ensure_com_initialized()
            # __import__ may be called for other things, but not pythoncom
            for call_args in mock_import.call_args_list:
                self.assertNotIn("pythoncom", str(call_args))


# ====================================================================
# 2. capture_foreground() — COM guard integration
# ====================================================================

class TestCaptureForegroundComGuard(unittest.TestCase):
    """capture_foreground() must call _ensure_com_initialized() first."""

    def setUp(self):
        self.grabber = TextGrabber()

    @patch("phraise.text_grabber._ensure_com_initialized")
    @patch.dict("sys.modules", {"uiautomation": Mock()})
    def test_calls_guard_before_uia(self, mock_guard):
        """capture_foreground calls _ensure_com_initialized before GetFocusedControl."""
        import uiautomation as uia
        mock_control = Mock()
        uia.GetFocusedControl.return_value = mock_control

        self.grabber.capture_foreground()

        mock_guard.assert_called_once()
        uia.GetFocusedControl.assert_called_once()

    @patch("phraise.text_grabber._ensure_com_initialized")
    @patch.dict("sys.modules", {"uiautomation": Mock()})
    def test_stores_control_under_lock(self, mock_guard):
        """capture_foreground stores the focused control via state lock."""
        import uiautomation as uia
        mock_control = Mock()
        uia.GetFocusedControl.return_value = mock_control

        self.grabber.capture_foreground()
        self.assertIs(self.grabber._foreground_control, mock_control)

    @patch("phraise.text_grabber._ensure_com_initialized")
    @patch.dict("sys.modules", {"uiautomation": Mock()})
    def test_sets_none_on_exception(self, mock_guard):
        """If GetFocusedControl raises, _foreground_control is set to None."""
        import uiautomation as uia
        uia.GetFocusedControl.side_effect = RuntimeError("UIA failure")

        self.grabber.capture_foreground()
        self.assertIsNone(self.grabber._foreground_control)


# ====================================================================
# 3. focus_foreground() — COM guard integration
# ====================================================================

class TestFocusForegroundComGuard(unittest.TestCase):
    """focus_foreground() must call _ensure_com_initialized() before SetFocus."""

    def setUp(self):
        self.grabber = TextGrabber()

    @patch("phraise.text_grabber._ensure_com_initialized")
    def test_returns_false_when_no_control_captured(self, mock_guard):
        """If _foreground_control is None, returns False without calling guard."""
        self.grabber._foreground_control = None
        result = self.grabber.focus_foreground()
        self.assertFalse(result)
        mock_guard.assert_not_called()

    @patch("phraise.text_grabber._ensure_com_initialized")
    def test_calls_guard_before_setfocus(self, mock_guard):
        """focus_foreground calls _ensure_com_initialized before SetFocus."""
        mock_control = Mock()
        mock_control.SetFocus.return_value = None
        self.grabber._foreground_control = mock_control

        self.grabber.focus_foreground()

        mock_guard.assert_called_once()
        mock_control.SetFocus.assert_called_once()

    @patch("phraise.text_grabber._ensure_com_initialized")
    def test_returns_false_on_exception(self, mock_guard):
        """If SetFocus raises, returns False."""
        mock_control = Mock()
        mock_control.SetFocus.side_effect = RuntimeError("SetFocus failed")
        self.grabber._foreground_control = mock_control

        result = self.grabber.focus_foreground()
        self.assertFalse(result)


# ====================================================================
# 4. replace_text() — COM guard integration
# ====================================================================

class TestReplaceTextComGuard(unittest.TestCase):
    """replace_text() must call _ensure_com_initialized() before operations."""

    def setUp(self):
        self.grabber = TextGrabber()

    def test_returns_false_for_empty_text(self):
        """Empty new_text returns False immediately, no COM init."""
        with patch("phraise.text_grabber._ensure_com_initialized") as mock_guard:
            result = self.grabber.replace_text("")
            self.assertFalse(result)
            mock_guard.assert_not_called()

    @patch("phraise.text_grabber._ensure_com_initialized")
    def test_calls_guard_before_operations(self, mock_guard):
        """replace_text calls _ensure_com_initialized before UIA ops.
        Called twice: once in replace_text, once via focus_foreground."""
        # Setup: captured control with ValuePattern that succeeds
        mock_control = Mock()
        mock_vp = Mock()
        mock_control.GetValuePattern.return_value = mock_vp
        mock_vp.SetValue.return_value = None
        self.grabber._foreground_control = mock_control

        self.grabber.replace_text("hello")

        self.assertEqual(mock_guard.call_count, 2)


# ====================================================================
# 5. Integration: main-thread COM init pattern
# ====================================================================

class TestMainThreadComIntegration(unittest.TestCase):
    """Verify the main-thread COM initialization pattern from main.py."""

    def test_main_com_init_pattern(self):
        """Replicate main.py's COM init logic — CoInitializeEx doesn't crash."""
        if sys.platform != "win32":
            self.skipTest("Windows-only COM test")

        import pythoncom
        # Simulate what main() does: init MTA before app starts
        try:
            pythoncom.CoInitializeEx(pythoncom.COINIT_MULTITHREADED)
        except Exception:
            pass  # Already initialized — continue

        # Now simulate calling _ensure_com_initialized afterwards —
        # it should be a no-op since COM is already initialized.
        _ensure_com_initialized()

    def test_main_com_init_and_guard_together(self):
        """Main-thread init + guard: capture_foreground doesn't throw COM error."""
        if sys.platform != "win32":
            self.skipTest("Windows-only COM test")

        import pythoncom
        try:
            pythoncom.CoInitializeEx(pythoncom.COINIT_MULTITHREADED)
        except Exception:
            pass  # Already initialized — continue

        # Patch uiautomation so we don't need a real UIA target
        with patch.dict("sys.modules", {"uiautomation": Mock()}):
            import uiautomation as uia
            uia.GetFocusedControl.return_value = Mock()

            grabber = TextGrabber()
            # Should not raise any COM error
            grabber.capture_foreground()


# ====================================================================
# 6. Edge case: guard handles missing pythoncom gracefully
# ====================================================================

class TestGuardMissingPythoncom(unittest.TestCase):
    """_ensure_com_initialized must not crash when pythoncom is unimportable."""

    @patch("phraise.text_grabber.sys")
    @patch("builtins.__import__", side_effect=ImportError("no pythoncom"))
    def test_ignores_import_error(self, mock_import, mock_sys):
        """If pythoncom cannot be imported, guard swallows ImportError."""
        mock_sys.platform = "win32"
        # Should not raise
        _ensure_com_initialized()


# ====================================================================
# Main
# ====================================================================

if __name__ == "__main__":
    unittest.main()
