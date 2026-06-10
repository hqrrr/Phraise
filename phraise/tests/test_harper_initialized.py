"""Unit tests for ``build_initialized_notification`` wiring in HarperLspManager.

Verifies the Task 8 startup flow: ``initialize()`` sends only the initialize
request; the ``initialized`` notification is deferred until the stdout reader
receives the server's ``initialize`` response via ``_decode_frames``.

Notification format (no ``id`` field) is tested in ``test_harper_types.py``
(``TestBuildInitializedNotification``) — this test focuses on the wiring.
"""

import json
import unittest
from unittest.mock import MagicMock, patch

from phraise.harper_lsp_manager import HarperLspManager
from phraise.harper_utils import get_harper_binary_path


def _binary_path() -> str:
    """Return the expected harper-ls binary path for test assertions."""
    from pathlib import Path
    path = get_harper_binary_path()
    if path is not None:
        return str(path)
    return str(Path("phraise") / "lsp" / "harper-ls.exe")


def _make_frame(body: dict) -> bytes:
    """Encode a JSON-RPC message as Content-Length framed bytes."""
    raw = json.dumps(body, ensure_ascii=False).encode("utf-8")
    header = f"Content-Length: {len(raw)}\r\n\r\n".encode("ascii")
    return header + raw


def _make_initialize_response(request_id: int = 1) -> dict:
    """Build a minimal ``initialize`` response from the server."""
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "result": {
            "capabilities": {
                "textDocumentSync": 1,
                "codeActionProvider": True,
            },
            "serverInfo": {"name": "harper-ls", "version": "0.1.0"},
        },
    }


def _extract_body(written: bytes) -> dict:
    """Extract JSON-RPC body from Content-Length framed bytes."""
    _, _, body = written.partition(b"\r\n\r\n")
    return json.loads(body.decode("utf-8"))


class TestInitializeSendsInitializedNotification(unittest.TestCase):
    """Task 8: ``initialize()`` sends only the initialize request.
    The ``initialized`` notification is deferred to the response handler."""

    def setUp(self):
        self._qproc_patcher = patch("phraise.harper_lsp_manager.QProcess")
        self._qtimer_patcher = patch("phraise.harper_lsp_manager.QTimer")
        self.mock_qproc_cls = self._qproc_patcher.start()
        self.mock_qtimer_cls = self._qtimer_patcher.start()

        self.mock_proc = MagicMock()
        self.mock_proc.readAllStandardOutput.return_value = b""
        self.mock_proc.state.return_value = 0
        self.mock_qproc_cls.return_value = self.mock_proc

        self.mock_timer = MagicMock()
        self.mock_qtimer_cls.return_value = self.mock_timer

        self.binary = _binary_path()
        self.manager = HarperLspManager(self.binary, "American", {}, 30)

    def tearDown(self):
        self._qproc_patcher.stop()
        self._qtimer_patcher.stop()

    def _get_stdout_slot(self):
        """Return the slot connected to readyReadStandardOutput."""
        calls = self.mock_proc.readyReadStandardOutput.connect.call_args_list
        self.assertGreater(len(calls), 0)
        return calls[0][0][0]

    # ------------------------------------------------------------------
    # Updated tests for Task 8 deferred-initialized flow
    # ------------------------------------------------------------------

    def test_initialize_writes_one_message(self):
        """initialize() should write exactly 1 message: the request only.
        The initialized notification is deferred (Task 8)."""
        self.manager.start()
        self.manager.initialize()

        self.assertEqual(self.mock_proc.write.call_count, 1)

    def test_initialized_sent_on_response(self):
        """When the stdout reader receives the initialize response,
        the initialized notification is sent."""
        self.manager.start()
        self.manager.initialize()

        # Verify only initialize was sent so far
        first_write: bytes = self.mock_proc.write.call_args_list[0][0][0]
        first_body = _extract_body(first_write)
        self.assertEqual(first_body["method"], "initialize")

        # Now simulate receiving the initialize response
        self.mock_proc.write.reset_mock()
        stdout_slot = self._get_stdout_slot()
        self.mock_proc.readAllStandardOutput.return_value = _make_frame(
            _make_initialize_response(request_id=1)
        )
        stdout_slot()

        # Verify initialized notification was now sent
        self.assertEqual(self.mock_proc.write.call_count, 1)
        second_write: bytes = self.mock_proc.write.call_args_list[0][0][0]
        second_body = _extract_body(second_write)
        self.assertEqual(second_body["method"], "initialized")
        self.assertEqual(second_body["params"], {})
        self.assertNotIn("id", second_body)

    def test_notification_has_no_id_field(self):
        """The initialized notification (sent on response) has no ``id`` field."""
        self.manager.start()
        self.manager.initialize()

        # Simulate receiving the initialize response
        stdout_slot = self._get_stdout_slot()
        self.mock_proc.readAllStandardOutput.return_value = _make_frame(
            _make_initialize_response(request_id=1)
        )
        stdout_slot()

        written: bytes = self.mock_proc.write.call_args_list[-1][0][0]
        payload = _extract_body(written)

        self.assertEqual(payload["method"], "initialized")
        self.assertNotIn("id", payload,
                         "Notifications must not carry an 'id' field")


