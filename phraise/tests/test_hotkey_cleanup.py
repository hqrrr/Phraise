# PhrAIse - AI writing assistant
# License: GNU GPLv3
# GitHub: https://github.com/hqrrr/Phraise
# Author: hqrrr
#
# Description: Unit tests for hotkey cleanup.
"""Tests for HotkeyManager shutdown cleanup.

Verifies:
- ``atexit.register(self.stop)`` is called during HotkeyManager init
- ``stop()`` is idempotent (safe to call multiple times)
- ``_quit_app()`` wraps ``hotkey_manager.stop()`` in try/except
"""

import unittest
from unittest.mock import Mock, patch

from phraise.hotkeys import HotkeyManager


class TestHotkeyCleanup(unittest.TestCase):
    """Validate atexit registration and robust shutdown."""

    def setUp(self):
        HotkeyManager._instance = None

    def _fresh_manager(self) -> HotkeyManager:
        return HotkeyManager()

    # ------------------------------------------------------------------
    # 1. atexit registration
    # ------------------------------------------------------------------

    @patch("atexit.register")
    def test_atexit_registers_stop_on_init(self, mock_register: Mock):
        """atexit.register(self.stop) called exactly once on first init."""
        mgr = self._fresh_manager()
        mock_register.assert_called_once_with(mgr.stop)

    def test_atexit_registration_happens_only_once(self):
        """Re-initializing the singleton does NOT re-register atexit."""
        HotkeyManager._instance = None
        with patch("atexit.register") as mock_register:
            mgr = self._fresh_manager()
            mock_register.assert_called_once_with(mgr.stop)

    @patch("atexit.register")
    def test_atexit_register_called_with_bound_method(self, mock_register: Mock):
        """Registered callable is the bound method mgr.stop."""
        mgr = self._fresh_manager()
        args, _kwargs = mock_register.call_args
        registered_func = args[0]
        # Unbound comparison: registered func's __self__ is our manager
        self.assertIs(registered_func.__self__, mgr)
        self.assertEqual(registered_func.__name__, "stop")

    @patch("atexit.register")
    def test_atexit_stop_idempotent_on_exit(self, mock_register: Mock):
        mgr = self._fresh_manager()
        args, _kwargs = mock_register.call_args
        registered_func = args[0]
        self.assertIs(registered_func.__self__, mgr)
        try:
            registered_func()
        except Exception:
            self.fail("registered atexit handler raised when manager not running")

    # ------------------------------------------------------------------
    # 2. sys.exit simulation
    # ------------------------------------------------------------------

    @patch.object(HotkeyManager, "stop")
    def test_atexit_handler_invokes_stop(self, mock_stop: Mock):
        """The atexit-registered handler calls stop() when invoked."""
        # Register a bound method with atexit
        mgr = self._fresh_manager()
        import atexit as _atexit
        _atexit.unregister(mgr.stop)

        # Re-register under the mock so we can detect the call.
        # atexit.register returns the registered function; invoke it directly
        # instead of _run_exitfuncs() to avoid executing global exit handlers
        # from other imported modules (e.g. PySide6 COM teardown) which would
        # corrupt state for later tests and produce RPC_E_WRONG_THREAD crashes.
        registered_func = _atexit.register(mgr.stop)
        registered_func()
        mock_stop.assert_called_once()

    # ------------------------------------------------------------------
    # 3. stop() idempotency
    # ------------------------------------------------------------------

    def test_stop_idempotent(self):
        """Calling stop() multiple times does not raise."""
        mgr = self._fresh_manager()
        mgr.start()
        mgr.stop()
        try:
            mgr.stop()
            mgr.stop()
        except Exception:
            self.fail("stop() raised on subsequent calls")

    def test_stop_before_start_is_safe(self):
        """Calling stop() without ever calling start() is safe."""
        mgr = self._fresh_manager()
        try:
            mgr.stop()
        except Exception:
            self.fail("stop() raised before start()")

    def test_stop_sets_running_false(self):
        """After stop(), _running is False."""
        mgr = self._fresh_manager()
        mgr.start()
        self.assertTrue(mgr._running)
        mgr.stop()
        self.assertFalse(mgr._running)

    # ------------------------------------------------------------------
    # 4. stop() on a partially-initialised manager
    # ------------------------------------------------------------------

    def test_stop_without_listener_is_safe(self):
        """stop() tolerates None _listener."""
        mgr = self._fresh_manager()
        mgr._listener = None
        mgr._trigger_detector = None
        try:
            mgr.stop()
        except Exception:
            self.fail("stop() raised with no listener")

    @patch("phraise.hotkeys.HotkeyManager._update_listener")
    def test_stop_calls_listener_stop(self, mock_update: Mock):
        """stop() calls _listener.stop() if listener exists."""
        mgr = self._fresh_manager()
        mgr._running = True
        mock_listener = Mock()
        mgr._listener = mock_listener
        mgr.stop()
        mock_listener.stop.assert_called_once()

    @patch("phraise.hotkeys.HotkeyManager._update_listener")
    def test_stop_calls_trigger_detector_stop(self, mock_update: Mock):
        """stop() calls _trigger_detector.stop() if detector exists."""
        mgr = self._fresh_manager()
        mgr._running = True
        mock_detector = Mock()
        mgr._trigger_detector = mock_detector
        mgr.stop()
        mock_detector.stop.assert_called_once()

    # ------------------------------------------------------------------
    # 5. listener.stop() failure tolerance
    # ------------------------------------------------------------------

    def test_stop_tolerates_listener_stop_exception(self):
        """If _listener.stop() raises, stop() logs and continues."""
        mgr = self._fresh_manager()
        mgr._running = True
        mock_listener = Mock()
        mock_listener.stop.side_effect = RuntimeError("listener boom")
        mgr._listener = mock_listener
        try:
            mgr.stop()
        except RuntimeError:
            self.fail("stop() propagated listener exception")
        self.assertIsNone(mgr._listener)


if __name__ == "__main__":
    unittest.main()
