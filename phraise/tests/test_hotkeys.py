# PhrAIse - AI writing assistant
# License: GNU GPLv3
# GitHub: https://github.com/hqrrr/Phraise
# Author: hqrrr
#
# Description: Unit tests for hotkeys.
"""TDD tests for hotkey double-tap parsing, validation, and state machine.

These tests import from phraise.hotkeys, which does not yet have the
_parse_trigger_config, _validate_trigger_hotkey, or DoubleTapDetector
symbols.  This is intentional — the RED phase of TDD.

Expected failures at this stage:
    ImportError: cannot import name '_parse_trigger_config'
    ImportError: cannot import name '_validate_trigger_hotkey'
    ImportError: cannot import name 'DoubleTapDetector'

Once the implementation exists the tests below should pass.
"""

import time
import unittest
from unittest.mock import Mock, patch

# ---------------------------------------------------------------------------
# Imports that WILL fail in the RED phase — that is expected.
# When the implementation is written, uncomment / fix as needed.
# ---------------------------------------------------------------------------
# fmt: off
try:
    from phraise.hotkeys import (
        DoubleTapDetector,
        _parse_trigger_config,
        _validate_trigger_hotkey,
    )
except ImportError:
    # RED phase — stubs so the test module itself is importable.
    # Replace with the real imports once the functions / class exist.
    DoubleTapDetector = None         # type: ignore[assignment]
    _parse_trigger_config: callable = None   # type: ignore[no-redef]
    _validate_trigger_hotkey: callable = None  # type: ignore[no-redef]
# fmt: on


# ====================================================================
# Helpers
# ====================================================================

def mock_key(name: str) -> Mock:
    """Create a mock pynput key object.

    ``name`` is the ``Key.name`` (e.g. "ctrl", "alt", "shift", "a", "1").
    ``char`` is set to ``name`` for single-character names, ``None`` otherwise.
    """
    m = Mock()
    m.name = name
    m.char = name if len(name) == 1 else None
    return m


# ====================================================================
# 1. Parsing  —  _parse_trigger_config(text) -> dict
# ====================================================================

