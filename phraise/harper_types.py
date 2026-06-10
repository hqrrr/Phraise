"""Pure-Python LSP dataclasses and JSON-RPC message builders/parsers.

All types are based on the REAL protocol captured from harper-ls v2.4.0
(see ``phraise/lsp/LSP_PROTOCOL.md``).

No third-party libraries, no Qt, no asyncio.
"""

from __future__ import annotations

from dataclasses import dataclass

from phraise.error_log import write_error

# ---------------------------------------------------------------------------
# LSP Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class LspPosition:
    """0-based position in a text document."""

    line: int
    character: int


@dataclass
class LspRange:
    """A range between two positions in a text document."""

    start: LspPosition
    end: LspPosition


@dataclass
class LspDiagnostic:
    """A diagnostic item from ``textDocument/publishDiagnostics``."""

    range: LspRange
    severity: int  # 1=Error, 2=Warning, 3=Info, 4=Hint
    message: str
    source: str = ""
    code: str = ""
    data: dict | None = None


@dataclass
class LspTextEdit:
    """A text edit to apply to a document."""

    range: LspRange
    newText: str


@dataclass
class LspCodeAction:
    """A code action returned by ``textDocument/codeAction``."""

    title: str
    kind: str = ""
    edit: dict | None = None  # The full ``edit`` dict from the response
    is_spelling_fix: bool = False


@dataclass
class HarperIssue:
    """Internal representation of a single spelling/grammar issue.

    Mirrors the ``grammar_issues`` schema used in ``prompts.py``.
    """

    original: str
    suggestion: str
    reason: str
    severity: str  # "error" | "warning" | "info" | "hint"


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _extract_text_at_range(text: str, range_: LspRange) -> str:
    """Extract the substring of *text* at the given 0-based *range_.

    Supports multi-line ranges by splitting on ``\\n`` and using
    ``.line`` + ``.character`` offsets.
    """
    lines = text.split("\n")

    if range_.start.line == range_.end.line:
        return lines[range_.start.line][
            range_.start.character : range_.end.character
        ]

    parts: list[str] = [
        lines[range_.start.line][range_.start.character :],
        *lines[range_.start.line + 1 : range_.end.line],
        lines[range_.end.line][: range_.end.character],
    ]

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Client → Server Request Builders
# ---------------------------------------------------------------------------


def build_initialize_request(request_id: int = 1) -> dict:
    """Build an ``initialize`` request.

    Matches the exact format described in LSP_PROTOCOL.md §1.
    """
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "method": "initialize",
        "params": {
            "processId": None,
            "rootUri": None,
            "capabilities": {},
            "trace": "off",
        },
    }


def build_initialized_notification() -> dict:
    """Build an ``initialized`` notification (sent after initialize response)."""
    return {
        "jsonrpc": "2.0",
        "method": "initialized",
        "params": {},
    }


def build_did_open_notification(
    text: str,
    uri: str = "file:///phraise.txt",
    language_id: str = "plaintext",
    version: int = 1,
) -> dict:
    """Build a ``textDocument/didOpen`` notification.

    Notifications MUST NOT include an ``id`` field.
    """
    return {
        "jsonrpc": "2.0",
        "method": "textDocument/didOpen",
        "params": {
            "textDocument": {
                "uri": uri,
                "languageId": language_id,
                "version": version,
                "text": text,
            }
        },
    }


def build_shutdown_request(request_id: int = 999) -> dict:
    """Build a ``shutdown`` request.

    CRITICAL:  Do NOT include ``"params": {}`` — harper-ls returns error
    ``-32602``.  The key is simply omitted.
    """
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "method": "shutdown",
    }


def build_exit_notification() -> dict:
    """Build an ``exit`` notification.

    Notifications have no ``id`` field and no ``params``.
    """
    return {
        "jsonrpc": "2.0",
        "method": "exit",
    }


