"""Unit tests for ``build_initialized_notification`` wiring in HarperLspManager.

Verifies that ``initialize()`` sends the ``initialized`` notification
(via ``_write_message``) immediately after the ``initialize`` request.

Notification format (no ``id`` field) is tested in ``test_harper_types.py``
(``TestBuildInitializedNotification``) — this test focuses on the wiring.
"""

import json
import unittest
from unittest.mock import MagicMock, patch, call

from phraise.harper_lsp_manager import HarperLspManager
from phraise.harper_utils import get_harper_binary_path


def _binary_path() -> str:
    """Return the expected harper-ls binary path for test assertions."""
    from pathlib import Path
    path = get_harper_binary_path()
    if path is not None:
        return str(path)
    return str(Path("phraise") / "lsp" / "harper-ls.exe")


class TestInitializeSendsInitializedNotification(unittest.TestCase):
    """``initialize()`` must send both the ``initialize`` request and the
    ``initialized`` notification."""

    def setUp(self):
        patcher = patch("phraise.harper_lsp_manager.QProcess")
        self.mock_qproc_cls = patcher.start()
        self.addCleanup(patcher.stop)

        self.mock_proc = MagicMock()
        self.mock_qproc_cls.return_value = self.mock_proc

        self.binary = _binary_path()
        self.manager = HarperLspManager(self.binary, "American", {}, 30)

    def test_initialize_writes_two_messages(self):
        """initialize() should write exactly 2 messages: request + notification."""
        self.manager.start()
        self.manager.initialize()

        self.assertEqual(self.mock_proc.write.call_count, 2)

    def test_initialize_contains_initialized_notification(self):
        """The second write call should be the ``initialized`` notification."""
        self.manager.start()
        self.manager.initialize()

        # Second write call is the initialized notification
        second_write: bytes = self.mock_proc.write.call_args_list[1][0][0]
        self.assertIn(b"Content-Length:", second_write)
        self.assertIn(b"\r\n\r\n", second_write)

        # Decode and verify payload
        _, _, body = second_write.partition(b"\r\n\r\n")
        payload = json.loads(body.decode("utf-8"))

        self.assertEqual(payload["jsonrpc"], "2.0")
        self.assertEqual(payload["method"], "initialized")
        self.assertEqual(payload["params"], {})
        self.assertNotIn("id", payload)

    def test_notification_has_no_id_field(self):
        """The initialized notification MUST NOT include an ``id`` field."""
        self.manager.start()
        self.manager.initialize()

        second_write: bytes = self.mock_proc.write.call_args_list[1][0][0]
        _, _, body = second_write.partition(b"\r\n\r\n")
        payload = json.loads(body.decode("utf-8"))

        self.assertNotIn("id", payload,
                         "Notifications must not carry an 'id' field")


class TestInitializeSendsRequestBeforeNotification(unittest.TestCase):
    """The ``initialize`` request must be sent BEFORE the ``initialized``
    notification (LSP protocol ordering)."""

    def test_request_before_notification(self):
        with patch("phraise.harper_lsp_manager.QProcess") as mock_qproc_cls:
            mock_proc = MagicMock()
            mock_qproc_cls.return_value = mock_proc

            manager = HarperLspManager(_binary_path(), "American", {}, 30)
            manager.start()
            manager.initialize()

            calls = mock_proc.write.call_args_list
            self.assertGreaterEqual(len(calls), 2)

            # First write: initialize request
            first_body = _extract_body(calls[0][0][0])
            self.assertEqual(first_body["method"], "initialize")
            self.assertIn("id", first_body)

            # Second write: initialized notification
            second_body = _extract_body(calls[1][0][0])
            self.assertEqual(second_body["method"], "initialized")
            self.assertNotIn("id", second_body)


def _extract_body(written: bytes) -> dict:
    """Extract JSON-RPC body from Content-Length framed bytes."""
    _, _, body = written.partition(b"\r\n\r\n")
    return json.loads(body.decode("utf-8"))


if __name__ == "__main__":
    unittest.main()