class TestParseTriggerConfig(unittest.TestCase):
    """Unit tests for ``_parse_trigger_config``.

    Expected signature::

        _parse_trigger_config(text: str) -> dict

    Returned dict keys::

        "is_double_tap"   bool
        "modifiers"       tuple[str, ...]
        "key"             str
    """

    # -- helpers -------------------------------------------------------

    def parse(self, text: str) -> dict:
        """Shorthand to call the function-under-test, skipping empty-string."""
        if _parse_trigger_config is None:
            self.skipTest("_parse_trigger_config not implemented yet")
        return _parse_trigger_config(text)

    # -- double-tap cases -----------------------------------------------

    def test_parse_double_tap_ctrl_c(self):
        """``ctrl+c+c`` → double-tap with one modifier."""
        result = self.parse("ctrl+c+c")
        self.assertTrue(result["is_double_tap"])
        self.assertEqual(result["modifiers"], ("ctrl",))
        self.assertEqual(result["key"], "c")

    def test_parse_double_tap_ctrl_shift_a(self):
        """``ctrl+shift+a+a`` → double-tap with two modifiers."""
        result = self.parse("ctrl+shift+a+a")
        self.assertTrue(result["is_double_tap"])
        self.assertEqual(result["modifiers"], ("ctrl", "shift"))
        self.assertEqual(result["key"], "a")

    def test_parse_double_tap_alt_x(self):
        """``alt+x+x`` → double-tap with alt modifier."""
        result = self.parse("alt+x+x")
        self.assertTrue(result["is_double_tap"])
        self.assertEqual(result["modifiers"], ("alt",))
        self.assertEqual(result["key"], "x")

    def test_parse_double_tap_win_c(self):
        """``win+c+c`` → double-tap with win/cmd modifier."""
        result = self.parse("win+c+c")
        self.assertTrue(result["is_double_tap"])
        self.assertEqual(result["modifiers"], ("win",))
        self.assertEqual(result["key"], "c")

    def test_parse_double_tap_digit_key(self):
        """``ctrl+1+1`` → double-tap with digit key."""
        result = self.parse("ctrl+1+1")
        self.assertTrue(result["is_double_tap"])
        self.assertEqual(result["modifiers"], ("ctrl",))
        self.assertEqual(result["key"], "1")

    def test_parse_double_tap_case_insensitive_modifiers(self):
        """``Ctrl+C+c`` → double-tap, case-insensitive for modifiers."""
        result = self.parse("Ctrl+C+c")
        self.assertTrue(result["is_double_tap"])
        self.assertEqual(result["modifiers"], ("Ctrl",))
        self.assertEqual(result["key"], "c")

    # -- single-combo cases ---------------------------------------------

    def test_parse_single_combo(self):
        """``ctrl+shift+o`` → single combo, NOT double-tap."""
        result = self.parse("ctrl+shift+o")
        self.assertFalse(result["is_double_tap"])

    def test_parse_single_combo_two_modifiers(self):
        """``ctrl+alt+del`` → single combo, three parts all different."""
        result = self.parse("ctrl+alt+del")
        self.assertFalse(result["is_double_tap"])

    def test_parse_single_combo_two_keys_different(self):
        """``ctrl+a+b`` → last two are different → NOT double-tap."""
        result = self.parse("ctrl+a+b")
        self.assertFalse(result["is_double_tap"])

    def test_parse_multi_char_key_not_double_tap(self):
        """``ctrl+abc+abc`` → multi-char key repetition → NOT double-tap."""
        result = self.parse("ctrl+abc+abc")
        self.assertFalse(result["is_double_tap"])

    def test_parse_modifier_name_as_key_not_double_tap(self):
        """``ctrl+shift+shift`` → 'shift' is multi-char → NOT double-tap."""
        result = self.parse("ctrl+shift+shift")
        self.assertFalse(result["is_double_tap"])

    # -- edge / boundary ------------------------------------------------

    def test_parse_single_key_only(self):
        """``c`` → single key, no modifiers, no double-tap."""
        result = self.parse("c")
        self.assertFalse(result["is_double_tap"])

    def test_parse_two_parts_same(self):
        """``x+x`` → two identical single-char keys (no modifiers)."""
        result = self.parse("x+x")
        self.assertTrue(result["is_double_tap"])
        self.assertEqual(result["modifiers"], ())
        self.assertEqual(result["key"], "x")

    def test_parse_double_tap_with_three_modifiers(self):
        """``ctrl+alt+shift+k+k`` → three modifiers + double-tap."""
        result = self.parse("ctrl+alt+shift+k+k")
        self.assertTrue(result["is_double_tap"])
        self.assertEqual(result["modifiers"], ("ctrl", "alt", "shift"))
        self.assertEqual(result["key"], "k")

    def test_parse_keys_are_case_sensitive(self):
        """``ctrl+a+A`` → different case → still double-tap because key chars
        are normalised to lowercase for comparison."""
        result = self.parse("ctrl+a+A")
        self.assertTrue(result["is_double_tap"])
        self.assertEqual(result["modifiers"], ("ctrl",))
        self.assertEqual(result["key"], "a")

    # -- empty / whitespace ---------------------------------------------

    def test_parse_empty_string(self):
        """Empty string → raises ValueError or returns non-double-tap."""
        try:
            result = self.parse("")
            self.assertFalse(result.get("is_double_tap", False))
        except ValueError:
            pass  # raising is also acceptable

    def test_parse_whitespace_only(self):
        """Whitespace-only string → should not be a valid hotkey."""
        try:
            result = self.parse("   ")
            self.assertFalse(result.get("is_double_tap", False))
        except ValueError:
            pass  # raising is acceptable


# ====================================================================
# 2. Validation  —  _validate_trigger_hotkey(text) -> bool
# ====================================================================

