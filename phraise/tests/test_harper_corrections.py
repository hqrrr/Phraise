# PhrAIse - AI writing assistant
# License: GNU GPLv3
# GitHub: https://github.com/hqrrr/Phraise
# Author: hqrrr
#
# Description: Unit tests for harper corrections.
"""Tests for automatic spelling/grammar correction via Harper codeAction.

``HarperClient`` should request code actions for each diagnostic and
apply the first quickfix to produce ``corrected_text`` in the final
``LintResult``.
"""

from __future__ import annotations

import json
import unittest
from unittest.mock import MagicMock, patch

from phraise.harper_client import HarperClient, LintResult


# ---------------------------------------------------------------------------
# Frame builders
# ---------------------------------------------------------------------------

def _make_frame(body: dict) -> bytes:
    raw = json.dumps(body, ensure_ascii=False).encode("utf-8")
    header = f"Content-Length: {len(raw)}\r\n\r\n".encode("ascii")
    return header + raw


def _initialize_response_frame(request_id: int = 1) -> bytes:
    return _make_frame({
        "jsonrpc": "2.0",
        "id": request_id,
        "result": {"capabilities": {}},
    })


def _diagnostics_frame(diagnostics: list[dict], uri: str = "file:///phraise.txt") -> bytes:
    return _make_frame({
        "jsonrpc": "2.0",
        "method": "textDocument/publishDiagnostics",
        "params": {"uri": uri, "diagnostics": diagnostics},
    })


def _empty_diagnostics_frame(uri: str = "file:///test.txt") -> bytes:
    return _diagnostics_frame([], uri=uri)


def _code_action_response_frame(request_id: int, action_title: str, new_text: str,
                                 start_char: int, end_char: int,
                                 line: int = 0) -> bytes:
    return _make_frame({
        "jsonrpc": "2.0",
        "id": request_id,
        "result": [{
            "title": action_title,
            "kind": "quickfix",
            "edit": {
                "changes": {
                    "file:///phraise.txt": [{
                        "newText": new_text,
                        "range": {
                            "start": {"line": line, "character": start_char},
                            "end": {"line": line, "character": end_char},
                        },
                    }]
                }
            },
        }],
    })


# ===================================================================
# Test 1 — Code action produces corrected text
# ===================================================================

