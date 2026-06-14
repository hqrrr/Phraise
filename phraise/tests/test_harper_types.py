"""Unit tests for ``phraise.harper_types``.

Tests cover dataclass construction, message builders, response parsers,
and format converters — all against the real protocol captured from
harper-ls v2.4.0 (see ``phraise/lsp/LSP_PROTOCOL.md``).
"""

import unittest

from phraise.harper_types import (
    LspCodeAction,
    LspDiagnostic,
    LspPosition,
    LspRange,
    LspTextEdit,
    HarperIssue,
    _extract_text_at_range,
    build_code_action_request,
    build_did_open_notification,
    build_exit_notification,
    build_initialize_request,
    build_initialized_notification,
    build_register_capability_response,
    build_shutdown_request,
    build_workspace_config_response,
    diagnostics_to_harper_issues,
    parse_code_action_response,
    parse_publish_diagnostics,
)


class TestDataclasses(unittest.TestCase):
    """Verify dataclass construction and defaults."""

    def test_lsp_position(self):
        p = LspPosition(line=0, character=4)
        self.assertEqual(p.line, 0)
        self.assertEqual(p.character, 4)

    def test_lsp_range(self):
        r = LspRange(
            start=LspPosition(0, 0),
            end=LspPosition(0, 4),
        )
        self.assertEqual(r.start.line, 0)
        self.assertEqual(r.start.character, 0)
        self.assertEqual(r.end.line, 0)
        self.assertEqual(r.end.character, 4)

    def test_lsp_diagnostic_defaults(self):
        r = LspRange(LspPosition(0, 0), LspPosition(0, 4))
        d = LspDiagnostic(range=r, severity=4, message="test")
        self.assertEqual(d.source, "")
        self.assertEqual(d.code, "")
        self.assertIsNone(d.data)

    def test_lsp_text_edit(self):
        r = LspRange(LspPosition(0, 0), LspPosition(0, 4))
        e = LspTextEdit(range=r, newText="hello")
        self.assertEqual(e.newText, "hello")
        self.assertIs(e.range, r)

    def test_lsp_code_action_defaults(self):
        a = LspCodeAction(title="Fix it")
        self.assertEqual(a.kind, "")
        self.assertIsNone(a.edit)
        self.assertFalse(a.is_spelling_fix)

    def test_harper_issue(self):
        issue = HarperIssue(
            original="helo",
            suggestion="hello",
            reason="Did you mean to spell `helo` this way?",
            severity="hint",
        )
        self.assertEqual(issue.original, "helo")
        self.assertEqual(issue.suggestion, "hello")
        self.assertEqual(issue.severity, "hint")


class TestBuildInitializeRequest(unittest.TestCase):
    """``build_initialize_request`` — LSP_PROTOCOL.md §1."""

    def test_structure(self):
        msg = build_initialize_request()
        self.assertEqual(msg["jsonrpc"], "2.0")
        self.assertEqual(msg["method"], "initialize")
        self.assertIsInstance(msg["id"], int)

    def test_params_shape(self):
        msg = build_initialize_request(request_id=5)
        self.assertEqual(msg["id"], 5)
        params = msg["params"]
        self.assertIsNone(params["processId"])
        self.assertIsNone(params["rootUri"])
        self.assertEqual(params["capabilities"], {})
        self.assertEqual(params["trace"], "off")


class TestBuildInitializedNotification(unittest.TestCase):
    """``build_initialized_notification`` — LSP_PROTOCOL.md §3."""

    def test_structure(self):
        msg = build_initialized_notification()
        self.assertEqual(msg["jsonrpc"], "2.0")
        self.assertEqual(msg["method"], "initialized")
        self.assertEqual(msg["params"], {})
        self.assertNotIn("id", msg)


class TestBuildDidOpenNotification(unittest.TestCase):
    """``build_did_open_notification`` — LSP_PROTOCOL.md §7."""

    def test_has_no_id_field(self):
        """Notifications MUST NOT carry an ``id`` field."""
        msg = build_did_open_notification(text="helo wrld")
        self.assertNotIn("id", msg)

    def test_structure(self):
        msg = build_did_open_notification(text="helo wrld")
        self.assertEqual(msg["jsonrpc"], "2.0")
        self.assertEqual(msg["method"], "textDocument/didOpen")
        td = msg["params"]["textDocument"]
        self.assertEqual(td["uri"], "file:///phraise.txt")
        self.assertEqual(td["languageId"], "plaintext")
        self.assertEqual(td["version"], 1)
        self.assertEqual(td["text"], "helo wrld")

    def test_custom_uri(self):
        msg = build_did_open_notification(
            text="test", uri="file:///custom.md", language_id="markdown", version=3
        )
        td = msg["params"]["textDocument"]
        self.assertEqual(td["uri"], "file:///custom.md")
        self.assertEqual(td["languageId"], "markdown")
        self.assertEqual(td["version"], 3)