def build_code_action_request(
    request_id: int,
    uri: str,
    diagnostic_range: LspRange,
    diagnostic: LspDiagnostic,
) -> dict:
    """Build a ``textDocument/codeAction`` request for a single diagnostic.

    The ``context.diagnostics`` array carries the diagnostic so the server
    knows which issue to provide actions for.
    """
    diag_dict = {
        "code": diagnostic.code,
        "range": {
            "start": {"line": diagnostic.range.start.line,
                      "character": diagnostic.range.start.character},
            "end": {"line": diagnostic.range.end.line,
                    "character": diagnostic.range.end.character},
        },
        "severity": diagnostic.severity,
        "source": diagnostic.source,
        "message": diagnostic.message,
    }

    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "method": "textDocument/codeAction",
        "params": {
            "textDocument": {"uri": uri},
            "range": {
                "start": {"line": diagnostic_range.start.line,
                          "character": diagnostic_range.start.character},
                "end": {"line": diagnostic_range.end.line,
                        "character": diagnostic_range.end.character},
            },
            "context": {
                "diagnostics": [diag_dict],
            },
        },
    }


# ---------------------------------------------------------------------------
# Client Response Builders (for server-initiated requests)
# ---------------------------------------------------------------------------


def build_workspace_config_response(request_id: int) -> dict:
    """Build a response to the server's ``workspace/configuration`` request.

    Returns an empty configuration array (``[]``).
    """
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "result": [],
    }


def build_register_capability_response(request_id: int) -> dict:
    """Build a response to the server's ``client/registerCapability`` request.

    Returns ``null`` to acknowledge registration.
    """
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "result": None,
    }


# ---------------------------------------------------------------------------
# Response / Notification Parsers
# ---------------------------------------------------------------------------


def parse_publish_diagnostics(json_data: dict) -> list[LspDiagnostic]:
    """Parse a ``textDocument/publishDiagnostics`` notification.

    Returns an empty list if the method doesn't match or no diagnostics are
    present.
    """
    if json_data.get("method") != "textDocument/publishDiagnostics":
        return []

    raw_diags: list[dict] = (json_data.get("params") or {}).get("diagnostics") or []
    result: list[LspDiagnostic] = []

    for d in raw_diags:
        r = d.get("range", {})
        start = r.get("start", {})
        end = r.get("end", {})

        result.append(
            LspDiagnostic(
                range=LspRange(
                    start=LspPosition(
                        line=start.get("line", 0),
                        character=start.get("character", 0),
                    ),
                    end=LspPosition(
                        line=end.get("line", 0),
                        character=end.get("character", 0),
                    ),
                ),
                severity=d.get("severity", 4),
                message=d.get("message", ""),
                source=d.get("source", ""),
                code=d.get("code", ""),
            )
        )

    return result


def parse_code_action_response(json_data: dict) -> list[LspCodeAction]:
    """Parse a ``textDocument/codeAction`` response.

    Each action with ``kind == "quickfix"`` that contains an ``edit`` is
    marked as a spelling fix.
    """
    raw_actions: list[dict] = json_data.get("result") or []
    result: list[LspCodeAction] = []

    for a in raw_actions:
        kind = a.get("kind", "")
        edit = a.get("edit")
        is_spelling = kind == "quickfix" and edit is not None

        result.append(
            LspCodeAction(
                title=a.get("title", ""),
                kind=kind,
                edit=edit,
                is_spelling_fix=is_spelling,
            )
        )

    return result


# ---------------------------------------------------------------------------
# Format Converters
# ---------------------------------------------------------------------------


_SEVERITY_MAP: dict[int, str] = {
    1: "error",
    2: "warning",
    3: "info",
    4: "hint",
}


def diagnostics_to_harper_issues(
    diagnostics: list[LspDiagnostic],
    original_text: str,
) -> list[HarperIssue]:
    """Convert LSP diagnostics into internal ``HarperIssue`` objects.

    The ``suggestion`` field is left empty (``""``) — it will be populated
    later by the code-action fix applier.
    """
    issues: list[HarperIssue] = []

    for d in diagnostics:
        severity_str = _SEVERITY_MAP.get(d.severity, "hint")
        original = _extract_text_at_range(original_text, d.range)

        issues.append(
            HarperIssue(
                original=original,
                suggestion="",
                reason=d.message,
                severity=severity_str,
            )
        )

    return issues


