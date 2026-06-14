"""TDD tests for Harper integration in ``FloatingWindow._do_optimize()``.

These tests verify that ``_do_optimize()`` correctly branches between Harper
grammar-checking and LLM rewriting.  The integration does **not** exist yet
(Task 13 implements it), so **all tests must FAIL** — this is the RED phase.

Expected failures at this stage:
    - HarperClient is never instantiated or consulted inside _do_optimize
    - ``optimize_text`` is always called regardless of the ``optimize_model`` config
    - No fallback logic exists for Harper unavailability or crashes
    - The unified result dict (``grammar_issues`` + ``rewrites``) is not produced
"""

import unittest
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Production imports
# ---------------------------------------------------------------------------
from phraise.floating_window import FloatingWindow
from phraise.harper_client import HarperClient


# ---------------------------------------------------------------------------
# Minimal test fixture — skips Qt constructor, wires up just the attributes
# that ``_do_optimize()`` touches.
# ---------------------------------------------------------------------------

def _make_fw(**overrides) -> FloatingWindow:
    """Return a bare ``FloatingWindow`` instance whose ``__init__`` was skipped.

    Only attributes read/written by ``_do_optimize()`` are pre-set.  Every
    callable attribute is a ``MagicMock`` so we can assert on interactions.
    """
    with patch.object(FloatingWindow, "__init__", return_value=None):
        fw = FloatingWindow.__new__(FloatingWindow)

    # -- attributes read by _do_optimize -----------------------------------
    fw._is_loading = False
    fw._current_text = "The quick brown fox jump over the lazy dog."
    fw._current_style = "concise"

    # -- callables touched by _do_optimize ---------------------------------
    fw._set_loading_state = MagicMock()
    fw._show_toast = MagicMock()
    fw._show_error = MagicMock()
    fw._on_optimize_done = MagicMock()

    fw._rewrite_label = MagicMock()
    fw._model_combo = MagicMock()
    fw._style_buttons = {}
    fw._set_harper_layout = MagicMock()

    # -- _on_optimize_done touches these; pre-populate as mocks ------------
    fw._rewrite_texts = [MagicMock(), MagicMock(), MagicMock()]
    for i, rt in enumerate(fw._rewrite_texts):
        rt.text_edit = MagicMock()
        rt.text_edit.setPlainText = MagicMock()
    fw._grammar_layout = MagicMock()
    fw._grammar_header = MagicMock()
    fw._grammar_container = MagicMock()

    # Apply any caller-supplied overrides
    for attr, val in overrides.items():
        setattr(fw, attr, val)

    return fw


# ====================================================================
# TestHarperOptimizeFlow
# ====================================================================

