"""HarperLspManager — QProcess-based LSP lifecycle manager for harper-ls.

Launches and manages the ``harper-ls`` binary as a QProcess subprocess,
communicating via stdin/stdout using JSON-RPC with Content-Length framing.
"""

from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import QObject, QProcess, QTimer, Signal

from phraise.harper_types import LspRange, build_did_open_notification, build_exit_notification, build_initialized_notification, build_initialize_request, build_shutdown_request


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
    error_occurred = Signal(str)  # error message
    process_finished = Signal(int)  # exit code

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
        self._buffer = b""
        self._timeout_secs = timeout_secs
        self._pending_request = False
        self._timeout_timer = QTimer(self)
        self._timeout_timer.setSingleShot(True)

        # Connect QProcess signals
        self._process.started.connect(self._on_process_started)
        self._process.errorOccurred.connect(self._on_process_error)
        self._process.finished.connect(self._on_process_finished)
        self._timeout_timer.timeout.connect(self._on_timeout)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Launch ``harper-ls`` via QProcess with ``--stdio`` flag."""
        self._process.start(self._binary_path, ["--stdio"])

    def initialize(self) -> None:
        """Send LSP ``initialize`` request and ``initialized`` notification.

        Sends the ``initialize`` request first, then immediately sends the
        ``initialized`` notification.  In the full LSP handshake (Task 7-8),
        the notification should be sent after receiving the server's
        ``initialize`` response — the current implementation wires the call.
        """
        self._request_id += 1
        msg = build_initialize_request(self._request_id)
        self._write_message(msg)
        self._write_message(build_initialized_notification())

    def send_text(self, text: str, language_id: str = "plaintext") -> None:
        """Send ``textDocument/didOpen`` notification with the given text.

        Starts the response timeout timer.
        """
        msg = build_did_open_notification(text, language_id=language_id)
        self._write_message(msg)
        self._pending_request = True
        self._timeout_timer.start(self._timeout_secs * 1000)

    def get_code_actions(self, uri: str, diagnostic_range: LspRange) -> None:
        """Send ``textDocument/codeAction`` request for a diagnostic range.

        Parameters
        ----------
        uri : str
            The document URI (e.g. ``file:///phraise.txt``).
        diagnostic_range : LspRange
            The range of the diagnostic to request actions for.
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

    def stop(self) -> None:
        """Shut down the LSP session and terminate the subprocess.

        Sends ``shutdown`` + ``exit``, terminates the QProcess, waits up
        to 3 seconds for it to finish, then disconnects all signals.
        """
        # Send shutdown request
        self._request_id += 1
        self._write_message(build_shutdown_request(self._request_id))
        # Send exit notification
        self._write_message(build_exit_notification())
        # Terminate and wait
        if self._process.state() != QProcess.NotRunning:
            self._process.terminate()
            self._process.waitForFinished(3000)
        # Disconnect signals
        self._process.started.disconnect(self._on_process_started)
        self._process.errorOccurred.disconnect(self._on_process_error)
        self._process.finished.disconnect(self._on_process_finished)

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

    # ------------------------------------------------------------------
    # Signal handlers
    # ------------------------------------------------------------------

    def _on_process_started(self) -> None:
        """Callback when the LSP subprocess starts (no-op)."""

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
