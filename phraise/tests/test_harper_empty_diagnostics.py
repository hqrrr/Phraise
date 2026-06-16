# PhrAIse - AI writing assistant
# License: GNU GPLv3
# GitHub: https://github.com/hqrrr/Phraise
# Author: hqrrr
#
# Description: Unit tests for harper empty diagnostics.
"""Regression test: empty diagnostics from Harper LSP server.

``HarperLspManager._decode_frames`` currently guards emission of
``diagnostics_ready`` with ``if diags:`` (line 260), which skips empty
diagnostic lists.  This prevents ``HarperClient.finished`` from ever firing
when the text is clean, leaving the UI in a loading state.

Test 1 — RED (demonstrates the bug)::
    ``test_empty_diagnostics_stalls_pipeline``
    Asserts ``diagnostics_ready`` fires for ``[]`` — fails because the
    ``if diags:`` guard drops the emission entirely.

Test 2 — expected behaviour after the fix::
    ``test_empty_diagnostics_client_finishes``
    Asserts ``HarperClient.finished`` fires with ``success=True`` and
    ``corrected_text`` == original text when diagnostics are empty.
"""

from __future__ import annotations

import json
import unittest
from unittest.mock import MagicMock, patch

from phraise.harper_client import HarperClient
from phraise.harper_lsp_manager import HarperLspManager


# ---------------------------------------------------------------------------
# Frame builders
# ---------------------------------------------------------------------------

def _make_frame(body: dict) -> bytes:
    """Encode a JSON-RPC message as Content-Length framed bytes."""
    raw = json.dumps(body, ensure_ascii=False).encode("utf-8")
    header = f"Content-Length: {len(raw)}\r\n\r\n".encode("ascii")
    return header + raw


def _empty_diagnostics_frame(uri: str = "file:///test.txt") -> bytes:
    """``textDocument/publishDiagnostics`` notification with no diagnostics."""
    return _make_frame({
        "jsonrpc": "2.0",
        "method": "textDocument/publishDiagnostics",
        "params": {"uri": uri, "diagnostics": []},
    })


def _initialize_response_frame(request_id: int = 1) -> bytes:
    """Minimal LSP ``initialize`` result from the server."""
    return _make_frame({
        "jsonrpc": "2.0",
        "id": request_id,
        "result": {"capabilities": {}},
    })


# ===================================================================
# Test 1 — Manager-level signal (RED — demonstrates the bug)
# ===================================================================

class TestEmptyDiagnosticsManager(unittest.TestCase):
    """``_decode_frames`` must emit ``diagnostics_ready`` even for ``[]``.

    The current production code has ``if diags:`` on line 260 which skips
    emission when the diagnostics list is empty.  This test asserts the
    correct behaviour (emission on empty), so it **FAILS** with the bug in
    place — standard TDD red phase.
    """

    def setUp(self):
        self._qproc = patch("phraise.harper_lsp_manager.QProcess")
        self._qtimer = patch("phraise.harper_lsp_manager.QTimer")
        self.mock_qproc_cls = self._qproc.start()
        self.mock_qtimer_cls = self._qtimer.start()

        self.mock_proc = MagicMock()
        self.mock_proc.readAllStandardOutput.return_value = b""
        self.mock_qproc_cls.return_value = self.mock_proc

        self.mock_timer = MagicMock()
        self.mock_qtimer_cls.return_value = self.mock_timer

        self.manager = HarperLspManager("fake-binary.exe", "American", {}, 30)

    def tearDown(self):
        self._qproc.stop()
        self._qtimer.stop()

    def test_empty_diagnostics_stalls_pipeline(self):
        """``diagnostics_ready`` MUST fire for ``[]`` (currently FAILS)."""
        events: list = []
        self.manager.diagnostics_ready.connect(events.append)
        self.manager.error_occurred.connect(lambda _: None)
        self.manager.process_finished.connect(lambda _: None)
        self.manager.server_ready.connect(lambda: None)

        self.manager._buffer += _empty_diagnostics_frame()
        self.manager._decode_frames()

        # This assertion FAILS because ``if diags:`` on line 260 skips
        # emission when ``diags == []``.  Removing the guard in production
        # code makes this test pass.
        self.assertEqual(
            len(events), 1,
            "diagnostics_ready should emit even for an empty diagnostics list; "
            "the current `if diags:` guard suppresses this.",
        )
        self.assertEqual(events[0], [])


# ===================================================================
# Test 2 — Client-level signal (expected behaviour after the fix)
# ===================================================================

class TestEmptyDiagnosticsClient(unittest.TestCase):
    """``HarperClient.finished`` must fire for clean text.

    After the production fix (removing the ``if diags:`` guard),
    an empty ``publishDiagnostics`` notification must trigger
    ``finished`` with ``success=True`` and no issues.
    """

    def setUp(self):
        self._mgr_qproc = patch("phraise.harper_lsp_manager.QProcess")
        self._mgr_qtimer = patch("phraise.harper_lsp_manager.QTimer")
        self._cl_qtimer = patch("phraise.harper_client.QTimer")
        self._bin_path = patch(
            "phraise.harper_client.get_harper_binary_path",
            return_value="/fake/harper-ls",
        )

        self.mock_mgr_qproc_cls = self._mgr_qproc.start()
        self.mock_mgr_qtimer_cls = self._mgr_qtimer.start()
        self.mock_cl_qtimer_cls = self._cl_qtimer.start()
        self._bin_path.start()

        self.mock_proc = MagicMock()
        self.mock_proc.readAllStandardOutput.return_value = b""
        self.mock_proc.state.return_value = 2  # QProcess.Running
        self.mock_mgr_qproc_cls.return_value = self.mock_proc

        self.mock_mgr_timer = MagicMock()
        self.mock_mgr_qtimer_cls.return_value = self.mock_mgr_timer

        self.mock_client_timer = MagicMock()
        self.mock_cl_qtimer_cls.return_value = self.mock_client_timer

    def tearDown(self):
        self._mgr_qproc.stop()
        self._mgr_qtimer.stop()
        self._cl_qtimer.stop()
        self._bin_path.stop()

    def test_empty_diagnostics_client_finishes(self):
        """``finished`` fires ``success=True`` for clean text."""
        client = HarperClient()
        emitted: list = []
        client.finished.connect(emitted.append)

        issues, text = client.check_text("hello")
        self.assertEqual(issues, [])
        self.assertEqual(text, "hello")

        # Simulate what _on_process_started does: bump IDs and send
        # the initialize request (already handled via mocked process).
        client._manager._request_id = 1
        client._manager._initialize_request_id = 1

        # Feed the initialize response → server_ready → send_text("hello")
        client._manager._buffer += _initialize_response_frame(request_id=1)
        client._manager._decode_frames()
        # server_ready fired, send_text wrote the didOpen notification,
        # _pending_request is True.  Stop the (mocked) timeout timer.
        client._manager._timeout_timer.stop()

        # Feed the empty diagnostics notification
        client._manager._buffer += _empty_diagnostics_frame()
        client._manager._decode_frames()

        # The bug: diagnostics_ready is never emitted, so _on_diagnostics
        # never fires, and finished is never emitted → this assertion
        # FAILS.  After the fix it should PASS.
        self.assertEqual(len(emitted), 1)
        self.assertTrue(emitted[0].success)
        self.assertEqual(emitted[0].issues, [])
        self.assertEqual(emitted[0].corrected_text, "hello")
        self.assertEqual(emitted[0].error, "")


if __name__ == "__main__":
    unittest.main()