class HarperDiagnosticsParser:
    """Parse LSP ``publishDiagnostics`` notifications into ``HarperIssue`` objects."""

    @staticmethod
    def parse_publish_diagnostics(raw_json: dict) -> list[LspDiagnostic]:
        """Extract ``LspDiagnostic`` list from a ``publishDiagnostics`` notification.

        Returns empty list if:
        - Not a valid JSON-RPC 2.0 message
        - ``method`` is not ``textDocument/publishDiagnostics``
        - ``params`` or ``diagnostics`` are missing
        """
        if not isinstance(raw_json, dict):
            return []
        if raw_json.get("jsonrpc") != "2.0":
            return []
        if raw_json.get("method") != "textDocument/publishDiagnostics":
            return []

        params = raw_json.get("params", {})
        if not isinstance(params, dict):
            return []

        raw_diagnostics = params.get("diagnostics", [])
        if not isinstance(raw_diagnostics, list):
            return []

        diagnostics: list[LspDiagnostic] = []
        for diag in raw_diagnostics:
            r = diag.get("range", {})
            if not r:
                write_error(
                    KeyError("range"),
                    f"Malformed diagnostic missing 'range': {diag}",
                )
                continue

            start = r.get("start", {})
            end = r.get("end", {})

            d = LspDiagnostic(
                range=LspRange(
                    start=LspPosition(
                        line=start.get("line", 0),
                        character=start.get("character", 0),
                    ),
                    end=LspPosition(
                        line=end.get("line", 0),
                        character=end.get("character", 0),
                    ),
                ),
                severity=diag.get("severity", 4),
                message=diag.get("message", ""),
                source=diag.get("source", ""),
                code=diag.get("code", ""),
            )
            diagnostics.append(d)

        return diagnostics

    @staticmethod
    def diagnostics_to_issues(diagnostics: list[LspDiagnostic], original_text: str) -> list[HarperIssue]:
        """Convert ``LspDiagnostic`` list to ``HarperIssue`` list.

        Severity mapping: 1 | ``"error"``, 2 | ``"warning"``, 3 | ``"info"``,
        4 | ``"hint"``, unknown | ``"hint"``.
        Suggestion starts empty (filled later by the fix applier).
        """
        severity_map = {1: "error", 2: "warning", 3: "info", 4: "hint"}

        issues: list[HarperIssue] = []
        for diag in diagnostics:
            original = _extract_text_at_range(original_text, diag.range)
            severity = severity_map.get(diag.severity, "hint")
            issues.append(
                HarperIssue(
                    original=original,
                    suggestion="",
                    reason=diag.message,
                    severity=severity,
                )
            )

        return issues

    @staticmethod
    def extract_text_at_range(text: str, range_: LspRange) -> str:
        return _extract_text_at_range(text, range_)


# ---------------------------------------------------------------------------
# Fix Applier
# ---------------------------------------------------------------------------


class HarperFixApplier:
    """Apply LSP text edits to produce corrected text.

    CRITICAL: Fixes are applied in REVERSE offset order (highest
    start.character first) to avoid offset invalidation when multiple
    fixes modify the same document.
    """

    @staticmethod
    def apply_fixes(original_text: str, text_edits: list) -> str:
        """Apply multiple LspTextEdits to produce corrected text.

        Sorts edits by ``range.start.character`` DESCENDING, then applies
        each.  Skips overlapping fixes (if a fix is fully contained within
        another fix's range).  Skips fixes where ``newText`` is empty.
        """
        if not text_edits:
            return original_text

        sorted_edits = sorted(
            text_edits,
            key=lambda e: e.range.start.character,
            reverse=True,
        )

        all_ranges = [
            (e.range.start.character, e.range.end.character)
            for e in sorted_edits
        ]

        result = original_text

        for i, edit in enumerate(sorted_edits):
            start, end = all_ranges[i]
            new_text = edit.newText

            if not new_text:
                continue

            if any(
                start >= other_start and end <= other_end
                for j, (other_start, other_end) in enumerate(all_ranges)
                if j != i
            ):
                continue

            result = result[:start] + new_text + result[end:]

        return result

    @staticmethod
    def apply_single_fix(
        text: str, start_char: int, end_char: int, replacement: str
    ) -> str:
        """Apply a single text replacement."""
        return text[:start_char] + replacement + text[end_char:]
