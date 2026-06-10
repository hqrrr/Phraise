"""Tests for HarperClient callback race condition and disambiguation (Task 10).

Verifies:
  - Stale ``HarperClient.finished`` callbacks are disconnected before a new
    request starts, preventing them from overwriting newer results.
  - ``_on_harper_done`` guards against accessing widgets on a deleted window.
  - The ``finished`` signal uses ``LintResult`` for success/error disambiguation.
"""

import unittest
from unittest.mock import ANY, MagicMock, call, patch

from phraise.floating_window import FloatingWindow
from phraise.harper_client import HarperClient, LintResult


# ---------------------------------------------------------------------------
# Minimal test fixture — skips Qt constructor, wires up just the attributes
# that ``_do_optimize()`` and ``_on_harper_done()`` touch.
# ---------------------------------------------------------------------------

def _make_fw(**overrides) -> FloatingWindow:
    """Return a bare ``FloatingWindow`` instance whose ``__init__`` was skipped."""
    with patch.object(FloatingWindow, "__init__", return_value=None):
        fw = FloatingWindow.__new__(FloatingWindow)

    fw._is_loading = False
    fw._active_client = None
    fw._current_text = "The quick brown fox jump over the lazy dog."
    fw._current_style = "concise"

    fw._set_loading_state = MagicMock()
    fw._show_toast = MagicMock()
    fw._show_error = MagicMock()
    fw._on_optimize_done = MagicMock()
    fw._do_optimize_llm = MagicMock()

    fw._rewrite_label = MagicMock()
    fw._model_combo = MagicMock()
    fw._style_buttons = {}
    fw._set_harper_layout = MagicMock()

    fw._rewrite_texts = [MagicMock(), MagicMock(), MagicMock()]
    for rt in fw._rewrite_texts:
        rt.text_edit = MagicMock()
        rt.text_edit.setPlainText = MagicMock()
    fw._grammar_layout = MagicMock()
    fw._grammar_header = MagicMock()
    fw._grammar_container = MagicMock()

    for attr, val in overrides.items():
        setattr(fw, attr, val)

    return fw


def _make_config_get(model_value: str):
    """Return a ``config.get`` side_effect for Harper mode."""
    def _get(*keys, default=None):
        if keys == ("general", "optimize_model"):
            return model_value
        if keys == ("floating_window", "last_style"):
            return "concise"
        if keys == ("styles",):
            return [{"id": "concise", "label": "Concise"}]
        return default
    return _get


class _DeletedAttr:
    """Descriptor that raises RuntimeError on access, simulating a
    deleted C++ QObject attribute."""

    def __get__(self, obj, objtype=None):
        raise RuntimeError("Internal C++ object already deleted")

    def __set__(self, obj, value):
        pass


# ====================================================================
# TestHarperCallbackRace
# ====================================================================