class TestHarperOptimizeFlow(unittest.TestCase):
    """RED-phase tests for the Harper ↔ LLM branching inside
    ``FloatingWindow._do_optimize()``.
    """

    # ------------------------------------------------------------------
    # 1. Harper mode produces one corrected version (not three rewrites)
    # ------------------------------------------------------------------

    def test_harper_mode_produces_one_version(self):
        """Mock HarperClient.check_text → (issues, corrected_text).
        Set config optimize_model="harper".
        Call _do_optimize().
        Assert result has ``grammar_issues`` and ``corrected_text``
        (not ``rewrites``).  Assert only 1 text box populated.
        """
        fw = _make_fw()

        issues = [{"original": "jump", "suggestion": "jumps", "reason": "SVA"}]
        corrected = "The quick brown fox jumps over the lazy dog."

        mock_client = MagicMock(spec=HarperClient)
        mock_client.is_available.return_value = True
        mock_client.check_text.return_value = (issues, corrected)

        with patch(
            "phraise.floating_window.optimize_text"
        ) as mock_opt, patch(
            "phraise.floating_window.check_output_fit",
            return_value=(True, 0, 0, ""),
        ), patch(
            "phraise.floating_window.run_on_main",
            side_effect=lambda fn: fn(),
        ), patch(
            "phraise.floating_window.config"
        ) as mock_cfg, patch(
            "phraise.harper_client.HarperClient",
            return_value=mock_client,
        ) as mock_hc_cls:

            mock_cfg.get.side_effect = _make_config_get("harper")

            FloatingWindow._do_optimize(fw)

            # ---- assertions that WILL FAIL until integration exists ----
            # LLM must NOT be called in Harper mode
            mock_opt.assert_not_called()

            # HarperClient must have been consulted
            mock_hc_cls.assert_called_once()
            mock_client.check_text.assert_called_once_with(fw._current_text)

            # The on_done callback must receive the Harper-style result
            # (check via _on_optimize_done, which run_on_main dispatches to)
            fw._on_optimize_done.assert_called_once()
            call_args = fw._on_optimize_done.call_args[0]
            result = call_args[0]

            self.assertIn("grammar_issues", result)
            self.assertIn("corrected_text", result)
            self.assertNotIn("rewrites", result)
            self.assertEqual(result["corrected_text"], corrected)

            # Only one text box populated (Harper gives exactly one version)
            populated = sum(
                1 for rt in fw._rewrite_texts
                if rt.text_edit.setPlainText.called
                and rt.text_edit.setPlainText.call_args
                and rt.text_edit.setPlainText.call_args[0][0] != ""
            )
            self.assertEqual(populated, 1)

    # ------------------------------------------------------------------
    # 2. Harper mode must NOT make an LLM call
    # ------------------------------------------------------------------

    def test_harper_mode_no_llm_call(self):
        """Set config to Harper mode.  Call _do_optimize().
        Assert ``optimize_text`` was NOT called.
        """
        fw = _make_fw()

        mock_client = MagicMock(spec=HarperClient)
        mock_client.is_available.return_value = True
        mock_client.check_text.return_value = ([], fw._current_text)

        with patch(
            "phraise.floating_window.optimize_text"
        ) as mock_opt, patch(
            "phraise.floating_window.check_output_fit",
            return_value=(True, 0, 0, ""),
        ), patch(
            "phraise.floating_window.run_on_main",
            side_effect=lambda fn: fn(),
        ), patch(
            "phraise.floating_window.config"
        ) as mock_cfg, patch(
            "phraise.harper_client.HarperClient",
            return_value=mock_client,
        ):

            mock_cfg.get.side_effect = _make_config_get("harper")

            FloatingWindow._do_optimize(fw)

            # This assertion WILL FAIL — current code always calls optimize_text
            mock_opt.assert_not_called()

    # ------------------------------------------------------------------
    # 3. LLM mode still works (backward compatibility)
    # ------------------------------------------------------------------

    def test_llm_mode_still_works(self):
        """Set config to LLM mode (model_1).  Call _do_optimize().
        Assert ``optimize_text`` IS called and produces ``rewrites`` key
        in the result dict.
        """
        fw = _make_fw()

        sample_rewrites = [
            {"text": "The swift brown fox jumps over the lazy dog."},
            {"text": "A quick brown fox leaps across the lazy dog."},
            {"text": "The fast brown fox vaults over the sleepy dog."},
        ]
        llm_result = {"rewrites": sample_rewrites}

        mock_client = MagicMock(spec=HarperClient)
        mock_client.is_available.return_value = True

        with patch(
            "phraise.floating_window.optimize_text"
        ) as mock_opt, patch(
            "phraise.floating_window.check_output_fit",
            return_value=(True, 0, 0, ""),
        ), patch(
            "phraise.floating_window.run_on_main",
            side_effect=lambda fn: fn(),
        ), patch(
            "phraise.floating_window.config"
        ) as mock_cfg, patch(
            "phraise.harper_client.HarperClient",
            return_value=mock_client,
        ):

            mock_cfg.get.side_effect = _make_config_get("model_1")

            # Simulate optimize_text calling its on_done callback
            def simulate_optimize_text(*args, **kwargs):
                on_done = kwargs.get("on_done")
                if on_done:
                    on_done(llm_result, None)

            mock_opt.side_effect = simulate_optimize_text

            FloatingWindow._do_optimize(fw)

            # ---- assertions ----
            # optimize_text must be called (this MAY pass — LLM path exists)
            mock_opt.assert_called()

            # HarperClient.is_available must have been checked as part of the
            # unified dispatch (WILL FAIL — current code never consults Harper)
            mock_client.is_available.assert_called()

            # The on_done callback delivers a rewrites list
            fw._on_optimize_done.assert_called_once()
            call_args = fw._on_optimize_done.call_args[0]
            result = call_args[0]
            self.assertIn("rewrites", result)
            self.assertEqual(len(result["rewrites"]), 3)

    # ------------------------------------------------------------------
    # 4. Harper unavailable → fall back to LLM
    # ------------------------------------------------------------------

    def test_harper_unavailable_falls_back_to_llm(self):
        """Mock ``HarperClient.is_available() → False``.
        Set Harper mode.  Call _do_optimize().
        Assert falls back to calling ``optimize_text``.
        """
        fw = _make_fw()

        mock_client = MagicMock(spec=HarperClient)
        mock_client.is_available.return_value = False

        with patch(
            "phraise.floating_window.optimize_text"
        ) as mock_opt, patch(
            "phraise.floating_window.check_output_fit",
            return_value=(True, 0, 0, ""),
        ), patch(
            "phraise.floating_window.run_on_main",
            side_effect=lambda fn: fn(),
        ), patch(
            "phraise.floating_window.config"
        ) as mock_cfg, patch(
            "phraise.harper_client.HarperClient",
            return_value=mock_client,
        ):

            mock_cfg.get.side_effect = _make_config_get("harper")

            FloatingWindow._do_optimize(fw)

            # WILL FAIL — current code never checks Harper availability;
            # the integration must call is_available() first, see it's False,
            # and then fall back to optimize_text
            mock_client.is_available.assert_called()
            mock_opt.assert_called()
            mock_client.check_text.assert_not_called()

    # ------------------------------------------------------------------
    # 5. Harper crash → fall back to LLM
    # ------------------------------------------------------------------

    def test_harper_crash_falls_back_to_llm(self):
        """Mock ``HarperClient.check_text()`` raises exception.
        Assert error is caught and falls back to ``optimize_text``.
        """
        fw = _make_fw()

        mock_client = MagicMock(spec=HarperClient)
        mock_client.is_available.return_value = True
        mock_client.check_text.side_effect = RuntimeError("Harper subprocess crashed")

        with patch(
            "phraise.floating_window.optimize_text"
        ) as mock_opt, patch(
            "phraise.floating_window.check_output_fit",
            return_value=(True, 0, 0, ""),
        ), patch(
            "phraise.floating_window.run_on_main",
            side_effect=lambda fn: fn(),
        ), patch(
            "phraise.floating_window.config"
        ) as mock_cfg, patch(
            "phraise.harper_client.HarperClient",
            return_value=mock_client,
        ):

            mock_cfg.get.side_effect = _make_config_get("harper")

            FloatingWindow._do_optimize(fw)

            # WILL FAIL — current code has no Harper crash handling
            # and never calls optimize_text as a fallback for Harper errors
            mock_opt.assert_called()
            mock_client.check_text.assert_called_once()

    # ------------------------------------------------------------------
    # 6. Concurrent Harper request → blocked by _is_loading
    # ------------------------------------------------------------------

    def test_concurrent_harper_request_blocked(self):
        """Two rapid optimize triggers in Harper mode.
        Verify the second is blocked by the ``_is_loading`` flag.
        """
        fw = _make_fw()

        mock_client = MagicMock(spec=HarperClient)
        mock_client.is_available.return_value = True
        mock_client.check_text.return_value = ([], fw._current_text)

        with patch(
            "phraise.floating_window.optimize_text"
        ) as mock_opt, patch(
            "phraise.floating_window.check_output_fit",
            return_value=(True, 0, 0, ""),
        ), patch(
            "phraise.floating_window.run_on_main",
            side_effect=lambda fn: fn(),
        ), patch(
            "phraise.floating_window.config"
        ) as mock_cfg, patch(
            "phraise.harper_client.HarperClient",
            return_value=mock_client,
        ):

            mock_cfg.get.side_effect = _make_config_get("harper")

            # First call — should proceed
            FloatingWindow._do_optimize(fw)

            # Second call — _is_loading is True, should return early
            FloatingWindow._do_optimize(fw)

            # ---- assertions ----
            # _is_loading must be True after first call
            self.assertTrue(fw._is_loading)

            # HarperClient must have been consulted exactly ONCE
            # WILL FAIL — current code has no Harper integration,
            # so check_text is never called at all
            self.assertEqual(mock_client.check_text.call_count, 1)

            # optimize_text must NOT have been called at all in Harper mode
            mock_opt.assert_not_called()


# ====================================================================
# Helpers
# ====================================================================

def _make_config_get(model_value: str):
    """Return a ``config.get`` side_effect that returns ``model_value`` for
    ``"general"/"optimize_model"`` and a sensible default for other keys.

    Matches the real ``Config.get(self, *keys, default=None)`` signature.
    """
    def _get(*keys, default=None):
        # config.get("general", "optimize_model", default="model_1")
        if keys == ("general", "optimize_model"):
            return model_value
        # config.get("floating_window", "last_style", default="concise")
        if keys == ("floating_window", "last_style"):
            return "concise"
        # config.get("styles", default=[])
        if keys == ("styles",):
            return [{"id": "concise", "label": "Concise"}]
        return default
    return _get


# ====================================================================
# Main
# ====================================================================

if __name__ == "__main__":
    unittest.main()
