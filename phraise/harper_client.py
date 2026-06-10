"""High-level Harper LSP client.

Composes lower-level parsers, protocol helpers, and fix-applier utilities
into a convenient API for use by the rest of the application.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from PySide6.QtCore import QObject, QTimer, Signal

from phraise.harper_lsp_manager import HarperLspManager
from phraise.harper_types import (
    HarperDiagnosticsParser,
    HarperFixApplier,
    HarperIssue,
    LspDiagnostic,
)
from phraise.harper_utils import get_harper_binary_path, is_harper_available
from phraise.i18n import t

__all__ = [
    "HarperClient",
    "HarperDiagnosticsParser",
    "HarperFixApplier",
    "LintResult",
]


@dataclass
class LintResult:
    """Result of a Harper grammar check.

    Attributes
    ----------
    success : bool
        ``True`` when the check completed without errors and produced
        grammar issues (if any).  ``False`` when the Harper process
        crashed, timed out, or the binary could not be found.
    issues : list[HarperIssue]
        Grammar issues discovered by Harper.  Empty list when no issues
        were found or when the check failed.
    corrected_text : str
        Text with Harper's auto-applied corrections.  Same as the
        original text when no corrections were applied.
    error : str
        Error message when ``success`` is ``False``.  Empty string on
        success.
    """
    success: bool
    issues: list = field(default_factory=list)
    corrected_text: str = ""
    error: str = ""


class HarperClient(QObject):
    """Central orchestration class for the Harper LSP pipeline.

    Composes ``HarperLspManager``, ``HarperDiagnosticsParser``, and
    ``HarperFixApplier`` to provide a single entry point for checking text
    with the Harper grammar engine.

    Signals
    -------
    finished : Signal(LintResult)
        Emitted when the check completes or fails.
        Carries a :class:`LintResult` with ``success``, ``issues``,
        ``corrected_text``, and ``error`` fields.
    """

    finished = Signal(LintResult)

    # Class-level registry of active instances for cleanup on app exit
    _active_instances: list = []

    def __init__(
        self,
        dialect: str = "American",
        linters: dict | None = None,
        timeout_secs: int = 30,
    ):
        super().__init__()
        self._manager: HarperLspManager | None = None
        self._dialect = dialect
        self._linters = linters or {}
        self._timeout_secs = timeout_secs
        self._current_text = ""
        self._timeout_timer = QTimer(self)
        self._timeout_timer.setSingleShot(True)
        self._timeout_timer.timeout.connect(self._on_client_timeout)
        HarperClient._active_instances.append(self)

    def is_available(self) -> bool:
        return is_harper_available()

    def check_text(self, text: str) -> tuple[list[HarperIssue], str]:
        """Check *text* with Harper and return ``(issues, corrected_text)``.

        This is the main entry point for the floating window.  It starts the
        full LSP pipeline: launch → initialize → send text → wait for
        diagnostics.  Results are delivered asynchronously via the
        :attr:`finished` signal; the immediate return value is a synchronous
        default.
        """
        binary_path = get_harper_binary_path()
        if binary_path is None:
            error_msg = t("harper.error.binary_not_found")
            self.finished.emit(
                LintResult(success=False, issues=[], corrected_text=text, error=error_msg)
            )
            return [], text

        try:
            self._manager = HarperLspManager(
                str(binary_path),
                self._dialect,
                self._linters,
                self._timeout_secs,
            )

            self._manager.diagnostics_ready.connect(self._on_diagnostics)
            self._manager.error_occurred.connect(self._on_error)
            self._manager.process_finished.connect(self._on_finished)

            self._current_text = text
            self._manager.start()
            self._manager.server_ready.connect(
                lambda t=text: self._manager.send_text(t)
            )
            self._timeout_timer.start(self._timeout_secs * 1000)

        except Exception as e:
            self.finished.emit(
                LintResult(success=False, issues=[], corrected_text=text, error=str(e))
            )
            self._manager = None

        return [], text

    @classmethod
    def shutdown_all(cls):
        """Terminate all active Harper subprocesses."""
        for client in list(cls._active_instances):
            try:
                client.shutdown()
            except Exception:
                pass
        cls._active_instances.clear()

    def shutdown(self):
        """Clean shutdown of the Harper subprocess."""
        self._timeout_timer.stop()
        try:
            if self._manager:
                self._manager.stop()
        except Exception:
            pass
        finally:
            self._manager = None
            try:
                HarperClient._active_instances.remove(self)
            except ValueError:
                pass

    # ------------------------------------------------------------------
    # Internal signal handlers
    # ------------------------------------------------------------------

    def _on_diagnostics(self, diagnostics: list[LspDiagnostic]):
        self._timeout_timer.stop()
        issues = HarperDiagnosticsParser.diagnostics_to_issues(
            diagnostics, self._current_text
        )
        corrected = self._current_text
        self.finished.emit(
            LintResult(success=True, issues=issues, corrected_text=corrected, error="")
        )

    def _on_error(self, error_msg: str):
        self._timeout_timer.stop()
        self.finished.emit(
            LintResult(
                success=False, issues=[], corrected_text=self._current_text, error=error_msg
            )
        )

    def _on_client_timeout(self):
        self._on_error(t("harper.error.timeout"))

    def _on_finished(self, exit_code: int):
        self._timeout_timer.stop()
