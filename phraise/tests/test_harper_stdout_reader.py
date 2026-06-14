"""Tests for HarperLspManager stdout reader — Content-Length frame decoding.

Verifies that ``_on_stdout_ready()`` correctly parses LSP frames from
QProcess stdout and emits ``diagnostics_ready`` for ``publishDiagnostics``
notifications.
"""

import json
import unittest
from unittest.mock import MagicMock, Mock, patch

from phraise.harper_lsp_manager import HarperLspManager


def _make_frame(body: dict) -> bytes:
    """Encode a JSON-RPC message as a Content-Length framed byte string."""
    raw = json.dumps(body, ensure_ascii=False).encode("utf-8")
    header = f"Content-Length: {len(raw)}\r\n\r\n".encode("ascii")
    return header + raw


def _publish_diag(
    message: str = "misspelled word",
    line: int = 0,
    start_char: int = 0,
    end_char: int = 4,
) -> dict:
    """Build a minimal ``textDocument/publishDiagnostics`` notification."""
    return {
        "jsonrpc": "2.0",
        "method": "textDocument/publishDiagnostics",
        "params": {
            "uri": "file:///test.txt",
            "diagnostics": [
                {
                    "range": {
                        "start": {"line": line, "character": start_char},
                        "end": {"line": line, "character": end_char},
                    },
                    "severity": 2,
                    "message": message,
                    "source": "harper",
                    "code": "SPELL",
                }
            ],
        },
    }