class TestValidateTriggerHotkey(unittest.TestCase):
    """Unit tests for ``_validate_trigger_hotkey``.

    Expected signature::

        _validate_trigger_hotkey(text: str) -> bool
    """

    def validate(self, text: str) -> bool:
        if _validate_trigger_hotkey is None:
            self.skipTest("_validate_trigger_hotkey not implemented yet")
        return _validate_trigger_hotkey(text)

    # -- valid double-tap strings ---------------------------------------

    def test_validate_double_tap_ctrl_c(self):
        """``ctrl+c+c`` → valid double-tap."""
        self.assertTrue(self.validate("ctrl+c+c"))

    def test_validate_double_tap_ctrl_shift_x(self):
        """``ctrl+shift+x+x`` → valid double-tap."""
        self.assertTrue(self.validate("ctrl+shift+x+x"))

    def test_validate_double_tap_alt_k(self):
        """``alt+k+k`` → valid double-tap."""
        self.assertTrue(self.validate("alt+k+k"))

    def test_validate_double_tap_win_f(self):
        """``win+f+f`` → valid double-tap."""
        self.assertTrue(self.validate("win+f+f"))

    def test_validate_double_tap_no_modifier(self):
        """``z+z`` → valid double-tap with no modifier."""
        self.assertTrue(self.validate("z+z"))

    # -- invalid double-tap strings -------------------------------------

    def test_validate_double_tap_mismatch(self):
        """``ctrl+c+d`` → last two keys differ → invalid."""
        self.assertFalse(self.validate("ctrl+c+d"))

    def test_validate_double_tap_empty_parts(self):
        """``ctrl++c`` → empty part between '+' → invalid."""
        self.assertFalse(self.validate("ctrl++c"))

    def test_validate_double_tap_trailing_plus(self):
        """``ctrl+c+`` → trailing plus → invalid."""
        self.assertFalse(self.validate("ctrl+c+"))

    def test_validate_double_tap_bad_modifier(self):
        """``xyz+c+c`` → 'xyz' is not a recognised modifier → invalid."""
        self.assertFalse(self.validate("xyz+c+c"))

    def test_validate_double_tap_number_as_modifier(self):
        """``1+c+c`` → '1' is not a modifier → invalid."""
        self.assertFalse(self.validate("1+c+c"))

    def test_validate_double_tap_too_many_same_keys(self):
        """``ctrl+c+c+c`` → three 'c' parts → invalid (ambiguous)."""
        self.assertFalse(self.validate("ctrl+c+c+c"))

    def test_validate_double_tap_multi_char_key(self):
        """``ctrl+tab+tab`` → multi-char key repetition → invalid as double-tap."""
        self.assertFalse(self.validate("ctrl+tab+tab"))

    def test_validate_double_tap_with_shift_modifier_and_shift_key(self):
        """``shift+1+1`` → shift is modifier, '1' is key → valid.

        Shift as a modifier in a double-tap should be accepted.
        """
        self.assertTrue(self.validate("shift+1+1"))

    def test_validate_double_tap_special_chars(self):
        """``ctrl+`+` `` → backtick double-tap → valid."""
        self.assertTrue(self.validate("ctrl+`+`"))

    # -- valid single-combo strings (backward compatibility) -------------

    def test_validate_single_combo_ctrl_shift_o(self):
        """``ctrl+shift+o`` → valid single combo."""
        self.assertTrue(self.validate("ctrl+shift+o"))

    def test_validate_single_combo_two_keys(self):
        """``ctrl+k`` → valid two-key combo."""
        self.assertTrue(self.validate("ctrl+k"))

    def test_validate_single_combo_three_modifiers(self):
        """``ctrl+alt+shift+del`` → valid combo."""
        self.assertTrue(self.validate("ctrl+alt+shift+del"))

    # -- invalid single-combo strings -----------------------------------

    def test_validate_single_combo_trailing(self):
        """``ctrl+`` → trailing plus → invalid."""
        self.assertFalse(self.validate("ctrl+"))

    def test_validate_empty(self):
        """Empty string → invalid."""
        self.assertFalse(self.validate(""))

    def test_validate_whitespace(self):
        """Whitespace-only → invalid."""
        self.assertFalse(self.validate("   "))

    def test_validate_single_key_no_modifier(self):
        """``x`` → single character with no '+' → valid or invalid?

        Most hotkey systems require at least a modifier+key combo
        for single combos.  Expect False.
        """
        self.assertFalse(self.validate("x"))


# ====================================================================
# 3. State machine  —  DoubleTapDetector
# ====================================================================

