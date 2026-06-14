"""TDD tests for HarperLspManager — QProcess-based LSP lifecycle manager.

These tests import from ``phraise.harper_lsp_manager``, which does NOT yet
exist.  This is intentional — the RED phase of TDD.

Expected failures at this stage:
    ImportError: cannot import name 'HarperLspManager'
    (followed by ``self.fail()`` in each test)

Once the implementation exists (Task 6), the assertions below define the
interface contract that must be satisfied.
"""

import json
import unittest
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

from phraise.harper_types import (
    LspPosition,
    LspRange,
    LspTextEdit,
    build_did_open_notification,
    build_initialize_request,
)
from phraise.harper_utils import get_harper_binary_path

# ---------------------------------------------------------------------------
# Imports that WILL fail in the RED phase — that is expected.
# ---------------------------------------------------------------------------
try:
    from phraise.harper_lsp_manager import HarperLspManager
except ImportError:
    # RED phase — stub so the test module itself is importable.
    HarperLspManager = None  # type: ignore[assignment]


def _binary_path() -> str:
    """Return the expected harper-ls binary path for test assertions."""
    path = get_harper_binary_path()
    if path is not None:
        return str(path)
    return str(Path("phraise") / "lsp" / "harper-ls.exe")


class TestHarperLspManager(unittest.TestCase):
    """RED-phase tests for HarperLspManager — QProcess-based LSP manager.

    All tests FAIL because the class does not exist yet.
    Once implemented (Task 6), these tests should PASS.
    """

    # ------------------------------------------------------------------
    # 1. Start launches QProcess
    # ------------------------------------------------------------------
    def test_start_launches_process(self):
        """start() launches QProcess with correct binary path and --stdio."""
        if HarperLspManager is None:
            self.fail("HarperLspManager not importable (RED phase)")

        with patch("phraise.harper_lsp_manager.QProcess") as mock_qproc_cls:
            mock_proc = MagicMock()
            mock_qproc_cls.return_value = mock_proc

            binary = _binary_path()
            manager = HarperLspManager(binary, "American", {}, 30)
            manager.start()

            mock_proc.start.assert_called_once_with(binary, ["--stdio"])

    # ------------------------------------------------------------------
    # 2. Initialize sends correct JSON
    # ------------------------------------------------------------------
    def test_initialize_sends_correct_json(self):
        """initialize() writes Content-Length-framed initialize request."""
        if HarperLspManager is None:
            self.fail("HarperLspManager not importable (RED phase)")

        with patch("phraise.harper_lsp_manager.QProcess") as mock_qproc_cls:
            mock_proc = MagicMock()
            mock_qproc_cls.return_value = mock_proc

            binary = _binary_path()
            manager = HarperLspManager(binary, "American", {}, 30)
            manager.start()
            manager.initialize()

            written = b"".join(
                c[0][0] for c in mock_proc.write.call_args_list
            )
            # Content-Length framing is used
            self.assertIn(b"Content-Length:", written)
            self.assertIn(b"\r\n\r\n", written)
            # Payload is a valid JSON-RPC 2.0 initialize request with id=1
            self.assertIn(b'"jsonrpc": "2.0"', written)
            self.assertIn(b'"method": "initialize"', written)
            self.assertIn(b'"id": 1', written)

    # ------------------------------------------------------------------
    # 3. Send text dispatches didOpen
    # ------------------------------------------------------------------
    def test_send_text_dispatches_did_open(self):
        """send_text() writes a didOpen notification with the given text."""
        if HarperLspManager is None:
            self.fail("HarperLspManager not importable (RED phase)")

        with patch("phraise.harper_lsp_manager.QProcess") as mock_qproc_cls:
            mock_proc = MagicMock()
            mock_qproc_cls.return_value = mock_proc
            # send_text() guards against non-Running process state
            mock_proc.state.return_value = 2  # QProcess.Running
            mock_qproc_cls.Running = 2
            mock_qproc_cls.NotRunning = 0
            mock_qproc_cls.Starting = 1

            binary = _binary_path()
            manager = HarperLspManager(binary, "American", {}, 30)
            manager.start()
            manager.send_text("hello world")

            written = b"".join(
                c[0][0] for c in mock_proc.write.call_args_list
            )
            self.assertIn(b"textDocument/didOpen", written)
            self.assertIn(b'"text": "hello world"', written)
            self.assertIn(b'"languageId": "plaintext"', written)

    # ------------------------------------------------------------------
    # 4. Stop terminates process
    # ------------------------------------------------------------------
    def test_stop_terminates_process(self):
        """stop() terminates QProcess and waits for it to finish."""
        if HarperLspManager is None:
            self.fail("HarperLspManager not importable (RED phase)")

        with patch("phraise.harper_lsp_manager.QProcess") as mock_qproc_cls:
            mock_proc = MagicMock()
            mock_qproc_cls.return_value = mock_proc

            binary = _binary_path()
            manager = HarperLspManager(binary, "American", {}, 30)
            manager.start()
            manager.stop()

            mock_proc.terminate.assert_called_once()
            mock_proc.waitForFinished.assert_called_once()

    # ------------------------------------------------------------------
    # 5. Process crash emits error signal
    # ------------------------------------------------------------------
    def test_process_crash_emits_error_signal(self):
        """QProcess errorOccurred(Crashed) → manager emits error_occurred."""
        if HarperLspManager is None:
            self.fail("HarperLspManager not importable (RED phase)")

        with patch("phraise.harper_lsp_manager.QProcess") as mock_qproc_cls:
            mock_proc = MagicMock()
            mock_qproc_cls.return_value = mock_proc

            binary = _binary_path()
            manager = HarperLspManager(binary, "American", {}, 30)
            manager.error_occurred = Mock()
            manager.start()

            # Simulate QProcess crash: invoke the connected slot
            connect_calls = mock_proc.errorOccurred.connect.call_args_list
            self.assertGreater(len(connect_calls), 0)
            error_slot = connect_calls[0][0][0]
            error_slot(1)  # 1 = QProcess.ProcessError.Crashed

            manager.error_occurred.emit.assert_called_once()
            msg = manager.error_occurred.emit.call_args[0][0]
            self.assertIsInstance(msg, str)
            self.assertGreater(len(msg), 0)

    # ------------------------------------------------------------------
    # 6. Process finished emits signal
    # ------------------------------------------------------------------
    def test_process_finished_emits_signal(self):
        """QProcess finished → manager emits process_finished(exit_code)."""
        if HarperLspManager is None:
            self.fail("HarperLspManager not importable (RED phase)")

        with patch("phraise.harper_lsp_manager.QProcess") as mock_qproc_cls:
            mock_proc = MagicMock()
            mock_qproc_cls.return_value = mock_proc

            binary = _binary_path()
            manager = HarperLspManager(binary, "American", {}, 30)
            manager.process_finished = Mock()
            manager.start()

            # Simulate QProcess finished with exit code 0
            connect_calls = mock_proc.finished.connect.call_args_list
            self.assertGreater(len(connect_calls), 0)
            finish_slot = connect_calls[0][0][0]
            finish_slot(0)

            manager.process_finished.emit.assert_called_once_with(0)

    # ------------------------------------------------------------------
    # 7. Response timeout emits error
    # ------------------------------------------------------------------
    def test_response_timeout_emits_error(self):
        """Pending request timeout → error_occurred with descriptive message."""
        if HarperLspManager is None:
            self.fail("HarperLspManager not importable (RED phase)")

        with patch("phraise.harper_lsp_manager.QProcess") as mock_qproc_cls, \
             patch("phraise.harper_lsp_manager.QTimer") as mock_timer_cls:
            mock_proc = MagicMock()
            mock_qproc_cls.return_value = mock_proc
            mock_timer = MagicMock()
            mock_timer_cls.return_value = mock_timer

            binary = _binary_path()
            manager = HarperLspManager(binary, "American", {}, 0.1)
            manager.error_occurred = Mock()
            manager.start()
            manager.send_text("hello world")

            # Trigger the timeout callback (no response arrived)
            mock_timer.timeout.connect.assert_called_once()
            timeout_fn = mock_timer.timeout.connect.call_args[0][0]
            timeout_fn()

            manager.error_occurred.emit.assert_called_once()
            args = manager.error_occurred.emit.call_args[0]
            self.assertIn("timeout", str(args[0]).lower())