class TestInitializeSendsRequestBeforeNotification(unittest.TestCase):
    """The ``initialize`` request must be sent BEFORE the ``initialized``
    notification (LSP protocol ordering).  Task 8: the initialized
    notification is deferred until the server response."""

    def setUp(self):
        self._qproc_patcher = patch("phraise.harper_lsp_manager.QProcess")
        self._qtimer_patcher = patch("phraise.harper_lsp_manager.QTimer")
        self.mock_qproc_cls = self._qproc_patcher.start()
        self.mock_qtimer_cls = self._qtimer_patcher.start()

        self.mock_proc = MagicMock()
        self.mock_proc.readAllStandardOutput.return_value = b""
        self.mock_proc.state.return_value = 0
        self.mock_qproc_cls.return_value = self.mock_proc

        self.mock_timer = MagicMock()
        self.mock_qtimer_cls.return_value = self.mock_timer

        self.binary = _binary_path()
        self.manager = HarperLspManager(self.binary, "American", {}, 30)

    def tearDown(self):
        self._qproc_patcher.stop()
        self._qtimer_patcher.stop()

    def _get_stdout_slot(self):
        calls = self.mock_proc.readyReadStandardOutput.connect.call_args_list
        self.assertGreater(len(calls), 0)
        return calls[0][0][0]

    def test_request_before_notification(self):
        """Initialize request sent first; initialized notification follows
        only after the server responds."""
        self.manager.start()
        self.manager.initialize()

        calls = self.mock_proc.write.call_args_list
        self.assertGreaterEqual(len(calls), 1)

        # First write: initialize request
        first_body = _extract_body(calls[0][0][0])
        self.assertEqual(first_body["method"], "initialize")
        self.assertIn("id", first_body)

        # No initialized notification yet
        for call_args in calls[1:]:
            body = _extract_body(call_args[0][0])
            self.assertNotEqual(body.get("method"), "initialized",
                                "initialized must not be sent before response")

        # Simulate receiving the initialize response
        stdout_slot = self._get_stdout_slot()
        self.mock_proc.readAllStandardOutput.return_value = _make_frame(
            _make_initialize_response(request_id=1)
        )
        stdout_slot()

        # Now the initialized notification should be the last write
        all_calls = self.mock_proc.write.call_args_list
        self.assertGreaterEqual(len(all_calls), 2,
                                "Should have at least initialize + initialized")

        last_body = _extract_body(all_calls[-1][0][0])
        self.assertEqual(last_body["method"], "initialized")
        self.assertNotIn("id", last_body)


if __name__ == "__main__":
    unittest.main()