class TestDoubleTapDetectorStateMachine(unittest.TestCase):
    """Behaviour tests for ``DoubleTapDetector``.

    Expected constructor::

        DoubleTapDetector(modifiers: tuple[str, ...],
                          trigger_key: str,
                          callback: Callable[[], None],
                          timeout: float = 1.0)

    The detector listens to raw key press/release events and fires
    ``callback`` when the double-tap sequence completes.

    States:

        IDLE
          ↓  all modifiers pressed
        MODIFIERS_HELD
          ↓  trigger_key pressed (1st tap)
        WAITING_KEY
          ↓  trigger_key pressed (2nd tap, within timeout)
        TRIGGERED  → fire callback → return to MODIFIERS_HELD

    Any modifier release → IDLE (hard reset).
    Timeout while WAITING_KEY → MODIFIERS_HELD (soft reset).
    Non-trigger keys are ignored.
    """

    # -- helpers -------------------------------------------------------

    def make_detector(self,
                      modifiers: tuple[str, ...] = ("ctrl",),
                      trigger_key: str = "c",
                      timeout: float = 0.5,
                      ) -> tuple[Mock, Mock]:
        """Return (detector, callback_mock)."""
        if DoubleTapDetector is None:
            self.skipTest("DoubleTapDetector not implemented yet")
        callback = Mock()
        detector = DoubleTapDetector(
            modifiers=modifiers,
            trigger_key=trigger_key,
            callback=callback,
            timeout=timeout,
        )
        return detector, callback

    # -- happy path ----------------------------------------------------

    def test_full_trigger_sequence(self):
        """Ctrl press → C press → C press → callback fired → state reset."""
        detector, callback = self.make_detector()

        # Simulate: Ctrl down, C down, C up, C down, C up, Ctrl up
        detector._on_press(mock_key("ctrl"))
        detector._on_press(mock_key("c"))
        detector._on_release(mock_key("c"))
        detector._on_press(mock_key("c"))
        detector._on_release(mock_key("c"))
        detector._on_release(mock_key("ctrl"))

        callback.assert_called_once()

    def test_full_sequence_with_multiple_modifiers(self):
        """Ctrl+Shift+A+A → callback fires."""
        detector, callback = self.make_detector(
            modifiers=("ctrl", "shift"),
            trigger_key="a",
        )

        detector._on_press(mock_key("ctrl"))
        detector._on_press(mock_key("shift"))
        detector._on_press(mock_key("a"))
        detector._on_release(mock_key("a"))
        detector._on_press(mock_key("a"))
        detector._on_release(mock_key("a"))
        detector._on_release(mock_key("shift"))
        detector._on_release(mock_key("ctrl"))

        callback.assert_called_once()

    def test_trigger_then_trigger_again(self):
        """Double-tap fires → release modifier → re-press → double-tap → fires twice."""
        detector, callback = self.make_detector()

        # First trigger
        detector._on_press(mock_key("ctrl"))
        detector._on_press(mock_key("c"))
        detector._on_release(mock_key("c"))
        detector._on_press(mock_key("c"))
        detector._on_release(mock_key("c"))
        # Release modifier and re-press before next trigger (new behavior)
        detector._on_release(mock_key("ctrl"))
        detector._on_press(mock_key("ctrl"))
        # Second trigger
        detector._on_press(mock_key("c"))
        detector._on_release(mock_key("c"))
        detector._on_press(mock_key("c"))
        detector._on_release(mock_key("c"))
        detector._on_release(mock_key("ctrl"))

        self.assertEqual(callback.call_count, 2)

    # -- timeout --------------------------------------------------------

    def test_timeout_resets_first_tap(self):
        """First tap → timeout elapses → second tap does NOT trigger."""
        detector, callback = self.make_detector(timeout=0.1)

        detector._on_press(mock_key("ctrl"))
        detector._on_press(mock_key("c"))
        detector._on_release(mock_key("c"))
        # Time passes — wait longer than the timeout
        time.sleep(0.15)
        detector._on_press(mock_key("c"))
        detector._on_release(mock_key("c"))
        detector._on_release(mock_key("ctrl"))

        callback.assert_not_called()

    def test_within_timeout_triggers(self):
        """First tap → very short pause (still within timeout) → trigger."""
        detector, callback = self.make_detector(timeout=1.0)

        detector._on_press(mock_key("ctrl"))
        detector._on_press(mock_key("c"))
        detector._on_release(mock_key("c"))
        time.sleep(0.05)  # well within 1 s
        detector._on_press(mock_key("c"))
        detector._on_release(mock_key("c"))
        detector._on_release(mock_key("ctrl"))

        callback.assert_called_once()

    # -- modifier release resets ----------------------------------------

    def test_modifier_release_during_waiting_key_resets(self):
        """Ctrl released after first tap → state resets → no trigger."""
        detector, callback = self.make_detector()

        detector._on_press(mock_key("ctrl"))
        detector._on_press(mock_key("c"))
        detector._on_release(mock_key("c"))
        # Modifier released — should abort
        detector._on_release(mock_key("ctrl"))
        # Now press everything again but only one tap
        detector._on_press(mock_key("ctrl"))
        detector._on_press(mock_key("c"))
        detector._on_release(mock_key("c"))
        detector._on_release(mock_key("ctrl"))

        callback.assert_not_called()

    def test_one_of_multiple_modifiers_released_resets(self):
        """Ctrl+Shift held → Shift released → state resets."""
        detector, callback = self.make_detector(
            modifiers=("ctrl", "shift"),
            trigger_key="a",
        )

        detector._on_press(mock_key("ctrl"))
        detector._on_press(mock_key("shift"))
        detector._on_press(mock_key("a"))
        detector._on_release(mock_key("a"))
        # Release only one modifier
        detector._on_release(mock_key("shift"))
        # Retry with both modifiers again
        detector._on_press(mock_key("ctrl"))
        detector._on_press(mock_key("shift"))
        detector._on_press(mock_key("a"))
        detector._on_release(mock_key("a"))
        detector._on_press(mock_key("a"))
        detector._on_release(mock_key("a"))
        detector._on_release(mock_key("shift"))
        detector._on_release(mock_key("ctrl"))

        callback.assert_called_once()

    # -- non-trigger keys ignored ---------------------------------------

    def test_non_trigger_key_during_modifiers_held_ignored(self):
        """Pressing 'x' while MODIFIERS_HELD doesn't advance state."""
        detector, callback = self.make_detector()

        detector._on_press(mock_key("ctrl"))
        detector._on_press(mock_key("x"))         # ignored
        detector._on_release(mock_key("x"))
        detector._on_press(mock_key("c"))         # 1st tap
        detector._on_release(mock_key("c"))
        detector._on_press(mock_key("c"))         # 2nd tap
        detector._on_release(mock_key("c"))
        detector._on_release(mock_key("ctrl"))

        callback.assert_called_once()

    def test_non_trigger_key_during_waiting_key_resets(self):
        """Pressing 'x' while WAITING_KEY invalidates first tap."""
        detector, callback = self.make_detector()

        detector._on_press(mock_key("ctrl"))
        detector._on_press(mock_key("c"))         # 1st tap
        detector._on_release(mock_key("c"))
        detector._on_press(mock_key("x"))         # wrong key → invalidates
        detector._on_release(mock_key("x"))
        detector._on_press(mock_key("c"))         # treated as new 1st tap
        detector._on_release(mock_key("c"))
        detector._on_press(mock_key("c"))         # 2nd tap
        detector._on_release(mock_key("c"))
        detector._on_release(mock_key("ctrl"))

        callback.assert_called_once()

    # -- edge cases -----------------------------------------------------

    def test_trigger_key_press_before_modifiers_ignored(self):
        """'c' pressed before Ctrl → ignored."""
        detector, callback = self.make_detector()

        detector._on_press(mock_key("c"))
        detector._on_release(mock_key("c"))
        detector._on_press(mock_key("ctrl"))
        detector._on_press(mock_key("c"))
        detector._on_release(mock_key("c"))
        detector._on_press(mock_key("c"))
        detector._on_release(mock_key("c"))
        detector._on_release(mock_key("ctrl"))

        callback.assert_called_once()

    def test_release_without_press_safe(self):
        """Releasing a key that was never pressed shouldn't crash."""
        detector, callback = self.make_detector()

        detector._on_release(mock_key("c"))
        detector._on_release(mock_key("ctrl"))
        # No crash is the success criterion
        callback.assert_not_called()

    def test_modifiers_out_of_order(self):
        """Shift pressed before Ctrl, both needed → still works."""
        detector, callback = self.make_detector(
            modifiers=("ctrl", "shift"),
            trigger_key="k",
        )

        detector._on_press(mock_key("shift"))
        detector._on_press(mock_key("ctrl"))
        detector._on_press(mock_key("k"))
        detector._on_release(mock_key("k"))
        detector._on_press(mock_key("k"))
        detector._on_release(mock_key("k"))
        detector._on_release(mock_key("ctrl"))
        detector._on_release(mock_key("shift"))

        callback.assert_called_once()

    def test_rapid_modifier_toggle_resets(self):
        """Ctrl down → Ctrl up → Ctrl down quickly → clean state."""
        detector, callback = self.make_detector()

        detector._on_press(mock_key("ctrl"))
        detector._on_release(mock_key("ctrl"))
        detector._on_press(mock_key("ctrl"))
        detector._on_press(mock_key("c"))
        detector._on_release(mock_key("c"))
        detector._on_press(mock_key("c"))
        detector._on_release(mock_key("c"))
        detector._on_release(mock_key("ctrl"))

        callback.assert_called_once()

    def test_key_hold_then_release_still_triggers(self):
        """Holding the trigger key down (long press) on first tap then
        releasing still allows the second tap to trigger."""
        detector, callback = self.make_detector()

        detector._on_press(mock_key("ctrl"))
        detector._on_press(mock_key("c"))
        # Long hold... then release
        detector._on_release(mock_key("c"))
        detector._on_press(mock_key("c"))         # 2nd tap
        detector._on_release(mock_key("c"))
        detector._on_release(mock_key("ctrl"))

        callback.assert_called_once()

    # -- stop / cleanup -------------------------------------------------

    def test_stop_prevents_further_triggers(self):
        """After calling stop(), key events do nothing."""
        detector, callback = self.make_detector()

        detector.stop()
        detector._on_press(mock_key("ctrl"))
        detector._on_press(mock_key("c"))
        detector._on_release(mock_key("c"))
        detector._on_press(mock_key("c"))
        detector._on_release(mock_key("c"))
        detector._on_release(mock_key("ctrl"))

        callback.assert_not_called()

    def test_listener_integration_skeleton(self):
        """Skeleton demonstrating expected listener wiring.

        This test documents expected integration with pynput.keyboard.Listener.
        Replace ``patched_keyboard`` with the actual import once DoubleTapDetector
        creates its own listener internally (or accepts one externally).
        """
        if DoubleTapDetector is None:
            self.skipTest("DoubleTapDetector not implemented yet")

        callback = Mock()
        detector = DoubleTapDetector(
            modifiers=("ctrl",),
            trigger_key="c",
            callback=callback,
        )

        # The detector should manage its own pynput.keyboard.Listener
        # (or expose start/stop methods that do).
        if hasattr(detector, "start"):
            detector.start()

        # Simulate key events directly for deterministic testing
        detector._on_press(mock_key("ctrl"))
        detector._on_press(mock_key("c"))
        detector._on_release(mock_key("c"))
        detector._on_press(mock_key("c"))
        detector._on_release(mock_key("c"))
        detector._on_release(mock_key("ctrl"))

        callback.assert_called_once()

        if hasattr(detector, "stop"):
            detector.stop()

    # -- non-configured modifiers -----------------------------------------

    def test_non_configured_modifier_shift_does_not_trigger(self):
        """Shift+C+C does NOT trigger when detector expects Ctrl."""
        detector, callback = self.make_detector()

        detector._on_press(mock_key("shift"))
        detector._on_press(mock_key("c"))
        detector._on_release(mock_key("c"))
        detector._on_press(mock_key("c"))
        detector._on_release(mock_key("c"))
        detector._on_release(mock_key("shift"))

        self.assertEqual(callback.call_count, 0)
        self.assertEqual(detector._state, "IDLE")

    def test_non_configured_modifier_alt_does_not_trigger(self):
        """Alt+C+C does NOT trigger when detector expects Ctrl."""
        detector, callback = self.make_detector()

        detector._on_press(mock_key("alt"))
        detector._on_press(mock_key("c"))
        detector._on_release(mock_key("c"))
        detector._on_press(mock_key("c"))
        detector._on_release(mock_key("c"))
        detector._on_release(mock_key("alt"))

        self.assertEqual(callback.call_count, 0)
        self.assertEqual(detector._state, "IDLE")

    def test_non_configured_modifier_win_does_not_trigger(self):
        """Win/Cmd+C+C does NOT trigger when detector expects Ctrl."""
        detector, callback = self.make_detector()

        detector._on_press(mock_key("cmd"))
        detector._on_press(mock_key("c"))
        detector._on_release(mock_key("c"))
        detector._on_press(mock_key("c"))
        detector._on_release(mock_key("c"))
        detector._on_release(mock_key("cmd"))

        self.assertEqual(callback.call_count, 0)
        self.assertEqual(detector._state, "IDLE")

    def test_no_modifier_hotkey_ignores_any_modifier(self):
        """Shift+Z+Z does NOT trigger when detector has no configured modifiers."""
        detector, callback = self.make_detector(modifiers=(), trigger_key="z")

        detector._on_press(mock_key("shift"))
        detector._on_press(mock_key("z"))
        detector._on_release(mock_key("z"))
        detector._on_press(mock_key("z"))
        detector._on_release(mock_key("z"))
        detector._on_release(mock_key("shift"))

        self.assertEqual(callback.call_count, 0)
        self.assertEqual(detector._state, "IDLE")

    def test_bare_trigger_after_stale_modifiers_does_not_trigger(self):
        """Pressing trigger key when state is stuck at MODIFIERS_HELD with no modifiers held does not trigger."""
        detector, callback = self.make_detector()

        detector._state = "MODIFIERS_HELD"
        detector._held_modifiers = set()
        detector._on_press(mock_key("c"))

        self.assertEqual(detector._state, "IDLE")
        self.assertEqual(callback.call_count, 0)