class TestBuildShutdownRequest(unittest.TestCase):
    """``build_shutdown_request`` — LSP_PROTOCOL.md §10.

    CRITICAL:  Must NOT include ``"params": {}``.
    """

    def test_has_no_params(self):
        msg = build_shutdown_request()
        self.assertNotIn("params", msg)

    def test_structure(self):
        msg = build_shutdown_request(request_id=42)
        self.assertEqual(msg["jsonrpc"], "2.0")
        self.assertEqual(msg["id"], 42)
        self.assertEqual(msg["method"], "shutdown")

    def test_default_id(self):
        msg = build_shutdown_request()
        self.assertEqual(msg["id"], 999)


class TestBuildExitNotification(unittest.TestCase):
    """``build_exit_notification`` — LSP_PROTOCOL.md §11."""

    def test_structure(self):
        msg = build_exit_notification()
        self.assertEqual(msg["jsonrpc"], "2.0")
        self.assertEqual(msg["method"], "exit")
        self.assertNotIn("id", msg)
        self.assertNotIn("params", msg)


class TestBuildCodeActionRequest(unittest.TestCase):
    """``build_code_action_request`` — LSP_PROTOCOL.md §9."""

    def setUp(self):
        self.diag_range = LspRange(LspPosition(0, 0), LspPosition(0, 4))
        self.diagnostic = LspDiagnostic(
            range=self.diag_range,
            severity=4,
            message="Did you mean to spell `helo` this way?",
            source="Harper",
            code="SpellCheck",
        )

    def test_structure(self):
        msg = build_code_action_request(
            request_id=100,
            uri="file:///test.txt",
            diagnostic_range=self.diag_range,
            diagnostic=self.diagnostic,
        )
        self.assertEqual(msg["jsonrpc"], "2.0")
        self.assertEqual(msg["id"], 100)
        self.assertEqual(msg["method"], "textDocument/codeAction")

    def test_params_include_context_diagnostics(self):
        msg = build_code_action_request(
            request_id=100,
            uri="file:///test.txt",
            diagnostic_range=self.diag_range,
            diagnostic=self.diagnostic,
        )
        ctx = msg["params"]["context"]
        self.assertIn("diagnostics", ctx)
        self.assertEqual(len(ctx["diagnostics"]), 1)
        diag = ctx["diagnostics"][0]
        self.assertEqual(diag["code"], "SpellCheck")
        self.assertEqual(diag["severity"], 4)
        self.assertEqual(diag["source"], "Harper")
        self.assertEqual(
            diag["message"], "Did you mean to spell `helo` this way?"
        )

    def test_params_range_matches(self):
        msg = build_code_action_request(
            request_id=100,
            uri="file:///test.txt",
            diagnostic_range=self.diag_range,
            diagnostic=self.diagnostic,
        )
        rng = msg["params"]["range"]
        self.assertEqual(rng["start"]["line"], 0)
        self.assertEqual(rng["start"]["character"], 0)
        self.assertEqual(rng["end"]["line"], 0)
        self.assertEqual(rng["end"]["character"], 4)


class TestBuildWorkspaceConfigResponse(unittest.TestCase):
    """``build_workspace_config_response`` — LSP_PROTOCOL.md §5."""

    def test_structure(self):
        msg = build_workspace_config_response(request_id=0)
        self.assertEqual(msg["jsonrpc"], "2.0")
        self.assertEqual(msg["id"], 0)
        self.assertEqual(msg["result"], [])


class TestBuildRegisterCapabilityResponse(unittest.TestCase):
    """``build_register_capability_response`` — LSP_PROTOCOL.md §6."""

    def test_structure(self):
        msg = build_register_capability_response(request_id=1)
        self.assertEqual(msg["jsonrpc"], "2.0")
        self.assertEqual(msg["id"], 1)
        self.assertIsNone(msg["result"])


