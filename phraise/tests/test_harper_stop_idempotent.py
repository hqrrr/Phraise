# PhrAIse - AI writing assistant
# License: GNU GPLv3
# GitHub: https://github.com/hqrrr/Phraise
# Author: hqrrr
#
# Description: Unit tests for harper stop idempotent.
"""Tests that HarperLspManager.stop() is idempotent.

Calling ``stop()`` twice must not raise ``RuntimeError`` from duplicate
Qt signal disconnections.  See Task 9.
"""

import unittest
from unittest.mock import MagicMock, patch

from phraise.harper_lsp_manager import HarperLspManager


def _make_disconnect_that_raises_on_repeat() -> MagicMock:
    """Return a mock ``Signal`` whose ``disconnect()`` raises on second call.

    On the first call the disconnection succeeds; on every subsequent
    call it raises ``RuntimeError``, simulating PySide6 behaviour when
    a signal is already disconnected.
    """
    call_count = [0]

    def _side_effect(*_args, **_kwargs):
        call_count[0] += 1
        if call_count[0] > 1:
            msg = "disconnect() called twice on mocked signal"
            raise RuntimeError(msg)

    mock_signal = MagicMock()
    mock_signal.disconnect.side_effect = _side_effect
    return mock_signal


class TestHarperStopIdempotent(unittest.TestCase):
    """Verify that ``stop()`` can be safely called multiple times."""

    def setUp(self):
        patcher_proc = patch("phraise.harper_lsp_manager.QProcess")
        patcher_timer = patch("phraise.harper_lsp_manager.QTimer")
        self.mock_qprocess_cls = patcher_proc.start()
        self.mock_qtimer_cls = patcher_timer.start()
        self.addCleanup(patcher_proc.stop)
        self.addCleanup(patcher_timer.stop)

        # Create a mock QProcess instance whose signals fail on repeat
        # disconnect
        self.mock_process = MagicMock()
        self.mock_process.started = _make_disconnect_that_raises_on_repeat()
        self.mock_process.errorOccurred = _make_disconnect_that_raises_on_repeat()
        self.mock_process.finished = _make_disconnect_that_raises_on_repeat()
        self.mock_process.readyReadStandardOutput = (
            _make_disconnect_that_raises_on_repeat()
        )
        # Make the process look already-running so terminate() is exercised
        self.mock_process.state.return_value = 2  # QProcess.Running

        self.mock_qprocess_cls.return_value = self.mock_process

        # Mock timer
        self.mock_timer = MagicMock()
        self.mock_qtimer_cls.return_value = self.mock_timer

        self.manager = HarperLspManager("harper-ls.exe", "American", {}, 30)

    # ------------------------------------------------------------------
    # 1. Double stop() must not raise
    # ------------------------------------------------------------------

    def test_double_stop_does_not_raise(self):
        """Calling stop() twice must not raise RuntimeError."""
        # First call — signals are "connected", disconnect succeeds
        try:
            self.manager.stop()
        except Exception as e:
            self.fail(f"First stop() raised {type(e).__name__}: {e}")

        # Second call — signals already "disconnected" → would raise
        # RuntimeError without the idempotency guard.
        try:
            self.manager.stop()
        except Exception as e:
            self.fail(f"Second stop() raised {type(e).__name__}: {e}")

    # ------------------------------------------------------------------
    # 2. Triple call for good measure
    # ------------------------------------------------------------------

    def test_triple_stop_does_not_raise(self):
        """Calling stop() three times must also be safe."""
        for i in range(3):
            try:
                self.manager.stop()
            except Exception as e:
                self.fail(f"stop() call #{i + 1} raised {type(e).__name__}: {e}")

    # ------------------------------------------------------------------
    # 3. Timeout timer is stopped on every call
    # ------------------------------------------------------------------

    def test_timeout_timer_stopped_on_each_call(self):
        """stop() must call _timeout_timer.stop() each time."""
        self.manager.stop()
        self.assertEqual(self.mock_timer.stop.call_count, 1)
        self.manager.stop()
        self.assertGreaterEqual(
            self.mock_timer.stop.call_count, 2,
            "stop() did not stop _timeout_timer on second call",
        )


if __name__ == "__main__":
    unittest.main()