class TestHarperStdoutReader(unittest.TestCase):
    """Mock tests for the stdout frame decoder."""

    # ------------------------------------------------------------------
    # Setup helper
    # ------------------------------------------------------------------

    def _make_manager_with_mock_process(self) -> tuple[HarperLspManager, MagicMock]:
        """Create a HarperLspManager with a fully mocked QProcess.

        Returns (manager, mock_process) — call the raw stdout slot via
        ``mock_process.readyReadStandardOutput.connect.call_args[0][0]``.
        """
        with patch("phraise.harper_lsp_manager.QProcess") as m_cls, \
             patch("phraise.harper_lsp_manager.QTimer") as m_timer:
            mock_proc = MagicMock()
            # readAllStandardOutput() returns empty by default
            mock_proc.readAllStandardOutput.return_value = b""
            m_cls.return_value = mock_proc
            m_timer.return_value = MagicMock()

            manager = HarperLspManager("harper-ls.exe", "American", {}, 30)
            return manager, mock_proc

    def _get_stdout_slot(self, mock_proc: MagicMock):
        """Return the slot connected to ``readyReadStandardOutput``."""
        connect_calls = mock_proc.readyReadStandardOutput.connect.call_args_list
        self.assertGreater(len(connect_calls), 0,
                           "readyReadStandardOutput must be connected")
        return connect_calls[0][0][0]

    def _feed_bytes(self, mock_proc: MagicMock, data: bytes) -> None:
        """Simulate QProcess emitting ``readyReadStandardOutput`` with data."""
        mock_proc.readAllStandardOutput.return_value = data
        slot = self._get_stdout_slot(mock_proc)
        slot()

    # ------------------------------------------------------------------
    # 1. Single publishDiagnostics frame
    # ------------------------------------------------------------------

    def test_single_publish_diagnostics_frame_emits_signal(self):
        """A complete frame with publishDiagnostics emits diagnostics_ready."""
        manager, mock_proc = self._make_manager_with_mock_process()
        manager.diagnostics_ready = Mock()

        diag_msg = _publish_diag(message="misspelled word")
        self._feed_bytes(mock_proc, _make_frame(diag_msg))

        manager.diagnostics_ready.emit.assert_called_once()
        diags = manager.diagnostics_ready.emit.call_args[0][0]
        self.assertEqual(len(diags), 1)
        self.assertEqual(diags[0].message, "misspelled word")
        self.assertEqual(diags[0].severity, 2)

    # ------------------------------------------------------------------
    # 2. Split header and body across two chunks
    # ------------------------------------------------------------------

    def test_split_header_and_body_across_chunks(self):
        """Header arrives first, then body in a second chunk — still decodes."""
        manager, mock_proc = self._make_manager_with_mock_process()
        manager.diagnostics_ready = Mock()

        diag_msg = _publish_diag(message="split frame")
        full_frame = _make_frame(diag_msg)

        # Find the \r\n\r\n separator
        sep = full_frame.find(b"\r\n\r\n")
        header_chunk = full_frame[:sep + 2]  # "Content-Length: N\r\n"
        body_chunk = full_frame[sep + 2:]     # "\r\n{json}"

        # Feed header only — signal must NOT fire yet
        self._feed_bytes(mock_proc, header_chunk)
        manager.diagnostics_ready.emit.assert_not_called()

        # Feed the rest — signal fires now
        self._feed_bytes(mock_proc, body_chunk)
        manager.diagnostics_ready.emit.assert_called_once()
        diags = manager.diagnostics_ready.emit.call_args[0][0]
        self.assertEqual(len(diags), 1)
        self.assertEqual(diags[0].message, "split frame")

    # ------------------------------------------------------------------
    # 3. Multiple frames in one chunk
    # ------------------------------------------------------------------

    def test_multiple_frames_in_one_chunk(self):
        """Two publishDiagnostics frames back-to-back — both emitted."""
        manager, mock_proc = self._make_manager_with_mock_process()
        manager.diagnostics_ready = Mock()

        frame1 = _make_frame(_publish_diag(message="first", start_char=0, end_char=5))
        frame2 = _make_frame(_publish_diag(message="second", start_char=6, end_char=11))

        self._feed_bytes(mock_proc, frame1 + frame2)

        self.assertEqual(manager.diagnostics_ready.emit.call_count, 2)
        args1 = manager.diagnostics_ready.emit.call_args_list[0][0][0]
        args2 = manager.diagnostics_ready.emit.call_args_list[1][0][0]
        self.assertEqual(args1[0].message, "first")
        self.assertEqual(args2[0].message, "second")

    # ------------------------------------------------------------------
    # 4. Non-publishDiagnostics message — no emission
    # ------------------------------------------------------------------

    def test_non_publish_diagnostics_message_does_not_emit(self):
        """A window/logMessage notification must not emit diagnostics_ready."""
        manager, mock_proc = self._make_manager_with_mock_process()
        manager.diagnostics_ready = Mock()

        log_msg = {
            "jsonrpc": "2.0",
            "method": "window/logMessage",
            "params": {"type": 4, "message": "hello"},
        }
        self._feed_bytes(mock_proc, _make_frame(log_msg))

        manager.diagnostics_ready.emit.assert_not_called()

    # ------------------------------------------------------------------
    # 5. Malformed JSON — no crash
    # ------------------------------------------------------------------

    def test_malformed_json_does_not_crash(self):
        """Garbage bytes after Content-Length header — skip gracefully."""
        manager, mock_proc = self._make_manager_with_mock_process()
        manager.diagnostics_ready = Mock()

        garbage = b"Content-Length: 5\r\n\r\nNOTJSON"
        self._feed_bytes(mock_proc, garbage)

        manager.diagnostics_ready.emit.assert_not_called()

    # ------------------------------------------------------------------
    # 6. Empty diagnostics list — must emit
    # ------------------------------------------------------------------

    def test_empty_diagnostics_emits(self):
        """A publishDiagnostics with empty diagnostics list — emit []."""
        manager, mock_proc = self._make_manager_with_mock_process()
        manager.diagnostics_ready = Mock()

        empty_diag = {
            "jsonrpc": "2.0",
            "method": "textDocument/publishDiagnostics",
            "params": {"uri": "file:///test.txt", "diagnostics": []},
        }
        self._feed_bytes(mock_proc, _make_frame(empty_diag))

        manager.diagnostics_ready.emit.assert_called_once_with([])

    # ------------------------------------------------------------------
    # 7. Mixed messages — only publishDiagnostics emitted
    # ------------------------------------------------------------------

    def test_mixed_messages_only_emit_for_publish_diag(self):
        """Interleaved logMessage + publishDiagnostics:
        only the diag message triggers emission."""
        manager, mock_proc = self._make_manager_with_mock_process()
        manager.diagnostics_ready = Mock()

        log_frame = _make_frame({
            "jsonrpc": "2.0",
            "method": "window/logMessage",
            "params": {"type": 3, "message": "log"},
        })
        diag_frame = _make_frame(_publish_diag(message="mixed test"))

        self._feed_bytes(mock_proc, log_frame + diag_frame)

        manager.diagnostics_ready.emit.assert_called_once()
        diags = manager.diagnostics_ready.emit.call_args[0][0]
        self.assertEqual(diags[0].message, "mixed test")

    # ------------------------------------------------------------------
    # 8. Empty data — no-op
    # ------------------------------------------------------------------

    def test_empty_read_does_nothing(self):
        """readAllStandardOutput returns empty bytes — no crash, no emission."""
        manager, mock_proc = self._make_manager_with_mock_process()
        manager.diagnostics_ready = Mock()

        mock_proc.readAllStandardOutput.return_value = b""
        slot = self._get_stdout_slot(mock_proc)
        slot()

        manager.diagnostics_ready.emit.assert_not_called()

    # ------------------------------------------------------------------
    # 9. Incremental accumulation across many small chunks
    # ------------------------------------------------------------------

    def test_byte_by_byte_accumulation(self):
        """Feeding one byte at a time still eventually decodes the frame."""
        manager, mock_proc = self._make_manager_with_mock_process()
        manager.diagnostics_ready = Mock()

        diag_msg = _publish_diag(message="byte by byte")
        full_frame = _make_frame(diag_msg)

        for i in range(len(full_frame)):
            mock_proc.readAllStandardOutput.return_value = full_frame[i:i + 1]
            slot = self._get_stdout_slot(mock_proc)
            slot()

        manager.diagnostics_ready.emit.assert_called_once()
        diags = manager.diagnostics_ready.emit.call_args[0][0]
        self.assertEqual(diags[0].message, "byte by byte")


if __name__ == "__main__":
    unittest.main()