class TestParsePublishDiagnostics(unittest.TestCase):
    """``parse_publish_diagnostics`` — LSP_PROTOCOL.md §8."""

    def test_wrong_method_returns_empty_list(self):
        data = {"method": "textDocument/didOpen"}
        result = parse_publish_diagnostics(data)
        self.assertEqual(result, [])

    def test_no_diagnostics_returns_empty_list(self):
        data = {
            "method": "textDocument/publishDiagnostics",
            "params": {"uri": "file:///test.txt", "diagnostics": []},
        }
        result = parse_publish_diagnostics(data)
        self.assertEqual(result, [])

    def test_missing_params_returns_empty_list(self):
        data = {"method": "textDocument/publishDiagnostics"}
        result = parse_publish_diagnostics(data)
        self.assertEqual(result, [])

    def test_parse_real_spelling_diagnostic(self):
        """Use the exact JSON from LSP_PROTOCOL.md §8."""
        data = {
            "jsonrpc": "2.0",
            "method": "textDocument/publishDiagnostics",
            "params": {
                "uri": "file:///test.txt",
                "diagnostics": [
                    {
                        "code": "SpellCheck",
                        "range": {
                            "start": {"line": 0, "character": 0},
                            "end": {"line": 0, "character": 4},
                        },
                        "severity": 4,
                        "source": "Harper",
                        "message": "Did you mean to spell `helo` this way?",
                    }
                ],
            },
        }
        result = parse_publish_diagnostics(data)
        self.assertEqual(len(result), 1)
        d = result[0]
        self.assertEqual(d.code, "SpellCheck")
        self.assertEqual(d.severity, 4)
        self.assertEqual(d.source, "Harper")
        self.assertEqual(d.message, "Did you mean to spell `helo` this way?")
        self.assertEqual(d.range.start.line, 0)
        self.assertEqual(d.range.start.character, 0)
        self.assertEqual(d.range.end.line, 0)
        self.assertEqual(d.range.end.character, 4)

    def test_parse_empty_diagnostics_on_shutdown(self):
        """Shutdown clears diagnostics with an empty array."""
        data = {
            "jsonrpc": "2.0",
            "method": "textDocument/publishDiagnostics",
            "params": {"uri": "file:///test.txt", "diagnostics": []},
        }
        result = parse_publish_diagnostics(data)
        self.assertEqual(result, [])


class TestParseCodeActionResponse(unittest.TestCase):
    """``parse_code_action_response`` — LSP_PROTOCOL.md §9."""

    def test_empty_result_returns_empty_list(self):
        data = {"jsonrpc": "2.0", "id": 100, "result": []}
        result = parse_code_action_response(data)
        self.assertEqual(result, [])

    def test_missing_result_returns_empty_list(self):
        data = {"jsonrpc": "2.0", "id": 100}
        result = parse_code_action_response(data)
        self.assertEqual(result, [])

    def test_quickfix_marked_as_spelling_fix(self):
        """Verify ``is_spelling_fix=True`` for quickfix items with edits."""
        data = {
            "jsonrpc": "2.0",
            "id": 100,
            "result": [
                {
                    "title": 'Replace with: "hello"',
                    "kind": "quickfix",
                    "edit": {
                        "changes": {
                            "file:///test.txt": [
                                {
                                    "newText": "hello",
                                    "range": {
                                        "start": {"line": 0, "character": 0},
                                        "end": {"line": 0, "character": 4},
                                    },
                                }
                            ]
                        }
                    },
                    "command": {
                        "title": "Record lint statistic",
                        "command": "HarperRecordLint",
                        "arguments": [],
                    },
                },
                {
                    "title": "Ignore Harper error.",
                    "command": "HarperIgnoreLint",
                    "arguments": [],
                },
                {
                    "title": 'Add "helo" to the user dictionary.',
                    "command": "HarperAddToUserDict",
                    "arguments": [],
                },
            ],
        }
        result = parse_code_action_response(data)
        self.assertEqual(len(result), 3)

        # First: quickfix with edit → spelling fix
        self.assertTrue(result[0].is_spelling_fix)
        self.assertEqual(result[0].kind, "quickfix")
        self.assertEqual(result[0].title, 'Replace with: "hello"')
        self.assertIsNotNone(result[0].edit)
        self.assertIn("changes", result[0].edit)

        # Second: command-only → NOT a spelling fix
        self.assertFalse(result[1].is_spelling_fix)
        self.assertEqual(result[1].kind, "")
        self.assertIsNone(result[1].edit)

        # Third: command-only → NOT a spelling fix
        self.assertFalse(result[2].is_spelling_fix)


