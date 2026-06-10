"""TDD tests for lock-held callback optimization in DoubleTapDetector.

Verifies that self._lock is released before calling _callback() and
re-acquired after, allowing key release events to be processed during
the ~200ms callback window.

Tests cover:
- Lock released during callback (no deadlock on concurrent _on_release)
- _callback_running flag prevents re-entrant triggers
- Exception in callback doesn't leave corrupt state
- Normal operation after callback completes
- Timer timeout behavior during callback
"""

import threading
import time
import unittest
from unittest.mock import Mock

from phraise.hotkeys import DoubleTapDetector


# ====================================================================
# Helpers
# ====================================================================

def mock_key(name: str) -> Mock:
    """Create a mock pynput key object."""
    m = Mock()
    m.name = name
    m.char = name if len(name) == 1 else None
    return m


# ====================================================================
# 1. Lock Released During Callback
# ====================================================================

class TestLockReleasedDuringCallback(unittest.TestCase):
    """Verify the lock is released before callback execution."""

    def test_release_during_callback_no_deadlock(self):
        """Calling _on_release from within callback succeeds (no deadlock).

        If the lock were still held during callback, _on_release would
        deadlock trying to acquire it. This test proves the lock is released.
        """
        def callback():
            # Release Ctrl during callback — must not deadlock
            detector._on_release(mock_key("ctrl"))

        cb_mock = Mock(side_effect=callback)
        detector = DoubleTapDetector(
            modifiers=("ctrl",), trigger_key="c", callback=cb_mock
        )

        detector._on_press(mock_key("ctrl"))
        detector._on_press(mock_key("c"))   # 1st tap
        detector._on_press(mock_key("c"))   # 2nd tap → fires callback

        cb_mock.assert_called_once()
        self.assertEqual(detector._state, "IDLE")

    def test_release_during_callback_from_another_thread(self):
        """Concurrent _on_release during callback does not deadlock.

        Callback waits on an event; test thread calls _on_release concurrently.
        """
        callback_started = threading.Event()
        allow_callback_return = threading.Event()

        def callback():
            callback_started.set()
            allow_callback_return.wait(timeout=2.0)

        detector = DoubleTapDetector(
            modifiers=("ctrl",), trigger_key="c", callback=callback
        )
        detector._on_press(mock_key("ctrl"))
        detector._on_press(mock_key("c"))  # 1st tap

        def trigger():
            detector._on_press(mock_key("c"))  # 2nd tap → fires callback

        t = threading.Thread(target=trigger)
        t.start()
        self.assertTrue(callback_started.wait(timeout=2.0),
                        "Callback should have started")

        # Release modifier from test thread — should NOT deadlock
        detector._on_release(mock_key("ctrl"))

        allow_callback_return.set()
        t.join(timeout=2.0)
        self.assertEqual(detector._state, "IDLE")

    def test_state_resets_when_modifier_released_during_callback(self):
        """Ctrl released during callback → state becomes IDLE."""
        def callback():
            detector._on_release(mock_key("ctrl"))

        cb_mock = Mock(side_effect=callback)
        detector = DoubleTapDetector(
            modifiers=("ctrl",), trigger_key="c", callback=cb_mock
        )

        detector._on_press(mock_key("ctrl"))
        detector._on_press(mock_key("c"))
        detector._on_press(mock_key("c"))  # fires callback

        self.assertEqual(detector._state, "IDLE")
        self.assertEqual(detector._held_modifiers, set())

    def test_multiple_modifiers_released_during_callback(self):
        """Both Ctrl and Shift released during callback → state resets."""
        def callback():
            detector._on_release(mock_key("ctrl"))
            detector._on_release(mock_key("shift"))

        cb_mock = Mock(side_effect=callback)
        detector = DoubleTapDetector(
            modifiers=("ctrl", "shift"), trigger_key="a", callback=cb_mock
        )

        detector._on_press(mock_key("ctrl"))
        detector._on_press(mock_key("shift"))
        detector._on_press(mock_key("a"))
        detector._on_press(mock_key("a"))  # fires callback

        self.assertEqual(detector._state, "IDLE")
        self.assertEqual(detector._held_modifiers, set())

    def test_non_modifier_release_during_callback_noop(self):
        """Releasing a non-modifier key during callback is harmless."""
        def callback():
            detector._on_release(mock_key("x"))  # not a modifier
            detector._on_release(mock_key("c"))  # trigger key but not a modifier

        cb_mock = Mock(side_effect=callback)
        detector = DoubleTapDetector(
            modifiers=("ctrl",), trigger_key="c", callback=cb_mock
        )

        detector._on_press(mock_key("ctrl"))
        detector._on_press(mock_key("c"))
        detector._on_press(mock_key("c"))  # fires callback

        cb_mock.assert_called_once()
        # State should still be MODIFIERS_HELD since no modifier was released
        self.assertEqual(detector._state, "MODIFIERS_HELD")


