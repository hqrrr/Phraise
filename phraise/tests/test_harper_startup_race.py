# PhrAIse - AI writing assistant
# License: GNU GPLv3
# GitHub: https://github.com/hqrrr/Phraise
# Author: hqrrr
#
# Description: Unit tests for harper startup race.
"""Tests for Harper LSP startup race condition fix (Task 8).

Verifies that ``initialize()`` and ``send_text()`` are deferred until
the QProcess ``started`` signal fires, and that the LSP handshake
(initialize → initialized → didOpen) proceeds in correct order via
signal-driven flow — no polling, no busy-wait.
"""

import json
import unittest
from unittest.mock import ANY, MagicMock, Mock, call, patch

from phraise.harper_lsp_manager import HarperLspManager
from phraise.harper_types import (
    build_initialized_notification,
    build_initialize_request,
)


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


def _make_workspace_config_request(request_id: int = 2) -> dict:
    """Build a ``workspace/configuration`` request from the server."""
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "method": "workspace/configuration",
        "params": {"items": [{"section": "harper-ls"}]},
    }


def _make_register_capability_request(request_id: int = 3) -> dict:
    """Build a ``client/registerCapability`` request from the server."""
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "method": "client/registerCapability",
        "params": {
            "registrations": [
                {
                    "id": "reg-1",
                    "method": "workspace/didChangeConfiguration",
                }
            ]
        },
    }