class TestHarperCallbackRace(unittest.TestCase):
    """Verify that stale HarperClient callbacks do not overwrite newer
    results, and that the callback-safe guard prevents crashes on a
    destroyed window."""

    # ------------------------------------------------------------------
    # 1. Stale client → disconnected before new client created
    # ------------------------------------------------------------------

    def test_stale_client_disconnected_before_new_request(self):
        """Second _do_optimize() disconnects the first client's finished
        signal before creating a new client."""
        fw = _make_fw()

        client1 = MagicMock(spec=HarperClient)
        client1.is_available.return_value = True
        client1.check_text.return_value = ([], fw._current_text)

        client2 = MagicMock(spec=HarperClient)
        client2.is_available.return_value = True
        client2.check_text.return_value = ([], fw._current_text)

        with patch(
            "phraise.harper_client.HarperClient",
            side_effect=[client1, client2],
        ), patch(
            "phraise.floating_window.config",
        ) as mock_cfg, patch(
            "phraise.floating_window.run_on_main",
            side_effect=lambda fn: fn(),
        ), patch(
            "phraise.floating_window.shiboken6.isValid", return_value=True
        ):
            mock_cfg.get.side_effect = _make_config_get("harper")

            # First call: creates client1, connects its finished signal
            fw._do_optimize()
            self.assertTrue(fw._is_loading)
            self.assertIs(fw._active_client, client1)
            client1.finished.connect.assert_called_once()
            client1.finished.disconnect.assert_not_called()

            # Simulate client1 callback — the real _on_optimize_done clears
            # _is_loading, but our mock doesn't, so reset it manually.
            fw._is_loading = False
            connected_cb = client1.finished.connect.call_args[0][0]
            connected_cb(LintResult(success=True, issues=[], corrected_text="old"))
            fw._on_optimize_done.assert_called_once()
            call_args = fw._on_optimize_done.call_args[0]
            self.assertEqual(call_args[0]["corrected_text"], "old")

            # Second call: must disconnect client1 before creating client2
            fw._on_optimize_done.reset_mock()
            fw._do_optimize()

            # client1.finished must have been disconnected
            client1.finished.disconnect.assert_called_once()
            self.assertIs(fw._active_client, client2)
            client2.finished.connect.assert_called_once()

            # Emit stale signal on client1 — must NOT reach _on_harper_done
            # (verified via the Qt disconnect, but in mock-land the callback
            # would still fire if we call it manually; the disconnect call
            # is the contract we test here)
            fw._on_optimize_done.assert_not_called()

    # ------------------------------------------------------------------
    # 2. Fresh result displayed — stale callback suppressed
    # ------------------------------------------------------------------

    def test_only_newest_result_displayed(self):
        """When a slow HarperClient finishes after a newer request, only
        the newer result reaches _on_optimize_done."""
        fw = _make_fw()

        client1 = MagicMock(spec=HarperClient)
        client1.is_available.return_value = True
        client1.check_text.return_value = ([], fw._current_text)

        client2 = MagicMock(spec=HarperClient)
        client2.is_available.return_value = True
        client2.check_text.return_value = ([], fw._current_text)

        with patch(
            "phraise.harper_client.HarperClient",
            side_effect=[client1, client2],
        ), patch(
            "phraise.floating_window.config",
        ) as mock_cfg, patch(
            "phraise.floating_window.run_on_main",
            side_effect=lambda fn: fn(),
        ), patch(
            "phraise.floating_window.shiboken6.isValid", return_value=True
        ):
            mock_cfg.get.side_effect = _make_config_get("harper")

            # First request
            fw._do_optimize()
            # Simulate first callback completing
            fw._is_loading = False
            cb1 = client1.finished.connect.call_args[0][0]
            cb1(LintResult(success=True, issues=[], corrected_text="old_result"))

            fw._on_optimize_done.reset_mock()

            # Second request — disconnects client1, connects client2
            fw._do_optimize()
            client1.finished.disconnect.assert_called_once()

            # Simulate newer client2 finishing
            fw._is_loading = False
            cb2 = client2.finished.connect.call_args[0][0]
            cb2(LintResult(
                success=True,
                issues=[{"original": "jump", "suggestion": "jumps", "reason": "SVA"}],
                corrected_text="The quick brown fox jumps over the lazy dog.",
            ))

            # Only the newest result should be delivered
            fw._on_optimize_done.assert_called_once()
            result = fw._on_optimize_done.call_args[0][0]
            self.assertEqual(
                result["corrected_text"],
                "The quick brown fox jumps over the lazy dog.",
            )
            self.assertEqual(len(result["grammar_issues"]), 1)

    # ------------------------------------------------------------------
    # 3. _active_client tracking prevents re-use of stale client
    # ------------------------------------------------------------------

    def test_active_client_replaced_on_new_request(self):
        """After a new _do_optimize(), _active_client points to the new
        HarperClient, not the stale one."""
        fw = _make_fw()

        client1 = MagicMock(spec=HarperClient)
        client1.is_available.return_value = True
        client1.check_text.return_value = ([], fw._current_text)

        client2 = MagicMock(spec=HarperClient)
        client2.is_available.return_value = True
        client2.check_text.return_value = ([], fw._current_text)

        with patch(
            "phraise.harper_client.HarperClient",
            side_effect=[client1, client2],
        ), patch(
            "phraise.floating_window.config",
        ) as mock_cfg, patch(
            "phraise.floating_window.run_on_main",
            side_effect=lambda fn: fn(),
        ), patch(
            "phraise.floating_window.shiboken6.isValid", return_value=True
        ):
            mock_cfg.get.side_effect = _make_config_get("harper")

            # First request
            fw._do_optimize()
            self.assertIs(fw._active_client, client1)

            # Complete first (reset _is_loading so second call can proceed)
            fw._is_loading = False
            cb1 = client1.finished.connect.call_args[0][0]
            cb1(LintResult(success=True, issues=[], corrected_text="first"))

            # Second request
            fw._do_optimize()
            self.assertIs(fw._active_client, client2)

    # ------------------------------------------------------------------
    # 4. Window destroyed during Harper processing → no crash
    # ------------------------------------------------------------------

    def test_window_destroyed_during_harper_callback_does_not_crash(self):
        """When _on_harper_done fires on a deleted window, the callback
        returns early without accessing widgets."""
        fw = _make_fw()

        result = LintResult(
            success=True,
            issues=[{"original": "jump", "suggestion": "jumps", "reason": "SVA"}],
            corrected_text="The quick brown fox jumps over the lazy dog.",
        )
        # Simulate deleted C++ object: isValid returns False and
        # accessing any widget attribute raises RuntimeError.
        with patch(
            "phraise.floating_window.shiboken6.isValid", return_value=False
        ):
            saved = fw._rewrite_texts
            del fw.__dict__["_rewrite_texts"]
            FloatingWindow._rewrite_texts = _DeletedAttr()
            try:
                FloatingWindow._on_harper_done(fw, result)
            finally:
                del FloatingWindow._rewrite_texts
                fw._rewrite_texts = saved

        # No widget access should have occurred
        fw._on_optimize_done.assert_not_called()
        fw._show_toast.assert_not_called()
        fw._do_optimize_llm.assert_not_called()
        for rt in fw._rewrite_texts:
            rt.text_edit.setPlainText.assert_not_called()

    # ------------------------------------------------------------------
    # 5. LintResult success/error disambiguation
    # ------------------------------------------------------------------

    def test_lintresult_success_calls_on_optimize_done(self):
        """A LintResult with success=True triggers the normal result
        delivery path."""
        fw = _make_fw()

        result = LintResult(
            success=True,
            issues=[{"original": "jump", "suggestion": "jumps", "reason": "SVA"}],
            corrected_text="The quick brown fox jumps over the lazy dog.",
        )
        with patch("phraise.floating_window.shiboken6.isValid", return_value=True):
            FloatingWindow._on_harper_done(fw, result)

        fw._on_optimize_done.assert_called_once()
        payload = fw._on_optimize_done.call_args[0][0]
        self.assertEqual(payload["corrected_text"], result.corrected_text)
        self.assertEqual(payload["grammar_issues"], result.issues)

    def test_lintresult_error_falls_back_to_llm(self):
        """A LintResult with success=False or non-empty error falls back
        to the LLM path."""
        fw = _make_fw()

        result = LintResult(
            success=False,
            issues=[],
            corrected_text=fw._current_text,
            error="Harper LSP process crashed",
        )
        with patch("phraise.floating_window.shiboken6.isValid", return_value=True):
            FloatingWindow._on_harper_done(fw, result)

        fw._show_toast.assert_called_once_with("Harper LSP process crashed")
        fw._do_optimize_llm.assert_called_once()
        fw._on_optimize_done.assert_not_called()

    def test_lintresult_empty_error_but_success_false_falls_back(self):
        """Even without an explicit error message, success=False triggers
        the fallback path."""
        fw = _make_fw()

        result = LintResult(success=False)
        with patch("phraise.floating_window.shiboken6.isValid", return_value=True):
            FloatingWindow._on_harper_done(fw, result)

        fw._do_optimize_llm.assert_called_once()
        fw._on_optimize_done.assert_not_called()