class TestHarperCorrections(unittest.TestCase):
    """``HarperClient.finished`` must emit ``LintResult`` whose
    ``corrected_text`` reflects Harper's first suggested fix for each issue.
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

    def _setup_client(self, text: str) -> tuple[HarperClient, list]:
        """Create a client, call check_text, and return (client, emitted_results)."""
        client = HarperClient()
        emitted: list = []
        client.finished.connect(emitted.append)

        issues, ret_text = client.check_text(text)
        self.assertEqual(issues, [])
        self.assertEqual(ret_text, text)

        # Simulate what _on_process_started does
        client._manager._request_id = 1
        client._manager._initialize_request_id = 1

        return client, emitted

    def test_code_action_produces_corrected_text(self):
        """A single SpellCheck diagnostic → codeAction → corrected_text differs
        from the original input.
        """
        client, emitted = self._setup_client("Key Fewatures")

        # Feed initialize response → server_ready → send_text("Key Fewatures")
        client._manager._buffer += _initialize_response_frame(request_id=1)
        client._manager._decode_frames()
        # Stop the manager-level send_text timeout
        client._manager._timeout_timer.stop()

        # Feed a diagnostics notification with one spelling issue
        diags = [{
            "code": "SpellCheck",
            "range": {
                "start": {"line": 0, "character": 4},
                "end": {"line": 0, "character": 14},
            },
            "severity": 4,
            "source": "Harper",
            "message": "Did you mean to spell `Fewatures` this way?",
        }]
        client._manager._buffer += _diagnostics_frame(diags)
        client._manager._decode_frames()

        # At this point, _on_diagnostics has been called. It should NOT have
        # emitted finished yet (diagnostics was non-empty). It requested
        # code actions. Verify get_code_actions was written to the process.
        written = b"".join(
            c[0][0] for c in self.mock_proc.write.call_args_list
        )
        self.assertIn(b"textDocument/codeAction", written)

        # Feed the codeAction response.  The get_code_actions call used
        # _request_id = 2 (1 was the initialize).
        client._manager._buffer += _code_action_response_frame(
            request_id=2,
            action_title="Replace with 'Features'",
            new_text="Features",
            start_char=4,
            end_char=14,
        )
        client._manager._decode_frames()

        # Now finished should have been emitted exactly once
        self.assertEqual(len(emitted), 1)

        result: LintResult = emitted[0]
        self.assertTrue(result.success)
        self.assertEqual(result.error, "")
        self.assertEqual(result.corrected_text, "Key Features")
        self.assertNotEqual(result.corrected_text, "Key Fewatures")
        self.assertEqual(len(result.issues), 1)
        self.assertEqual(result.issues[0].original, "Fewatures")
        self.assertEqual(result.issues[0].suggestion, "Features")
        self.assertIn("Did you mean", result.issues[0].reason)

    def test_multiple_diagnostics_all_corrected(self):
        """Two diagnostics → two codeAction responses → both fixes applied."""
        client, emitted = self._setup_client("the helo wrld")

        client._manager._buffer += _initialize_response_frame(request_id=1)
        client._manager._decode_frames()
        client._manager._timeout_timer.stop()

        diags = [
            {
                "code": "SpellCheck",
                "range": {
                    "start": {"line": 0, "character": 4},
                    "end": {"line": 0, "character": 8},
                },
                "severity": 4,
                "source": "Harper",
                "message": "Did you mean 'hello'?",
            },
            {
                "code": "SpellCheck",
                "range": {
                    "start": {"line": 0, "character": 9},
                    "end": {"line": 0, "character": 13},
                },
                "severity": 4,
                "source": "Harper",
                "message": "Did you mean 'world'?",
            },
        ]
        client._manager._buffer += _diagnostics_frame(diags)
        client._manager._decode_frames()

        # Feed codeAction response for request_id=2 (first diagnostic)
        client._manager._buffer += _code_action_response_frame(
            request_id=2,
            action_title="Replace with 'hello'",
            new_text="hello",
            start_char=4,
            end_char=8,
        )
        client._manager._decode_frames()
        # Not yet finished — only 1 of 2 code actions received
        self.assertEqual(len(emitted), 0)

        # Feed codeAction response for request_id=3 (second diagnostic)
        client._manager._buffer += _code_action_response_frame(
            request_id=3,
            action_title="Replace with 'world'",
            new_text="world",
            start_char=9,
            end_char=13,
        )
        client._manager._decode_frames()

        self.assertEqual(len(emitted), 1)
        result = emitted[0]
        self.assertTrue(result.success)
        self.assertEqual(result.corrected_text, "the hello world")
        self.assertEqual(len(result.issues), 2)

    def test_empty_diagnostics_finishes_immediately(self):
        """Empty diagnostics → finished emitted synchronously with original text."""
        client, emitted = self._setup_client("clean text no issues")

        client._manager._buffer += _initialize_response_frame(request_id=1)
        client._manager._decode_frames()
        client._manager._timeout_timer.stop()

        client._manager._buffer += _empty_diagnostics_frame()
        client._manager._decode_frames()

        self.assertEqual(len(emitted), 1)
        result = emitted[0]
        self.assertTrue(result.success)
        self.assertEqual(result.issues, [])
        self.assertEqual(result.corrected_text, "clean text no issues")
        self.assertEqual(result.error, "")

    def test_empty_code_action_result_does_not_crash(self):
        """A codeAction response with an empty result list is safe —
        no edit is applied, and finished is still emitted.
        """
        client, emitted = self._setup_client("Key Fewatures")

        client._manager._buffer += _initialize_response_frame(request_id=1)
        client._manager._decode_frames()
        client._manager._timeout_timer.stop()

        diags = [{
            "code": "SpellCheck",
            "range": {
                "start": {"line": 0, "character": 4},
                "end": {"line": 0, "character": 14},
            },
            "severity": 4,
            "source": "Harper",
            "message": "Did you mean 'Fewatures'?",
        }]
        client._manager._buffer += _diagnostics_frame(diags)
        client._manager._decode_frames()

        # Feed a codeAction response with empty result
        client._manager._buffer += _make_frame({
            "jsonrpc": "2.0",
            "id": 2,
            "result": [],
        })
        client._manager._decode_frames()

        self.assertEqual(len(emitted), 1)
        result = emitted[0]
        self.assertTrue(result.success)
        # No edit was applied — corrected_text equals original
        self.assertEqual(result.corrected_text, "Key Fewatures")
        self.assertEqual(len(result.issues), 1)

    def test_stale_code_action_ignored(self):
        """A codeAction response for an unknown request_id is silently ignored."""
        client, emitted = self._setup_client("hello")

        client._manager._buffer += _initialize_response_frame(request_id=1)
        client._manager._decode_frames()
        client._manager._timeout_timer.stop()

        # Feed empty diagnostics → finished emitted synchronously
        client._manager._buffer += _empty_diagnostics_frame()
        client._manager._decode_frames()

        self.assertEqual(len(emitted), 1)

        # Now feed a stale codeAction response — must not crash or emit again
        client._manager._buffer += _code_action_response_frame(
            request_id=99,
            action_title="Stale",
            new_text="ignored",
            start_char=0,
            end_char=5,
        )
        client._manager._decode_frames()

        # No additional finished emission
        self.assertEqual(len(emitted), 1)


if __name__ == "__main__":
    unittest.main()