class TestDiagnosticsToHarperIssues(unittest.TestCase):
    """``diagnostics_to_harper_issues`` — format converter."""

    def test_severity_mapping(self):
        """Verify the 1→error, 2→warning, 3→info, 4→hint mapping."""
        text = "test"
        diags = [
            LspDiagnostic(range=LspRange(LspPosition(0, 0), LspPosition(0, 4)),
                          severity=1, message="err"),
            LspDiagnostic(range=LspRange(LspPosition(0, 0), LspPosition(0, 4)),
                          severity=2, message="warn"),
            LspDiagnostic(range=LspRange(LspPosition(0, 0), LspPosition(0, 4)),
                          severity=3, message="info"),
            LspDiagnostic(range=LspRange(LspPosition(0, 0), LspPosition(0, 4)),
                          severity=4, message="hint"),
        ]
        issues = diagnostics_to_harper_issues(diags, text)
        self.assertEqual(len(issues), 4)
        self.assertEqual(issues[0].severity, "error")
        self.assertEqual(issues[1].severity, "warning")
        self.assertEqual(issues[2].severity, "info")
        self.assertEqual(issues[3].severity, "hint")

    def test_extracts_original_text_from_range(self):
        """Given "helo wrld" and range (0,0)-(0,4), original should be "helo"."""
        text = "helo wrld"
        diags = [
            LspDiagnostic(
                range=LspRange(LspPosition(0, 0), LspPosition(0, 4)),
                severity=4,
                message="Did you mean to spell `helo` this way?",
                source="Harper",
                code="SpellCheck",
            )
        ]
        issues = diagnostics_to_harper_issues(diags, text)
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].original, "helo")
        self.assertEqual(issues[0].suggestion, "")  # Filled later by fix applier
        self.assertEqual(issues[0].reason,
                         "Did you mean to spell `helo` this way?")

    def test_empty_diagnostics_returns_empty_list(self):
        self.assertEqual(diagnostics_to_harper_issues([], "text"), [])

    def test_unknown_severity_defaults_to_hint(self):
        """A severity value outside 1-4 should map to ``"hint"``."""
        text = "test"
        diags = [
            LspDiagnostic(range=LspRange(LspPosition(0, 0), LspPosition(0, 4)),
                          severity=99, message="weird"),
        ]
        issues = diagnostics_to_harper_issues(diags, text)
        self.assertEqual(issues[0].severity, "hint")

    def test_multi_diagnostic(self):
        text = "helo wrld is a tset"
        diags = [
            LspDiagnostic(range=LspRange(LspPosition(0, 0), LspPosition(0, 4)),
                          severity=4, message="Spell: helo"),
            LspDiagnostic(range=LspRange(LspPosition(0, 5), LspPosition(0, 9)),
                          severity=4, message="Spell: wrld"),
        ]
        issues = diagnostics_to_harper_issues(diags, text)
        self.assertEqual(len(issues), 2)
        self.assertEqual(issues[0].original, "helo")
        self.assertEqual(issues[1].original, "wrld")


class TestExtractTextAtRange(unittest.TestCase):
    """``_extract_text_at_range`` — single-line helper."""

    def test_extracts_substring(self):
        text = "helo wrld"
        result = _extract_text_at_range(text, LspRange(LspPosition(0, 0), LspPosition(0, 4)))
        self.assertEqual(result, "helo")

    def test_middle_of_string(self):
        text = "helo wrld"
        result = _extract_text_at_range(text, LspRange(LspPosition(0, 5), LspPosition(0, 9)))
        self.assertEqual(result, "wrld")

    def test_empty_range(self):
        text = "hello"
        result = _extract_text_at_range(text, LspRange(LspPosition(0, 2), LspPosition(0, 2)))
        self.assertEqual(result, "")

    def test_full_string(self):
        text = "hello"
        result = _extract_text_at_range(text, LspRange(LspPosition(0, 0), LspPosition(0, 5)))
        self.assertEqual(result, "hello")

    def test_zero_start(self):
        text = "abc"
        result = _extract_text_at_range(text, LspRange(LspPosition(0, 0), LspPosition(0, 3)))
        self.assertEqual(result, "abc")


if __name__ == "__main__":
    unittest.main()
