"""RED-phase tests for ``HarperDiagnosticsParser``.

The parser class does NOT exist yet — all tests in this file MUST fail
(``ImportError`` or ``AttributeError``) until Task 8 implements it.

When the class is implemented, these tests should pass without modification.
"""

import unittest

from phraise.harper_types import HarperDiagnosticsParser


class TestHarperDiagnosticsParser(unittest.TestCase):
    """``HarperDiagnosticsParser`` — RED phase (parser not yet implemented)."""

    # ------------------------------------------------------------------ #
    # parse_publish_diagnostics
    # ------------------------------------------------------------------ #

    def test_parse_single_diagnostic(self):
        """Feed valid publishDiagnostics JSON-RPC with 1 diagnostic.

        Expect 1 ``LspDiagnostic`` with code="SpellCheck", severity=4,
        message containing "Did you mean".
        """
        raw = {
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
        result = HarperDiagnosticsParser.parse_publish_diagnostics(raw)
        self.assertEqual(len(result), 1)
        d = result[0]
        self.assertEqual(d.code, "SpellCheck")
        self.assertEqual(d.severity, 4)
        self.assertIn("Did you mean", d.message)

    def test_parse_multiple_diagnostics(self):
        """JSON with 3 diagnostics. Expect 3 objects, preserving order."""
        raw = {
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
                        "message": "First diagnostic",
                    },
                    {
                        "code": "SpellCheck",
                        "range": {
                            "start": {"line": 0, "character": 5},
                            "end": {"line": 0, "character": 9},
                        },
                        "severity": 4,
                        "source": "Harper",
                        "message": "Second diagnostic",
                    },
                    {
                        "code": "Grammar",
                        "range": {
                            "start": {"line": 0, "character": 10},
                            "end": {"line": 0, "character": 15},
                        },
                        "severity": 2,
                        "source": "Harper",
                        "message": "Third diagnostic",
                    },
                ],
            },
        }
        result = HarperDiagnosticsParser.parse_publish_diagnostics(raw)
        self.assertEqual(len(result), 3)
        self.assertEqual(result[0].message, "First diagnostic")
        self.assertEqual(result[1].message, "Second diagnostic")
        self.assertEqual(result[2].message, "Third diagnostic")

    def test_parse_empty_diagnostics(self):
        """``params.diagnostics: []`` → empty list.

        Also represents the shutdown-clearing case.
        """
        raw = {
            "jsonrpc": "2.0",
            "method": "textDocument/publishDiagnostics",
            "params": {
                "uri": "file:///test.txt",
                "diagnostics": [],
            },
        }
        result = HarperDiagnosticsParser.parse_publish_diagnostics(raw)
        self.assertEqual(result, [])

    def test_parse_malformed_json(self):
        """Not valid JSON-RPC envelope → return empty list or raise."""
        raw = {"not": "valid"}
        result = HarperDiagnosticsParser.parse_publish_diagnostics(raw)
        # Must not crash; should return empty list or raise controlled exception
        self.assertEqual(result, [])

    def test_parse_wrong_method(self):
        """JSON-RPC with wrong method → handle gracefully."""
        raw = {
            "jsonrpc": "2.0",
            "method": "textDocument/didOpen",
            "params": {"textDocument": {"uri": "file:///test.txt"}},
        }
        result = HarperDiagnosticsParser.parse_publish_diagnostics(raw)
        self.assertEqual(result, [])

    # ------------------------------------------------------------------ #
    # diagnostics_to_issues  (severity mapping)
    # ------------------------------------------------------------------ #

    def test_parse_severity_error(self):
        """severity=1 → HarperIssue.severity="error"."""
        from phraise.harper_types import LspDiagnostic, LspRange, LspPosition

        diags = [
            LspDiagnostic(
                range=LspRange(LspPosition(0, 0), LspPosition(0, 4)),
                severity=1,
                message="Error test",
            )
        ]
        issues = HarperDiagnosticsParser.diagnostics_to_issues(diags, "test")
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].severity, "error")

    def test_parse_severity_warning(self):
        """severity=2 → HarperIssue.severity="warning"."""
        from phraise.harper_types import LspDiagnostic, LspRange, LspPosition

        diags = [
            LspDiagnostic(
                range=LspRange(LspPosition(0, 0), LspPosition(0, 4)),
                severity=2,
                message="Warning test",
            )
        ]
        issues = HarperDiagnosticsParser.diagnostics_to_issues(diags, "test")
        self.assertEqual(issues[0].severity, "warning")

    def test_parse_severity_info(self):
        """severity=3 → HarperIssue.severity="info"."""
        from phraise.harper_types import LspDiagnostic, LspRange, LspPosition

        diags = [
            LspDiagnostic(
                range=LspRange(LspPosition(0, 0), LspPosition(0, 4)),
                severity=3,
                message="Info test",
            )
        ]
        issues = HarperDiagnosticsParser.diagnostics_to_issues(diags, "test")
        self.assertEqual(issues[0].severity, "info")

    def test_parse_severity_hint(self):
        """severity=4 → HarperIssue.severity="hint" (Harper's default for SpellCheck)."""
        from phraise.harper_types import LspDiagnostic, LspRange, LspPosition

        diags = [
            LspDiagnostic(
                range=LspRange(LspPosition(0, 0), LspPosition(0, 4)),
                severity=4,
                message="Hint test",
            )
        ]
        issues = HarperDiagnosticsParser.diagnostics_to_issues(diags, "test")
        self.assertEqual(issues[0].severity, "hint")

    # ------------------------------------------------------------------ #
    # extract_text_at_range
    # ------------------------------------------------------------------ #

    def test_extract_text_from_range(self):
        """Given original_text="hello world", diagnostic range (0,0)-(0,5),
        extract "hello"."""
        from phraise.harper_types import LspRange, LspPosition

        result = HarperDiagnosticsParser.extract_text_at_range(
            "hello world",
            LspRange(LspPosition(0, 0), LspPosition(0, 5)),
        )
        self.assertEqual(result, "hello")


if __name__ == "__main__":
    unittest.main()
