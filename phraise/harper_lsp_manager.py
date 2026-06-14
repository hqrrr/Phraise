"""HarperLspManager — QProcess-based LSP lifecycle manager for harper-ls.

Launches and manages the ``harper-ls`` binary as a QProcess subprocess,
communicating via stdin/stdout using JSON-RPC with Content-Length framing.
"""

from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import QObject, QProcess, QTimer, Signal

from phraise.harper_types import LspPosition, LspRange, LspTextEdit, build_did_open_notification, build_exit_notification, build_initialized_notification, build_initialize_request, build_register_capability_response, build_shutdown_request, build_workspace_config_response, parse_publish_diagnostics


class HarperLspManager(QObject):
    """Manages the harper-ls LSP subprocess lifecycle via QProcess.

    Signals
    -------
    diagnostics_ready : list[LspDiagnostic]
        Emitted when diagnostics are received from the language server.
    error_occurred : str
        Emitted when a process error or timeout occurs.
    process_finished : int
        Emitted when the LSP subprocess exits (carries exit code).
    """

    diagnostics_ready = Signal(list)  # list[LspDiagnostic]
    code_actions_ready = Signal(int, list)  # request_id, list[LspTextEdit]
    error_occurred = Signal(str)  # error message
    process_finished = Signal(int)  # exit code
    server_ready = Signal()  # emitted after initialize→initialized handshake

    def __init__(
        self,
        binary_path: str | Path,
        dialect: str = "American",
        linters: dict | None = None,
        timeout_secs: int = 30,
    ) -> None:
        """Initialise the manager.

        Parameters
        ----------
        binary_path : str | Path
            Path to the ``harper-ls`` executable.
        dialect : str
            Harper dialect setting (default ``"American"``).
        linters : dict | None
            Harper linter configuration (default ``None``).
        timeout_secs : int
            Seconds before a pending request times out (default ``30``).
        """
        super().__init__()
        self._binary_path = str(binary_path)
        self._process = QProcess(self)
        self._request_id = 0
        self._initialize_request_id = 0
        self._initialized = False
        self._buffer = b""
        self._timeout_secs = timeout_secs
        self._pending_request = False
        self._timeout_timer = QTimer(self)
        self._timeout_timer.setSingleShot(True)

        # Connect QProcess signals
        self._process.started.connect(self._on_process_started)
        self._process.errorOccurred.connect(self._on_process_error)
        self._process.finished.connect(self._on_process_finished)
        self._process.readyReadStandardOutput.connect(self._on_stdout_ready)
        self._timeout_timer.timeout.connect(self._on_timeout)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Launch ``harper-ls`` via QProcess with ``--stdio`` flag."""
        self._process.start(self._binary_path, ["--stdio"])

    def initialize(self) -> None:
        """Send LSP ``initialize`` request.

        The ``initialized`` notification is sent automatically by the stdout
        reader when the server's response is received.  Callers should NOT
        invoke this method directly during normal operation — the startup
        flow is driven by ``QProcess.started`` → ``_on_process_started``.
        """
        self._request_id += 1
        self._initialize_request_id = self._request_id
        msg = build_initialize_request(self._request_id)
        self._write_message(msg)

    def send_text(self, text: str, language_id: str = "plaintext") -> None:
        """Send ``textDocument/didOpen`` notification with the given text.

        Guards against writing to a process that is not yet running.
        Starts the response timeout timer.
        """
        if self._process.state() != QProcess.Running:
            return
        msg = build_did_open_notification(text, language_id=language_id)
        self._write_message(msg)
        self._pending_request = True
        self._timeout_timer.start(self._timeout_secs * 1000)

    def get_code_actions(self, uri: str, diagnostic_range: LspRange) -> int:
        """Send ``textDocument/codeAction`` request for a diagnostic range.

        Parameters
        ----------
        uri : str
            The document URI (e.g. ``file:///phraise.txt``).
        diagnostic_range : LspRange
            The range of the diagnostic to request actions for.

        Returns
        -------
        int
            The request ID assigned to this codeAction request.
        """
        self._request_id += 1
        msg = {
            "jsonrpc": "2.0",
            "id": self._request_id,
            "method": "textDocument/codeAction",
            "params": {
                "textDocument": {"uri": uri},
                "range": {
                    "start": {
                        "line": diagnostic_range.start.line,
                        "character": diagnostic_range.start.character,
                    },
                    "end": {
                        "line": diagnostic_range.end.line,
                        "character": diagnostic_range.end.character,
                    },
                },
                "context": {"diagnostics": []},
            },
        }
        self._write_message(msg)
        return self._request_id

    def stop(self) -> None:
        """Shut down the LSP session and terminate the subprocess.

        Sends ``shutdown`` + ``exit``, terminates the QProcess, waits up
        to 3 seconds for it to finish, then disconnects all signals.
        Idempotent — calling ``stop()`` multiple times is safe.
        """
        self._timeout_timer.stop()

        # Send shutdown request
        self._request_id += 1
        self._write_message(build_shutdown_request(self._request_id))
        # Send exit notification
        self._write_message(build_exit_notification())
        # Terminate and wait
        if self._process.state() != QProcess.NotRunning:
            self._process.terminate()
            self._process.waitForFinished(3000)
        for signal_name, slot in (
            ("started", self._on_process_started),
            ("errorOccurred", self._on_process_error),
            ("finished", self._on_process_finished),
            ("readyReadStandardOutput", self._on_stdout_ready),
        ):
            try:
                getattr(self._process, signal_name).disconnect(slot)
            except (RuntimeError, TypeError):
                pass

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _write_message(self, msg: dict) -> None:
        """Write a JSON-RPC message with Content-Length framing.

        Format: ``Content-Length: N\\r\\n\\r\\n{json_body}``
        """
        body = json.dumps(msg, ensure_ascii=False).encode("utf-8")
        header = f"Content-Length: {len(body)}\r\n\r\n".encode("ascii")
        self._process.write(header + body)

    def _on_stdout_ready(self) -> None:
        """Read available stdout data from the LSP subprocess.

        Appends all newly-available bytes to ``self._buffer`` and
        attempts to decode complete Content-Length frames.
        """
        data = bytes(self._process.readAllStandardOutput())
        if not data:
            return
        self._buffer += data
        self._decode_frames()

    def _decode_frames(self) -> None:
        """Decode complete LSP frames from ``self._buffer``.

        Parses Content-Length headers, extracts JSON bodies, and for
        ``textDocument/publishDiagnostics`` notifications emits the
        ``diagnostics_ready`` signal.

        Handles:
        - Single frame in one chunk
        - Split header/body across multiple chunks
        - Multiple frames in one chunk
        """
        while True:
            idx = self._buffer.find(b"\r\n\r\n")
            if idx == -1:
                return  # header not yet complete

            header_part = self._buffer[:idx]
            content_length = 0
            for line in header_part.split(b"\r\n"):
                if line.lower().startswith(b"content-length:"):
                    try:
                        content_length = int(line.split(b":", 1)[1].strip())
                    except ValueError:
                        pass  # malformed header — discard and continue

            if content_length <= 0:
                # No valid Content-Length; skip past the separator
                self._buffer = self._buffer[idx + 4:]
                continue

            body_start = idx + 4
            body_end = body_start + content_length

            if len(self._buffer) < body_end:
                return  # body not fully received yet

            body = self._buffer[body_start:body_end]
            self._buffer = self._buffer[body_end:]

            try:
                msg = json.loads(body)
            except json.JSONDecodeError:
                continue  # skip malformed JSON

            # -- Server requests that block diagnostics until responded to --
            req_id = msg.get("id")
            method = msg.get("method")
            is_request = req_id is not None and method is not None

            if is_request and method == "workspace/configuration":
                self._write_message(build_workspace_config_response(req_id))
                continue
            if is_request and method == "client/registerCapability":
                self._write_message(build_register_capability_response(req_id))
                continue

            # -- Response to our initialize request --
            if req_id == self._initialize_request_id and "result" in msg and not self._initialized:
                self._write_message(build_initialized_notification())
                self._initialized = True
                self.server_ready.emit()

            # -- Response to codeAction request --
            if req_id is not None and "result" in msg and "method" not in msg and req_id != self._initialize_request_id:
                text_edits = _parse_code_action_result(msg.get("result", []))
                self.code_actions_ready.emit(req_id, text_edits)

            # -- Diagnostics notification --
            if msg.get("method") == "textDocument/publishDiagnostics":
                diags = parse_publish_diagnostics(msg)
                self.diagnostics_ready.emit(diags)

    # ------------------------------------------------------------------
    # Signal handlers
    # ------------------------------------------------------------------

    def _on_process_started(self) -> None:
        """Send the LSP ``initialize`` request as soon as the process starts."""
        self._request_id += 1
        self._initialize_request_id = self._request_id
        msg = build_initialize_request(self._request_id)
        self._write_message(msg)

    def _on_process_error(self, error: QProcess.ProcessError) -> None:
        """Emit ``error_occurred`` when the subprocess encounters an error."""
        msg = f"Harper LSP process error: {error}"
        self.error_occurred.emit(msg)

    def _on_process_finished(self, exit_code: int) -> None:
        """Emit ``process_finished`` when the subprocess exits."""
        self.process_finished.emit(exit_code)

    def _on_timeout(self) -> None:
        """Emit ``error_occurred`` when a pending request times out."""
        self.error_occurred.emit("Harper LSP request timeout")


# ------------------------------------------------------------------
# Module-level helpers
# ------------------------------------------------------------------


def _parse_code_action_result(result: list) -> list[LspTextEdit]:
    """Parse a ``textDocument/codeAction`` response result into ``LspTextEdit`` list.

    Takes ``result[0].edit.changes`` for the first URI key, converts each
    ``{newText, range}`` dict into an ``LspTextEdit``.  Returns an empty
    list when the result is empty, malformed, or contains no edits.
    """
    if not isinstance(result, list) or len(result) == 0:
        return []

    first_action = result[0]
    if not isinstance(first_action, dict):
        return []

    edit = first_action.get("edit")
    if not isinstance(edit, dict):
        return []

    changes = edit.get("changes")
    if not isinstance(changes, dict):
        return []

    for _uri, uri_changes in changes.items():
        if not isinstance(uri_changes, list):
            continue
        text_edits: list[LspTextEdit] = []
        for change in uri_changes:
            if not isinstance(change, dict):
                continue
            r = change.get("range", {})
            start = r.get("start", {})
            end = r.get("end", {})
            text_edits.append(
                LspTextEdit(
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
                    newText=change.get("newText", ""),
                )
            )
        return text_edits

    return []