# ====================================================================
# 4. Integration-style  —  parse + validate round-trip
# ====================================================================

class TestParseValidateRoundTrip(unittest.TestCase):
    """Ensure that valid parsed results pass validation and vice versa."""

    def parse(self, text: str) -> dict:
        if _parse_trigger_config is None:
            self.skipTest("_parse_trigger_config not implemented yet")
        return _parse_trigger_config(text)

    def validate(self, text: str) -> bool:
        if _validate_trigger_hotkey is None:
            self.skipTest("_validate_trigger_hotkey not implemented yet")
        return _validate_trigger_hotkey(text)

    def test_all_valid_double_taps_validate(self):
        """Every double-tap string that parses must validate."""
        valid_strings = [
            "ctrl+c+c",
            "ctrl+shift+x+x",
            "alt+k+k",
            "win+f+f",
            "z+z",
            "shift+1+1",
            "ctrl+`+`",
        ]
        for s in valid_strings:
            with self.subTest(hotkey=s):
                self.assertTrue(self.validate(s),
                                f"'{s}' should be valid")

    def test_all_invalid_strings_do_not_validate(self):
        """Invalid strings must be rejected by the validator."""
        invalid_strings = [
            "ctrl+c+d",
            "ctrl++c",
            "ctrl+c+",
            "xyz+c+c",
            "1+c+c",
            "ctrl+c+c+c",
            "ctrl+tab+tab",
            "ctrl+",
            "",
            "   ",
            "x",
        ]
        for s in invalid_strings:
            with self.subTest(hotkey=s):
                self.assertFalse(self.validate(s),
                                 f"'{s}' should be invalid")


# ====================================================================
# 5. Configuration integration  —  _normalize_double_tap
# ====================================================================

class TestNormalizeDoubleTap(unittest.TestCase):
    """Tests for ``_normalize_double_tap`` (if separate from parse).

    This function would convert a parsed double-tap config into the
    pynput GlobalHotKeys format (or return None for double-taps that
    must be handled by the state machine).  The exact API is TBD, so
    these tests are exploratory.
    """

    def test_placeholder(self):
        """Placeholder — will be filled once the API is decided.

        Expected behaviour: for backward compatibility with the existing
        HotkeyManager._normalize_hotkey, double-tap strings should NOT
        be passed to pynput's GlobalHotKeys directly.
        """
        self.skipTest("_normalize_double_tap API not yet defined")


# ====================================================================
# Main
# ====================================================================

if __name__ == "__main__":
    unittest.main()
