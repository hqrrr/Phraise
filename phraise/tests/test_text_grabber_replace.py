# PhrAIse - AI writing assistant
# License: GNU GPLv3
# GitHub: https://github.com/hqrrr/Phraise
# Author: hqrrr
#
# Description: Unit tests for selection-aware UIA text replacement.
"""Tests for _replace_via_uia selection-aware behaviour.

These tests encode the DESIRED behaviour where the selection-aware
TextPattern path is preferred over ValuePattern.SetValue().
The production code currently tries ValuePattern first — these tests
are expected to FAIL (RED) until the fix is applied.

Verifies that:
- S1: Saved _selection_range is used directly, ValuePattern is skipped.
- S2: Without saved range, GetSelection() is used.
- S3: Stale saved range falls through to GetSelection().
- S4: ValuePattern-only controls still work (regression).
- S5: Controls with no UIA patterns return False (regression).
"""

from unittest.mock import MagicMock, patch

import pytest

from phraise.text_grabber import TextGrabber


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_control_with_both_patterns():
    """Return a MagicMock with both GetTextPattern and GetValuePattern."""
    control = MagicMock()
    tp = MagicMock()
    control.GetTextPattern.return_value = tp
    vp = MagicMock()
    control.GetValuePattern.return_value = vp
    return control, tp, vp


def _make_control_value_pattern_only():
    """Return a MagicMock where GetTextPattern raises AttributeError
    but GetValuePattern returns a valid mock."""
    control = MagicMock()
    control.GetTextPattern.side_effect = AttributeError("no TextPattern")
    vp = MagicMock()
    control.GetValuePattern.return_value = vp
    return control, vp


def _make_control_no_patterns():
    """Return a MagicMock where both pattern accessors raise AttributeError."""
    control = MagicMock()
    control.GetTextPattern.side_effect = AttributeError("no TextPattern")
    control.GetValuePattern.side_effect = AttributeError("no ValuePattern")
    control.GetParentControl.return_value = None
    return control


# ---------------------------------------------------------------------------
# S1: Happy path — saved _selection_range is preferred
# ---------------------------------------------------------------------------

def test_s1_saved_range_preferred_over_valuepattern():
    """When _selection_range is saved, use it with SendKeys; skip ValuePattern."""
    grabber = TextGrabber()
    control, tp, vp = _make_control_with_both_patterns()
    grabber._foreground_control = control

    saved_range = MagicMock()
    saved_range.Select.return_value = True
    grabber._selection_range = saved_range

    with patch("phraise.text_grabber._ensure_com_initialized"):
        result = grabber._replace_via_uia("replacement text")

    # DESIRED: saved range is used first
    saved_range.Select.assert_called_once()
    # DESIRED: text is sent via SendKeys with escaping
    control.SendKeys.assert_called_once_with("replacement text")
    # DESIRED: ValuePattern is never touched when TextPattern path succeeds
    control.GetValuePattern.assert_not_called()
    # DESIRED: method reports success
    assert result is True


# ---------------------------------------------------------------------------
# S2: No saved range — uses GetSelection()
# ---------------------------------------------------------------------------

def test_s2_no_saved_range_uses_getselection():
    """Without _selection_range, call tp.GetSelection() and use its result."""
    grabber = TextGrabber()
    control, tp, vp = _make_control_with_both_patterns()
    grabber._foreground_control = control
    # _selection_range stays None

    selected_range = MagicMock()
    selected_range.Select.return_value = True
    tp.GetSelection.return_value = [selected_range]

    with patch("phraise.text_grabber._ensure_com_initialized"):
        result = grabber._replace_via_uia("text")

    # DESIRED: GetSelection() is called to find the current selection
    tp.GetSelection.assert_called()
    # DESIRED: the returned range is selected
    selected_range.Select.assert_called()
    # DESIRED: replacement is sent via SendKeys
    control.SendKeys.assert_called()
    # DESIRED: ValuePattern is not used when TextPattern is available
    control.GetValuePattern.assert_not_called()
    assert result is True


# ---------------------------------------------------------------------------
# S3: Stale saved range falls through to GetSelection()
# ---------------------------------------------------------------------------

def test_s3_stale_saved_range_falls_through():
    """When _selection_range.Select() raises OSError, fall back to GetSelection()."""
    grabber = TextGrabber()
    control, tp, vp = _make_control_with_both_patterns()
    grabber._foreground_control = control

    stale_range = MagicMock()
    stale_range.Select.side_effect = OSError("stale selection range")
    grabber._selection_range = stale_range

    fallback_range = MagicMock()
    fallback_range.Select.return_value = True
    tp.GetSelection.return_value = [fallback_range]

    with patch("phraise.text_grabber._ensure_com_initialized"):
        result = grabber._replace_via_uia("text")

    # DESIRED: no unhandled exception — the OSError is caught internally
    # DESIRED: GetSelection() is called as the fallback
    tp.GetSelection.assert_called()
    # DESIRED: method succeeds via the fallback path
    assert result is True


# ---------------------------------------------------------------------------
# S4: Regression — ValuePattern-only control still works
# ---------------------------------------------------------------------------

def test_s4_valuepattern_only_control_still_works():
    """When there is no TextPattern, fall back to ValuePattern.SetValue()."""
    grabber = TextGrabber()
    control, vp = _make_control_value_pattern_only()
    grabber._foreground_control = control

    with patch("phraise.text_grabber._ensure_com_initialized"):
        result = grabber._replace_via_uia("text")

    # DESIRED: TextPattern is attempted first (and fails gracefully)
    control.GetTextPattern.assert_called()
    # DESIRED: ValuePattern.SetValue() is called as the fallback
    vp.SetValue.assert_called_once_with("text")
    # DESIRED: SendKeys is not used on ValuePattern-only controls
    control.SendKeys.assert_not_called()
    # DESIRED: method succeeds
    assert result is True


# ---------------------------------------------------------------------------
# S5: Regression — no UIA patterns at all
# ---------------------------------------------------------------------------

def test_s5_no_uia_patterns_returns_false():
    """When neither TextPattern nor ValuePattern exists, return False."""
    grabber = TextGrabber()
    control = _make_control_no_patterns()
    grabber._foreground_control = control

    with patch("phraise.text_grabber._ensure_com_initialized"):
        result = grabber._replace_via_uia("text")

    # DESIRED: no unhandled exception
    # DESIRED: TextPattern is attempted before ValuePattern
    calls = [str(c) for c in control.mock_calls]
    text_calls = [i for i, c in enumerate(calls) if "GetTextPattern" in c]
    value_calls = [i for i, c in enumerate(calls) if "GetValuePattern" in c]
    assert text_calls and value_calls, (
        f"Both GetTextPattern and GetValuePattern must be called; "
        f"calls were: {calls}"
    )
    assert text_calls[0] < value_calls[0], (
        "TextPattern must be tried before ValuePattern "
        f"(found TextPattern at index {text_calls[0]}, "
        f"ValuePattern at index {value_calls[0]})"
    )
    # DESIRED: method returns False when nothing works
    assert result is False