# ---------------------------------------------------------------------------
# HarperFixApplier (Task 9 — RED phase)
# ---------------------------------------------------------------------------

try:
    from phraise.harper_types import HarperFixApplier  # noqa: F811
except ImportError:
    # RED phase — stub so the test module itself is importable.
    HarperFixApplier = None  # type: ignore[assignment]


class TestHarperFixApplier(unittest.TestCase):
    """RED-phase tests for ``HarperFixApplier`` — applies grammar fix
    suggestions to original text in REVERSE offset order.

    CRITICAL DESIGN RULE
        Fixes MUST be applied in REVERSE offset order (highest offset first)
        so that earlier offsets are not invalidated by later edits.

    All tests FAIL because the class does not exist yet.
    Once implemented (Task 10), these tests should PASS.
    """

    # ------------------------------------------------------------------
    # Single fix
    # ------------------------------------------------------------------

    def test_apply_single_fix(self):
        """Replace a single word in full."""
        if HarperFixApplier is None:
            self.fail("HarperFixApplier not importable (RED phase)")

        result = HarperFixApplier.apply_single_fix("helo", 0, 4, "hello")
        self.assertEqual(result, "hello")

    # ------------------------------------------------------------------
    # Multiple non-overlapping fixes
    # ------------------------------------------------------------------

    def test_apply_multiple_non_overlapping_fixes(self):
        """Two disjoint fixes applied in reverse-offset order."""
        if HarperFixApplier is None:
            self.fail("HarperFixApplier not importable (RED phase)")

        text = "helo wrld"
        edits = [
            LspTextEdit(
                range=LspRange(LspPosition(0, 0), LspPosition(0, 4)),
                newText="hello",
            ),
            LspTextEdit(
                range=LspRange(LspPosition(0, 5), LspPosition(0, 9)),
                newText="world",
            ),
        ]
        result = HarperFixApplier.apply_fixes(text, edits)
        # Reverse order: offset-5 fix first, then offset-0 fix
        self.assertEqual(result, "hello world")

    # ------------------------------------------------------------------
    # Reverse-order preservation
    # ------------------------------------------------------------------

    def test_reverse_order_preserves_offsets(self):
        """Applying fixes forward would corrupt later offsets — reverse
        order must be used to keep earlier offsets valid."""
        if HarperFixApplier is None:
            self.fail("HarperFixApplier not importable (RED phase)")

        text = "a b c"
        edits = [
            LspTextEdit(
                range=LspRange(LspPosition(0, 0), LspPosition(0, 1)),
                newText="A",
            ),
            LspTextEdit(
                range=LspRange(LspPosition(0, 4), LspPosition(0, 5)),
                newText="C",
            ),
        ]
        result = HarperFixApplier.apply_fixes(text, edits)
        # Offset-4 fix applied before offset-0 fix
        self.assertEqual(result, "A b C")

    # ------------------------------------------------------------------
    # Overlapping fixes — skip contained
    # ------------------------------------------------------------------

    def test_apply_overlapping_fixes(self):
        """When two fixes overlap, the one fully contained within a
        previously applied (higher-offset) fix MUST be skipped.

        "abcdef"  Fix A: (2,4)→"XYZ"   contained inside
                   Fix B: (1,5)→"1234"  containing

        Reverse-order: Fix A (offset 2) processed first, but it is fully
        contained within Fix B (offset 1).  Skip Fix A; only Fix B is
        applied → "a1234f".
        """
        if HarperFixApplier is None:
            self.fail("HarperFixApplier not importable (RED phase)")

        text = "abcdef"
        edits = [
            LspTextEdit(
                range=LspRange(LspPosition(0, 2), LspPosition(0, 4)),
                newText="XYZ",
            ),
            LspTextEdit(
                range=LspRange(LspPosition(0, 1), LspPosition(0, 5)),
                newText="1234",
            ),
        ]
        result = HarperFixApplier.apply_fixes(text, edits)
        self.assertEqual(result, "a1234f")

    # ------------------------------------------------------------------
    # Fix at end of text
    # ------------------------------------------------------------------

    def test_apply_fix_at_end_of_text(self):
        """A fix targeting the last character(s) of the text."""
        if HarperFixApplier is None:
            self.fail("HarperFixApplier not importable (RED phase)")

        text = "hello worl"
        edits = [
            LspTextEdit(
                range=LspRange(LspPosition(0, 9), LspPosition(0, 10)),
                newText="d",
            ),
        ]
        result = HarperFixApplier.apply_fixes(text, edits)
        # Range (9,10) replaces the "l" at position 9 with "d" → "hello word"
        self.assertEqual(result, "hello word")

    # ------------------------------------------------------------------
    # Empty suggestion (skip)
    # ------------------------------------------------------------------

    def test_apply_fix_empty_suggestion(self):
        """A fix whose ``newText`` is empty should be skipped."""
        if HarperFixApplier is None:
            self.fail("HarperFixApplier not importable (RED phase)")

        text = "hello"
        edits = [
            LspTextEdit(
                range=LspRange(LspPosition(0, 0), LspPosition(0, 5)),
                newText="",
            ),
        ]
        result = HarperFixApplier.apply_fixes(text, edits)
        self.assertEqual(result, "hello")

    # ------------------------------------------------------------------
    # No fixes
    # ------------------------------------------------------------------

    def test_apply_no_fixes(self):
        """Empty edit list → identity."""
        if HarperFixApplier is None:
            self.fail("HarperFixApplier not importable (RED phase)")

        text = "hello"
        result = HarperFixApplier.apply_fixes(text, [])
        self.assertEqual(result, "hello")

    # ------------------------------------------------------------------
    # Preserve surrounding text
    # ------------------------------------------------------------------

    def test_apply_fix_preserves_surrounding_text(self):
        """Only the targeted range is replaced; text before and after
        is left intact."""
        if HarperFixApplier is None:
            self.fail("HarperFixApplier not importable (RED phase)")

        text = "the helo word"
        edits = [
            LspTextEdit(
                range=LspRange(LspPosition(0, 4), LspPosition(0, 8)),
                newText="hello",
            ),
        ]
        result = HarperFixApplier.apply_fixes(text, edits)
        self.assertEqual(result, "the hello word")


# ---------------------------------------------------------------------------
# HarperClient integration (Task 11)
# ---------------------------------------------------------------------------

try:
    from phraise.harper_client import HarperClient
except ImportError:
    HarperClient = None  # type: ignore[assignment]


class TestHarperClientIntegration(unittest.TestCase):
    """Integration tests for ``HarperClient`` — the unified orchestration
    class that composes the LSP manager, diagnostics parser, and fix applier.
    """

    def test_is_available_returns_false_when_binary_missing(self):
        if HarperClient is None:
            self.fail("HarperClient not importable")
        client = HarperClient()
        with patch("phraise.harper_client.is_harper_available", return_value=False):
            self.assertFalse(client.is_available())

    def test_check_text_returns_error_when_binary_missing(self):
        if HarperClient is None:
            self.fail("HarperClient not importable")
        client = HarperClient()
        with patch("phraise.harper_client.get_harper_binary_path", return_value=None):
            issues, text = client.check_text("hello")
            self.assertEqual(issues, [])
            self.assertEqual(text, "hello")


if __name__ == "__main__":
    unittest.main()