class TestHarperStartupRace(unittest.TestCase):
    """Verify that initialize and send_text are deferred until process is ready."""

    def setUp(self):
        """Start QProcess and QTimer patches for the entire test."""
        self._qproc_patcher = patch("phraise.harper_lsp_manager.QProcess")
        self._qtimer_patcher = patch("phraise.harper_lsp_manager.QTimer")
        self.mock_qproc_cls = self._qproc_patcher.start()
        self.mock_qtimer_cls = self._qtimer_patcher.start()

        # Default mock process
        self.mock_proc = MagicMock()
        self.mock_proc.readAllStandardOutput.return_value = b""
        self.mock_proc.state.return_value = 0
        self.mock_qproc_cls.return_value = self.mock_proc
        self.mock_qproc_cls.Running = 2
        self.mock_qproc_cls.NotRunning = 0
        self.mock_qproc_cls.Starting = 1

        # Default mock timer
        self.mock_timer = MagicMock()
        self.mock_qtimer_cls.return_value = self.mock_timer

        self.manager = HarperLspManager("harper-ls.exe", "American", {}, 30)

    def tearDown(self):
        """Stop patches."""
        self._qproc_patcher.stop()
        self._qtimer_patcher.stop()

    def _get_slot(self, signal_name: str):
        """Return the first connected slot for a QProcess signal."""
        signal = getattr(self.mock_proc, signal_name)
        calls = signal.connect.call_args_list
        self.assertGreater(
            len(calls), 0,
            f"{signal_name} must have at least one connected slot",
        )
        return calls[0][0][0]

    # ------------------------------------------------------------------
    # 1. send_text guarded against not-running process
    # ------------------------------------------------------------------

    def test_send_text_noop_when_process_not_running(self):
        """send_text() must NOT write to stdin when process is not Running."""
        self.mock_proc.state.return_value = 0
        self.mock_proc.write.reset_mock()
        self.manager.send_text("hello world")
        self.mock_proc.write.assert_not_called()

    def test_send_text_noop_when_process_starting(self):
        """send_text() must NOT write to stdin when process is Starting (1)."""
        self.mock_proc.state.return_value = 1
        self.mock_proc.write.reset_mock()
        self.manager.send_text("hello world")
        self.mock_proc.write.assert_not_called()

    def test_send_text_writes_when_process_running(self):
        """send_text() writes to stdin when process is Running (2)."""
        self.mock_proc.state.return_value = 2
        self.mock_proc.write.reset_mock()
        self.manager.send_text("hello world")

        self.assertGreater(self.mock_proc.write.call_count, 0)
        written = b"".join(
            c[0][0] for c in self.mock_proc.write.call_args_list
        )
        self.assertIn(b"textDocument/didOpen", written)
        self.assertIn(b'"text": "hello world"', written)

    # ------------------------------------------------------------------
    # 2. _on_process_started sends initialize request
    # ------------------------------------------------------------------

    def test_on_process_started_sends_initialize(self):
        """When QProcess.started fires, initialize request is sent."""
        self.manager.start()
        self.mock_proc.write.reset_mock()

        slot = self._get_slot("started")
        slot()

        written = b"".join(
            c[0][0] for c in self.mock_proc.write.call_args_list
        )
        self.assertIn(b'"method": "initialize"', written)
        self.assertIn(b'"id": 1', written)

    def test_on_process_started_only_sends_initialize_not_initialized(self):
        """The started handler sends initialize, not initialized notification."""
        self.manager.start()
        self.mock_proc.write.reset_mock()

        slot = self._get_slot("started")
        slot()

        written = b"".join(
            c[0][0] for c in self.mock_proc.write.call_args_list
        )
        self.assertIn(b'"method": "initialize"', written)
        self.assertNotIn(b'"method": "initialized"', written)

    # ------------------------------------------------------------------
    # 3. initialize response → initialized notification → server_ready
    # ------------------------------------------------------------------

    def test_initialize_response_triggers_initialized_and_server_ready(self):
        """Receiving the initialize response sends initialized + emits server_ready."""
        self.manager.server_ready = Mock()
        self.manager.start()

        started_slot = self._get_slot("started")
        started_slot()
        self.mock_proc.write.reset_mock()

        stdout_slot = self._get_slot("readyReadStandardOutput")
        self.mock_proc.readAllStandardOutput.return_value = _make_frame(
            _make_initialize_response(request_id=1)
        )
        stdout_slot()

        written = b"".join(
            c[0][0] for c in self.mock_proc.write.call_args_list
        )
        self.assertIn(b'"method": "initialized"', written)
        self.manager.server_ready.emit.assert_called_once()

    def test_initialize_response_only_triggers_once(self):
        """Server must not re-emit server_ready on subsequent responses."""
        self.manager.server_ready = Mock()
        self.manager.start()

        started_slot = self._get_slot("started")
        started_slot()

        stdout_slot = self._get_slot("readyReadStandardOutput")

        self.mock_proc.readAllStandardOutput.return_value = _make_frame(
            _make_initialize_response(request_id=1)
        )
        stdout_slot()
        self.assertEqual(self.manager.server_ready.emit.call_count, 1)

        # Same response again — should NOT re-trigger
        self.mock_proc.readAllStandardOutput.return_value = _make_frame(
            _make_initialize_response(request_id=1)
        )
        stdout_slot()
        self.assertEqual(self.manager.server_ready.emit.call_count, 1)

    # ------------------------------------------------------------------
    # 4. Server requests handled (workspace/configuration, registerCapability)
    # ------------------------------------------------------------------

    def test_workspace_configuration_request_responded(self):
        """Server's workspace/configuration request gets a response."""
        self.manager.start()
        started_slot = self._get_slot("started")
        started_slot()
        self.mock_proc.write.reset_mock()

        stdout_slot = self._get_slot("readyReadStandardOutput")
        self.mock_proc.readAllStandardOutput.return_value = _make_frame(
            _make_workspace_config_request(request_id=2)
        )
        stdout_slot()

        written = b"".join(
            c[0][0] for c in self.mock_proc.write.call_args_list
        )
        self.assertIn(b'"id": 2', written)
        self.assertIn(b'"result": []', written)

    def test_register_capability_request_responded(self):
        """Server's client/registerCapability request gets a response."""
        self.manager.start()
        started_slot = self._get_slot("started")
        started_slot()
        self.mock_proc.write.reset_mock()

        stdout_slot = self._get_slot("readyReadStandardOutput")
        self.mock_proc.readAllStandardOutput.return_value = _make_frame(
            _make_register_capability_request(request_id=3)
        )
        stdout_slot()

        written = b"".join(
            c[0][0] for c in self.mock_proc.write.call_args_list
        )
        self.assertIn(b'"id": 3', written)
        self.assertIn(b'"result": null', written)

    # ------------------------------------------------------------------
    # 5. Full startup sequence — correct message order
    # ------------------------------------------------------------------

    def test_full_startup_sequence_message_order(self):
        """Messages arrive in correct order: initialize→response→initialized→didOpen."""
        self.manager.server_ready = Mock()
        self.manager.start()
        self.mock_proc.write.reset_mock()

        # Step 1: process starts → sends initialize
        started_slot = self._get_slot("started")
        started_slot()

        writes_after_start = [
            json.loads(c[0][0].decode("utf-8").split("\r\n\r\n", 1)[-1])
            for c in self.mock_proc.write.call_args_list
        ]
        self.assertEqual(writes_after_start[0]["method"], "initialize")
        self.assertEqual(len(writes_after_start), 1)

        # Step 2: server sends initialize response → sends initialized
        self.mock_proc.write.reset_mock()
        stdout_slot = self._get_slot("readyReadStandardOutput")
        self.mock_proc.readAllStandardOutput.return_value = _make_frame(
            _make_initialize_response(request_id=1)
        )
        stdout_slot()

        writes_after_response = [
            json.loads(c[0][0].decode("utf-8").split("\r\n\r\n", 1)[-1])
            for c in self.mock_proc.write.call_args_list
        ]
        self.assertEqual(writes_after_response[0]["method"], "initialized")
        self.assertEqual(len(writes_after_response), 1)
        self.manager.server_ready.emit.assert_called_once()

        # Step 3: server_ready fires → client calls send_text → didOpen sent
        self.mock_proc.write.reset_mock()
        self.mock_proc.state.return_value = 2
        self.manager.send_text("hello world")

        writes_after_ready = [
            json.loads(c[0][0].decode("utf-8").split("\r\n\r\n", 1)[-1])
            for c in self.mock_proc.write.call_args_list
        ]
        self.assertEqual(writes_after_ready[0]["method"], "textDocument/didOpen")
        self.assertIn("hello world", json.dumps(writes_after_ready[0]))

    # ------------------------------------------------------------------
    # 6. Slow start — data accumulates correctly
    # ------------------------------------------------------------------

    def test_slow_start_data_not_lost(self):
        """When process sends data before started signal, data accumulates
        and is decoded correctly once started fires."""
        self.manager.server_ready = Mock()
        self.manager.diagnostics_ready = Mock()

        stdout_slot = self._get_slot("readyReadStandardOutput")

        # Feed initialize response BEFORE started signal
        init_response = _make_initialize_response(request_id=1)
        self.mock_proc.readAllStandardOutput.return_value = _make_frame(
            init_response
        )
        stdout_slot()

        # Now simulate started → sends initialize request with request_id=1
        started_slot = self._get_slot("started")
        started_slot()

        # Feed another frame to trigger _decode_frames again
        self.mock_proc.readAllStandardOutput.return_value = _make_frame(
            _make_initialize_response(request_id=1)
        )
        stdout_slot()

        self.manager.server_ready.emit.assert_called_once()

    # ------------------------------------------------------------------
    # 7. Integration: HarperClient defers initialize + send_text
    # ------------------------------------------------------------------

    def test_harper_client_defers_initialize_and_send_text(self):
        """HarperClient.check_text() calls start() only, not initialize() or
        send_text() — those are deferred to the signal chain."""
        from phraise.harper_client import HarperClient

        with patch("phraise.harper_client.get_harper_binary_path") as m_bin, \
             patch("phraise.harper_client.HarperLspManager") as m_mgr_cls, \
             patch("phraise.harper_client.QTimer") as m_timer:

            m_bin.return_value = "harper-ls.exe"
            mock_mgr = MagicMock()
            m_mgr_cls.return_value = mock_mgr
            m_timer.return_value = MagicMock()

            client = HarperClient()
            client.check_text("hello world")

            mock_mgr.start.assert_called_once()
            mock_mgr.initialize.assert_not_called()
            mock_mgr.send_text.assert_not_called()
            mock_mgr.server_ready.connect.assert_called_once()

            # Simulate server_ready firing → verify send_text is called
            mock_mgr.send_text.reset_mock()
            connect_handler = mock_mgr.server_ready.connect.call_args[0][0]
            connect_handler()
            mock_mgr.send_text.assert_called_once_with("hello world")


if __name__ == "__main__":
    unittest.main()
