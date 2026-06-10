"""Tests for stale callback guards — prevent crash on destroyed window (Task 12).

Verifies that ``_on_optimize_done``, ``_on_translate_done``, ``_on_custom_done``,
and ``_on_harper_done`` all return safely when the ``FloatingWindow`` C++ object
has been deleted before the callback fires.
"""

import unittest
from unittest.mock import MagicMock, patch

from phraise.floating_window import FloatingWindow


# ---------------------------------------------------------------------------
# Descriptor that simulates a deleted QObject attribute
# ---------------------------------------------------------------------------

class _DeletedAttr:
    """Descriptor that raises RuntimeError on access, simulating a
    deleted C++ QObject attribute."""

    def __get__(self, obj, objtype=None):
        raise RuntimeError("Internal C++ object already deleted")

    def __set__(self, obj, value):
        pass


# ---------------------------------------------------------------------------
# Bare FloatingWindow factory
# ---------------------------------------------------------------------------

def _make_fw(**overrides) -> FloatingWindow:
    """Return a bare ``FloatingWindow`` instance whose ``__init__`` was skipped."""
    with patch.object(FloatingWindow, "__init__", return_value=None):
        fw = FloatingWindow.__new__(FloatingWindow)

    fw._is_loading = False
    fw._active_client = None
    fw._current_text = "The quick brown fox."
    fw._current_style = "concise"
    fw._current_mode = "optimize"

    fw._set_loading_state = MagicMock()
    fw._show_toast = MagicMock()
    fw._show_error = MagicMock()
    fw._show_raw_text = MagicMock()
    fw._populate_grammar_issues = MagicMock()
    fw._do_optimize_llm = MagicMock()

    fw._rewrite_texts = [MagicMock(), MagicMock(), MagicMock()]
    for rt in fw._rewrite_texts:
        rt.text_edit = MagicMock()
        rt.text_edit.setPlainText = MagicMock()
        rt.text_edit.clear = MagicMock()

    fw._translation_text = MagicMock()
    fw._translation_text.setPlainText = MagicMock()

    fw._grammar_layout = MagicMock()
    fw._grammar_header = MagicMock()
    fw._grammar_container = MagicMock()

    for attr, val in overrides.items():
        setattr(fw, attr, val)

    return fw


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestCallbackAfterDestroy(unittest.TestCase):
    """All four callbacks must return safely when self is deleted."""

    def setUp(self):
        """Clean up any ``_DeletedAttr`` descriptors from previous tests."""
        for attr in ("_rewrite_texts", "_translation_text"):
            try:
                delattr(FloatingWindow, attr)
            except AttributeError:
                pass

    # ---- _on_optimize_done ----

    def test_optimize_done_deleted_self_returns_safely(self):
        fw = _make_fw()
        FloatingWindow._rewrite_texts = _DeletedAttr()
        try:
            fw._on_optimize_done({"rewrites": [{"text": "test"}]}, None)
        except Exception as e:
            self.fail(f"_on_optimize_done raised {type(e).__name__}: {e}")

    def test_optimize_done_with_error_on_deleted_self(self):
        fw = _make_fw()
        FloatingWindow._rewrite_texts = _DeletedAttr()
        try:
            fw._on_optimize_done(None, "LLM timeout")
        except Exception as e:
            self.fail(f"_on_optimize_done(error) raised {type(e).__name__}: {e}")

    def test_optimize_done_alive_self_still_works(self):
        fw = _make_fw()
        fw._on_optimize_done({"rewrites": [{"text": "hello"}]}, None)
        fw._set_loading_state.assert_called_with(False)
        self.assertFalse(fw._is_loading)

    # ---- _on_translate_done ----

    def test_translate_done_deleted_self_returns_safely(self):
        fw = _make_fw()
        FloatingWindow._translation_text = _DeletedAttr()
        try:
            fw._on_translate_done({"translation": "bonjour"}, None)
        except Exception as e:
            self.fail(f"_on_translate_done raised {type(e).__name__}: {e}")

    def test_translate_done_with_error_on_deleted_self(self):
        fw = _make_fw()
        FloatingWindow._translation_text = _DeletedAttr()
        try:
            fw._on_translate_done(None, "API error")
        except Exception as e:
            self.fail(f"_on_translate_done(error) raised {type(e).__name__}: {e}")

    def test_translate_done_alive_self_still_works(self):
        fw = _make_fw()
        fw._on_translate_done({"translation": "guten tag"}, None)
        fw._set_loading_state.assert_called_with(False)
        self.assertFalse(fw._is_loading)

    # ---- _on_custom_done ----

    def test_custom_done_deleted_self_returns_safely(self):
        fw = _make_fw()
        FloatingWindow._rewrite_texts = _DeletedAttr()
        try:
            fw._on_custom_done({"result": "custom output"}, None)
        except Exception as e:
            self.fail(f"_on_custom_done raised {type(e).__name__}: {e}")

    def test_custom_done_with_error_on_deleted_self(self):
        fw = _make_fw()
        FloatingWindow._rewrite_texts = _DeletedAttr()
        try:
            fw._on_custom_done(None, "Custom error")
        except Exception as e:
            self.fail(f"_on_custom_done(error) raised {type(e).__name__}: {e}")

    def test_custom_done_alive_self_still_works(self):
        fw = _make_fw()
        fw._on_custom_done({"result": "custom result"}, None)
        fw._set_loading_state.assert_called_with(False)
        self.assertFalse(fw._is_loading)

    # ---- _on_harper_done (already guarded from Task 10) ----

    def test_harper_done_deleted_self_returns_safely(self):
        from phraise.harper_client import LintResult
        fw = _make_fw()
        FloatingWindow._rewrite_texts = _DeletedAttr()
        result = LintResult(success=True, issues=[], corrected_text="corrected")
        try:
            fw._on_harper_done(result)
        except Exception as e:
            self.fail(f"_on_harper_done raised {type(e).__name__}: {e}")

    def test_harper_done_error_on_deleted_self(self):
        from phraise.harper_client import LintResult
        fw = _make_fw()
        FloatingWindow._rewrite_texts = _DeletedAttr()
        result = LintResult(success=False, issues=[], corrected_text="", error="LSP died")
        try:
            fw._on_harper_done(result)
        except Exception as e:
            self.fail(f"_on_harper_done(error) raised {type(e).__name__}: {e}")
