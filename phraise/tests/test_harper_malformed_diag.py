# PhrAIse - AI writing assistant
# License: GNU GPLv3
# GitHub: https://github.com/hqrrr/Phraise
# Author: hqrrr
#
# Description: Unit tests for harper malformed diag.
"""Tests: ``HarperDiagnosticsParser.parse_publish_diagnostics`` handles
malformed diagnostic JSON without crashing.

If a diagnostic dict is missing the ``range``, ``start``, or ``end`` keys,
the parser must:

1. NOT raise ``KeyError`` (defensive ``.get()`` chains instead of direct access)
2. Log the malformed entry via ``write_error()`` for debugging
3. Gracefully skip the broken diagnostic and continue with valid ones

Regression: valid diagnostics must still parse correctly.
"""

import unittest

from phraise.harper_types import HarperDiagnosticsParser


class TestMalformedDiagnostics(unittest.TestCase):
    """``HarperDiagnosticsParser.parse_publish_diagnostics`` malformed JSON."""

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #

    def _make_envelope(self, diagnostics: list) -> dict:
        """Wrap diagnostics in a valid JSON-RPC ``publishDiagnostics`` envelope."""
        return {
            "jsonrpc": "2.0",
            "method": "textDocument/publishDiagnostics",
            "params": {
                "uri": "file:///test.txt",
                "diagnostics": diagnostics,
            },
        }

    # ------------------------------------------------------------------ #
    # Malformed — should NOT crash, should be skipped
    # ------------------------------------------------------------------ #

    def test_missing_range_key_does_not_crash(self):
        """Diagnostic without ``range`` key → skipped (no KeyError)."""
        raw = self._make_envelope([
            {
                "code": "SpellCheck",
                "severity": 4,
                "source": "Harper",
                "message": "Missing range",
            },
        ])
        result = HarperDiagnosticsParser.parse_publish_diagnostics(raw)
        self.assertEqual(result, [])

    def test_missing_start_key_does_not_crash(self):
        """Diagnostic with ``range`` but no ``start`` → uses (0,0) defaults."""
        raw = self._make_envelope([
            {
                "code": "SpellCheck",
                "range": {"end": {"line": 0, "character": 4}},
                "severity": 4,
                "source": "Harper",
                "message": "Missing start",
            },
        ])
        result = HarperDiagnosticsParser.parse_publish_diagnostics(raw)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].range.start.line, 0)
        self.assertEqual(result[0].range.start.character, 0)

    def test_missing_end_key_does_not_crash(self):
        """Diagnostic with ``range`` but no ``end`` → uses (0,0) defaults."""
        raw = self._make_envelope([
            {
                "code": "SpellCheck",
                "range": {"start": {"line": 0, "character": 0}},
                "severity": 4,
                "source": "Harper",
                "message": "Missing end",
            },
        ])
        result = HarperDiagnosticsParser.parse_publish_diagnostics(raw)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].range.end.line, 0)
        self.assertEqual(result[0].range.end.character, 0)

    def test_malformed_skipped_valid_parsed(self):
        """Mixed: malformed diagnostic skipped, valid one still parsed."""
        raw = self._make_envelope([
            {
                "code": "SpellCheck",
                "severity": 4,
                "source": "Harper",
                "message": "Missing range — should be skipped",
            },
            {
                "code": "SpellCheck",
                "range": {
                    "start": {"line": 0, "character": 0},
                    "end": {"line": 0, "character": 4},
                },
                "severity": 4,
                "source": "Harper",
                "message": "Valid diagnostic",
            },
        ])
        result = HarperDiagnosticsParser.parse_publish_diagnostics(raw)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].message, "Valid diagnostic")

    # ------------------------------------------------------------------ #
    # Regression — valid input still works
    # ------------------------------------------------------------------ #

    def test_valid_diagnostic_still_parsed(self):
        """Fully valid diagnostic parses correctly (regression)."""
        raw = self._make_envelope([
            {
                "code": "SpellCheck",
                "range": {
                    "start": {"line": 0, "character": 0},
                    "end": {"line": 0, "character": 4},
                },
                "severity": 4,
                "source": "Harper",
                "message": "Did you mean to spell `helo` this way?",
            },
        ])
        result = HarperDiagnosticsParser.parse_publish_diagnostics(raw)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].code, "SpellCheck")
        self.assertEqual(result[0].range.start.line, 0)
        self.assertEqual(result[0].range.start.character, 0)
        self.assertEqual(result[0].range.end.line, 0)
        self.assertEqual(result[0].range.end.character, 4)

    def test_empty_diagnostics_list(self):
        """Empty diagnostics list returns empty list."""
        raw = self._make_envelope([])
        result = HarperDiagnosticsParser.parse_publish_diagnostics(raw)
        self.assertEqual(result, [])

    def test_non_dict_jsonrpc_returns_empty(self):
        """Non-dict input returns empty list."""
        result = HarperDiagnosticsParser.parse_publish_diagnostics("not a dict")
        self.assertEqual(result, [])

    def test_wrong_jsonrpc_version_returns_empty(self):
        """Wrong ``jsonrpc`` version returns empty list."""
        raw = {
            "jsonrpc": "1.0",
            "method": "textDocument/publishDiagnostics",
            "params": {"diagnostics": []},
        }
        result = HarperDiagnosticsParser.parse_publish_diagnostics(raw)
        self.assertEqual(result, [])


if __name__ == "__main__":
    unittest.main()