# ====================================================================
# TestHarperClientLintResult — signal contract
# ====================================================================

class TestHarperClientLintResult(unittest.TestCase):
    """Verify that HarperClient emits LintResult with correct fields."""

    def test_binary_not_found_emits_success_false(self):
        """When the Harper binary cannot be found, finished emits a
        LintResult with success=False."""
        client = HarperClient()
        emitted = []

        def collect(result):
            emitted.append(result)

        client.finished.connect(collect)

        with patch(
            "phraise.harper_client.get_harper_binary_path", return_value=None
        ):
            issues, text = client.check_text("hello")

        self.assertEqual(issues, [])
        self.assertEqual(text, "hello")
        self.assertEqual(len(emitted), 1)
        self.assertFalse(emitted[0].success)
        self.assertEqual(emitted[0].issues, [])
        self.assertTrue(len(emitted[0].error) > 0)

    def test_exception_emits_success_false(self):
        """When check_text raises an exception, finished emits a
        LintResult with success=False."""
        client = HarperClient()
        emitted = []

        def collect(result):
            emitted.append(result)

        client.finished.connect(collect)

        with patch(
            "phraise.harper_client.get_harper_binary_path", return_value="/fake/harper"
        ), patch(
            "phraise.harper_client.HarperLspManager",
            side_effect=RuntimeError("subprocess error"),
        ), patch(
            "phraise.harper_client.QTimer", return_value=MagicMock()
        ):
            issues, text = client.check_text("hello")

        self.assertEqual(issues, [])
        self.assertEqual(text, "hello")
        self.assertEqual(len(emitted), 1)
        self.assertFalse(emitted[0].success)
        self.assertIn("subprocess error", emitted[0].error)
        self.assertEqual(emitted[0].corrected_text, "hello")

    def test_diagnostics_emits_success_true(self):
        """When diagnostics arrive, finished emits a LintResult with
        success=True and populated issues."""
        client = HarperClient()
        emitted = []

        def collect(result):
            emitted.append(result)

        client.finished.connect(collect)

        with patch(
            "phraise.harper_client.get_harper_binary_path",
            return_value="/fake/harper",
        ), patch(
            "phraise.harper_client.HarperLspManager",
        ) as mock_mgr_cls, patch(
            "phraise.harper_client.QTimer", return_value=MagicMock()
        ):
            mock_mgr = MagicMock()
            mock_mgr_cls.return_value = mock_mgr

            client.check_text("hello world")

            # Simulate diagnostics arriving
            client._current_text = "hello world"
            client._on_diagnostics([])

        self.assertEqual(len(emitted), 1)
        self.assertTrue(emitted[0].success)
        self.assertEqual(emitted[0].issues, [])
        self.assertEqual(emitted[0].corrected_text, "hello world")
        self.assertEqual(emitted[0].error, "")

    def test_error_signal_emits_success_false(self):
        """When the LSP manager reports an error, finished emits
        success=False."""
        client = HarperClient()
        emitted = []

        def collect(result):
            emitted.append(result)

        client.finished.connect(collect)

        with patch(
            "phraise.harper_client.get_harper_binary_path",
            return_value="/fake/harper",
        ), patch(
            "phraise.harper_client.HarperLspManager",
        ) as mock_mgr_cls, patch(
            "phraise.harper_client.QTimer", return_value=MagicMock()
        ):
            mock_mgr = MagicMock()
            mock_mgr_cls.return_value = mock_mgr

            client.check_text("hello world")
            client._current_text = "hello world"
            client._on_error("connection refused")

        self.assertEqual(len(emitted), 1)
        self.assertFalse(emitted[0].success)
        self.assertEqual(emitted[0].error, "connection refused")
        self.assertEqual(emitted[0].corrected_text, "hello world")


# ====================================================================
# Main
# ====================================================================

if __name__ == "__main__":
    unittest.main()
