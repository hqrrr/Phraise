"""Regression test: ``_populate_grammar_issues`` accepts ``HarperIssue`` dataclasses.

The production code at ``floating_window.py:728`` originally called
``issue.get(...)`` on each item in the issues list (dict-style access).  When
Harper mode is enabled the issues list contains ``HarperIssue`` dataclass
instances instead of plain dicts, and ``.get()`` raised
``AttributeError: 'HarperIssue' object has no attribute 'get'``.

Tests in this file:
1. ``test_harper_issue_dataclass_renders_label`` — proves ``HarperIssue`` instances work.
2. ``test_dict_backward_compat`` — ensures plain-dict issues still work.
3. ``test_empty_issues_list_no_error`` — empty list edge case.
"""

import unittest
from unittest.mock import MagicMock, patch

from PySide6.QtWidgets import QApplication

from phraise.floating_window import FloatingWindow
from phraise.harper_types import HarperIssue


# ---------------------------------------------------------------------------
# Mocked config.get  —  same defaults used by test_toast_lifecycle.py
# ---------------------------------------------------------------------------

_CONFIG_DEFAULTS = {
    # FloatingWindow geometry
    ("floating_window", "opacity"): 0.95,
    ("floating_window", "width"): 400,
    ("floating_window", "height"): 500,
    ("floating_window", "position_x"): 1400,
    ("floating_window", "position_y"): 600,
    ("floating_window", "last_style"): "concise",
    # Theme colors (needed by _build_ui)
    ("floating_window", "bg"): "#1e1e2e",
    ("floating_window", "bg_darker"): "#181825",
    ("floating_window", "border"): "#313244",
    ("floating_window", "surface"): "#313244",
    ("floating_window", "text"): "#cdd6f4",
    ("floating_window", "text_muted"): "#6c7086",
    ("floating_window", "primary"): "#89b4fa",
    ("floating_window", "yellow"): "#f9e2af",
    ("floating_window", "red"): "#f38ba8",
    ("floating_window", "green"): "#a6e3a1",
    # Styles
    ("styles",): [{"id": "concise", "label": "Concise"}],
}


def _mock_config_get(*keys, default=None):
    """Return sensible defaults for config keys used during FloatingWindow init."""
    key = tuple(keys)
    if key in _CONFIG_DEFAULTS:
        return _CONFIG_DEFAULTS[key]
    if default is not None:
        return default
    return "concise"


# ---------------------------------------------------------------------------
# Test class
# ---------------------------------------------------------------------------


class TestFloatingWindowHarperIssues(unittest.TestCase):
    """``_populate_grammar_issues`` must accept both ``HarperIssue`` and dict."""

    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance()
        if cls._app is None:
            cls._app = QApplication([])

    def setUp(self) -> None:
        """Clean up descriptors leaked by ``test_callback_after_destroy.py``."""
        for attr in ("_rewrite_texts", "_translation_text"):
            try:
                delattr(FloatingWindow, attr)
            except AttributeError:
                pass

    # ------------------------------------------------------------------
    # Helper
    # ------------------------------------------------------------------

    def _make_fw(self) -> FloatingWindow:
        """Create a minimal ``FloatingWindow`` with mocked dependencies."""
        grabber = MagicMock()
        with (
            patch("phraise.floating_window.add_listener", return_value=None),
            patch("phraise.floating_window.config.update_section", return_value=None),
            patch("phraise.i18n.add_listener", return_value=None),
            patch("phraise.floating_window.config.get", side_effect=_mock_config_get),
        ):
            fw = FloatingWindow(grabber, on_close=MagicMock())
        return fw

    # ------------------------------------------------------------------
    # Tests
    # ------------------------------------------------------------------

    def test_harper_issue_dataclass_renders_label(self):
        """``_populate_grammar_issues`` accepts ``HarperIssue`` dataclass instances.

        Before the fix, ``issue.get(...)`` crashed with::

            AttributeError: 'HarperIssue' object has no attribute 'get'
        """
        fw = self._make_fw()
        issues = [
            HarperIssue(
                original="teh",
                suggestion="the",
                reason="spelling",
                severity="warning",
            ),
        ]
        try:
            fw._populate_grammar_issues(issues)
        except Exception as exc:  # noqa: BLE001
            self.fail(f"_populate_grammar_issues raised {type(exc).__name__}: {exc}")

    def test_dict_backward_compat(self):
        """``_populate_grammar_issues`` accepts plain-dict issues without error."""
        fw = self._make_fw()
        issues = [
            {
                "original": "teh",
                "suggestion": "the",
                "reason": "spelling",
                "severity": "warning",
            },
            {
                "original": "recieve",
                "suggestion": "receive",
                "reason": "spelling",
                "severity": "error",
            },
        ]
        try:
            fw._populate_grammar_issues(issues)
        except Exception as exc:  # noqa: BLE001
            self.fail(f"_populate_grammar_issues raised {type(exc).__name__}: {exc}")

    def test_empty_issues_list_no_error(self):
        """``_populate_grammar_issues([])`` must not raise — shows the "no issues" label."""
        fw = self._make_fw()
        try:
            fw._populate_grammar_issues([])
        except Exception as exc:  # noqa: BLE001
            self.fail(f"_populate_grammar_issues([]) raised {type(exc).__name__}: {exc}")