# ====================================================================
# 2. Re-entrant Trigger Prevention
# ====================================================================

class TestReentrantPrevention(unittest.TestCase):
    """Verify _callback_running flag prevents re-entrant triggers."""

    def test_second_trigger_blocked_during_callback(self):
        """Double-tapping again during callback does not fire a second time."""
        call_count = 0

        def callback():
            nonlocal call_count
            call_count += 1
            # Try another trigger during callback
            detector._on_press(mock_key("c"))  # should be blocked
            detector._on_press(mock_key("c"))  # should be blocked

        cb_mock = Mock(side_effect=callback)
        detector = DoubleTapDetector(
            modifiers=("ctrl",), trigger_key="c", callback=cb_mock
        )

        detector._on_press(mock_key("ctrl"))
        detector._on_press(mock_key("c"))
        detector._on_press(mock_key("c"))  # fires callback (once)

        self.assertEqual(cb_mock.call_count, 1)
        self.assertEqual(call_count, 1)

    def test_full_double_tap_blocked_during_callback(self):
        """Complete Ctrl+C+C sequence during callback is blocked."""
        call_count = 0

        def callback():
            nonlocal call_count
            call_count += 1
            # Full double-tap sequence during callback
            detector._on_press(mock_key("ctrl"))
            detector._on_press(mock_key("c"))
            detector._on_press(mock_key("c"))  # would fire but blocked

        cb_mock = Mock(side_effect=callback)
        detector = DoubleTapDetector(
            modifiers=("ctrl",), trigger_key="c", callback=cb_mock
        )

        detector._on_press(mock_key("ctrl"))
        detector._on_press(mock_key("c"))
        detector._on_press(mock_key("c"))  # fires callback

        self.assertEqual(cb_mock.call_count, 1)
        self.assertEqual(call_count, 1)

    def test_normal_triggers_work_after_callback_completes(self):
        """After callback finishes, new double-tap triggers normally."""
        def callback():
            pass  # quick callback

        cb_mock = Mock(side_effect=callback)
        detector = DoubleTapDetector(
            modifiers=("ctrl",), trigger_key="c", callback=cb_mock
        )

        # First trigger
        detector._on_press(mock_key("ctrl"))
        detector._on_press(mock_key("c"))
        detector._on_press(mock_key("c"))  # fires callback #1
        detector._on_release(mock_key("ctrl"))

        self.assertEqual(cb_mock.call_count, 1)

        # Second trigger (after callback completed, new modifier press)
        detector._on_press(mock_key("ctrl"))
        detector._on_press(mock_key("c"))
        detector._on_press(mock_key("c"))  # fires callback #2
        detector._on_release(mock_key("ctrl"))

        self.assertEqual(cb_mock.call_count, 2)


# ====================================================================
# 3. Exception Safety
# ====================================================================

class TestCallbackExceptionSafety(unittest.TestCase):
    """Verify exception in callback doesn't corrupt state or deadlock."""

    def test_exception_in_callback_clears_flag(self):
        """_callback_running is reset to False even if callback raises."""
        def callback():
            raise ValueError("simulated callback error")

        detector = DoubleTapDetector(
            modifiers=("ctrl",), trigger_key="c", callback=callback
        )

        detector._on_press(mock_key("ctrl"))
        detector._on_press(mock_key("c"))
        detector._on_press(mock_key("c"))  # callback raises

        # Flag must be cleared
        self.assertFalse(detector._callback_running)

        # New trigger must work after exception
        cb_mock = Mock()
        detector._callback = cb_mock
        detector._on_press(mock_key("ctrl"))
        detector._on_press(mock_key("c"))
        detector._on_press(mock_key("c"))  # should work now

        cb_mock.assert_called_once()

    def test_exception_in_callback_does_not_deadlock(self):
        """Callback raises → lock is properly released, state remains safe."""
        def callback():
            raise RuntimeError("boom")

        detector = DoubleTapDetector(
            modifiers=("ctrl",), trigger_key="c", callback=callback
        )

        detector._on_press(mock_key("ctrl"))
        detector._on_press(mock_key("c"))
        detector._on_press(mock_key("c"))  # callback raises, lock re-acquired

        # State should still be valid
        self.assertEqual(detector._state, "MODIFIERS_HELD")
        self.assertFalse(detector._callback_running)

        # Lock should be released after _on_press returns (no leak)
        # Verify by calling _on_release — must not deadlock
        detector._on_release(mock_key("ctrl"))
        self.assertEqual(detector._state, "IDLE")


# ====================================================================
# 4. State Integrity
# ====================================================================

class TestStateIntegrity(unittest.TestCase):
    """Verify state machine correctness with lock release optimization."""

    def test_callback_running_flag_initial_state(self):
        """_callback_running starts False."""
        detector = DoubleTapDetector(
            modifiers=("ctrl",), trigger_key="c",
            callback=lambda: None, timeout=0.5,
        )
        self.assertFalse(detector._callback_running)

    def test_callback_running_false_after_normal_trigger(self):
        """After normal trigger completes, _callback_running is False."""
        cb_mock = Mock()
        detector = DoubleTapDetector(
            modifiers=("ctrl",), trigger_key="c", callback=cb_mock
        )

        detector._on_press(mock_key("ctrl"))
        detector._on_press(mock_key("c"))
        detector._on_press(mock_key("c"))

        cb_mock.assert_called_once()
        self.assertFalse(detector._callback_running)

    def test_still_works_after_stop_and_restart(self):
        """Stop/restart cycle with lock release works correctly."""
        cb_mock = Mock()
        detector = DoubleTapDetector(
            modifiers=("ctrl",), trigger_key="c", callback=cb_mock
        )

        detector._on_press(mock_key("ctrl"))
        detector._on_press(mock_key("c"))
        detector._on_press(mock_key("c"))
        cb_mock.assert_called_once()

        detector.stop()
        detector._on_press(mock_key("ctrl"))
        detector._on_press(mock_key("c"))
        detector._on_press(mock_key("c"))
        self.assertEqual(cb_mock.call_count, 1)  # no new calls during stop

        # Simulate start resets running flag
        detector._running = True
        detector._on_press(mock_key("ctrl"))
        detector._on_press(mock_key("c"))
        detector._on_press(mock_key("c"))
        self.assertEqual(cb_mock.call_count, 2)


# ====================================================================
# 5. Timing Edge Cases
# ====================================================================

class TestTimingEdgeCases(unittest.TestCase):
    """Edge cases involving timers and concurrent events."""

    def test_rapid_trigger_after_callback_no_double_fire(self):
        """Extremely fast re-trigger after callback should not double-fire."""
        call_count = 0

        def callback():
            nonlocal call_count
            call_count += 1

        cb_mock = Mock(side_effect=callback)
        detector = DoubleTapDetector(
            modifiers=("ctrl",), trigger_key="c",
            callback=cb_mock, timeout=0.5,
        )

        # Press and hold Ctrl
        detector._on_press(mock_key("ctrl"))
        # Rapid C taps
        detector._on_press(mock_key("c"))  # 1st tap
        detector._on_press(mock_key("c"))  # 2nd tap → fires callback
        # During callback (blocked by _callback_running), more taps
        # These happen after callback returns because _on_press is synchronous
        detector._on_press(mock_key("c"))  # new 1st tap (after callback)
        detector._on_press(mock_key("c"))  # 2nd tap → fires callback #2

        self.assertEqual(cb_mock.call_count, 2)
        self.assertEqual(call_count, 2)

    def test_timeout_elapses_during_next_trigger(self):
        """Timer expiry does not interfere with lock release pattern."""
        cb_mock = Mock()
        detector = DoubleTapDetector(
            modifiers=("ctrl",), trigger_key="c",
            callback=cb_mock, timeout=0.1,
        )

        detector._on_press(mock_key("ctrl"))
        detector._on_press(mock_key("c"))  # 1st tap, timer starts
        time.sleep(0.15)  # timer expires → state goes back to MODIFIERS_HELD
        detector._on_press(mock_key("c"))  # new 1st tap
        detector._on_press(mock_key("c"))  # 2nd tap → fires callback

        cb_mock.assert_called_once()

    def test_release_all_modifiers_between_taps_then_repress(self):
        """Release Ctrl between taps, re-press, should not trigger."""
        detector = DoubleTapDetector(
            modifiers=("ctrl",), trigger_key="c",
            callback=Mock(),
        )

        detector._on_press(mock_key("ctrl"))
        detector._on_press(mock_key("c"))   # 1st tap
        detector._on_release(mock_key("ctrl"))   # release → reset
        detector._on_press(mock_key("ctrl"))      # re-press
        detector._on_press(mock_key("c"))         # new 1st tap
        detector._on_press(mock_key("c"))         # 2nd tap → fires
        detector._on_release(mock_key("ctrl"))

        detector._callback.assert_called_once()


# ====================================================================
# Main
# ====================================================================

if __name__ == "__main__":
    unittest.main()
