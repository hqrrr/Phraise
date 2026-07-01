# PhrAIse - AI writing assistant
# License: GNU GPLv3
# GitHub: https://github.com/hqrrr/Phraise
# Author: hqrrr
#
# Description: Global hotkey listener and registration.
import atexit
import re
import threading
import time
from collections.abc import Callable

from pynput import keyboard

from .config import config
from .error_log import write_error


def _parse_trigger_config(text: str):
    """Parse a hotkey config string. Returns dict with is_double_tap, modifiers, key."""
    if not text or not text.strip():
        return {"is_double_tap": False, "modifiers": (), "key": ""}
    parts = [p.strip() for p in text.split("+")]
    parts_lower = [p.lower() for p in parts]
    if len(parts) >= 2 and parts_lower[-1] == parts_lower[-2] and len(parts[-1]) == 1:
        return {"is_double_tap": True, "modifiers": tuple(parts[:-2]), "key": parts_lower[-1]}
    return {"is_double_tap": False, "modifiers": (), "key": ""}


def _validate_trigger_hotkey(text: str) -> bool:
    """Validate a hotkey config string (double-tap or single combo)."""
    if not text or not text.strip():
        return False
    parts = [p.strip().lower() for p in text.split("+")]
    if not parts or any(not p for p in parts):
        return False

    modifiers = {"ctrl", "control", "alt", "shift", "win", "cmd", "super"}

    # Check for double-tap pattern: last two parts identical
    if len(parts) >= 2 and parts[-1] == parts[-2]:
        if len(parts[-1]) == 1:
            # Single char double-tap: all preceding parts must be modifiers
            mod_parts = parts[:-2]
            return all(m in modifiers for m in mod_parts)
        else:
            # Multi-char repetition (tab+tab, shift+shift) → invalid
            return False

    # Single combo: at least 1 modifier, exactly 1 non-modifier, no unknown parts
    non_mod = [p for p in parts if p not in modifiers]
    mod_parts = [p for p in parts if p in modifiers]
    if len(non_mod) != 1 or len(mod_parts) == 0:
        return False
    # All parts must be accounted for
    return len(non_mod) + len(mod_parts) == len(parts)


class DoubleTapDetector:
    """Detects 'hold modifier(s), press key twice quickly' sequences using pynput."""

    MODIFIER_KEY_MAP = {
        "ctrl": {keyboard.Key.ctrl_l, keyboard.Key.ctrl_r},
        "control": {keyboard.Key.ctrl_l, keyboard.Key.ctrl_r},
        "shift": {keyboard.Key.shift_l, keyboard.Key.shift_r},
        "alt": {keyboard.Key.alt_l, keyboard.Key.alt_r},
        "cmd": {keyboard.Key.cmd_l, keyboard.Key.cmd_r},
        "win": {keyboard.Key.cmd_l, keyboard.Key.cmd_r},
        "super": {keyboard.Key.cmd_l, keyboard.Key.cmd_r},
    }

    _MODIFIER_ALIASES = {"control": "ctrl", "win": "cmd", "super": "cmd"}

    def __init__(self, modifiers, trigger_key, callback, timeout=0.5):
        self._modifiers = set()
        for m in modifiers:
            ml = m.lower()
            self._modifiers.add(self._MODIFIER_ALIASES.get(ml, ml))
        self._trigger_key = trigger_key.lower()
        self._callback = callback
        self._tap_timeout = timeout
        self._state = "IDLE"
        self._held_modifiers = set()
        self._timer = None
        self._listener = None
        self._lock = threading.Lock()
        self._callback_running = False
        self._running = True

    def start(self):
        if self._listener is not None:
            return
        self._running = True
        self._listener = keyboard.Listener(
            on_press=self._on_press,
            on_release=self._on_release,
            suppress=False,
        )
        t = threading.Thread(target=self._listener.run, daemon=True)
        t.start()

    def stop(self):
        self._running = False
        self._cancel_timer()
        if self._listener:
            try:
                self._listener.stop()
            except Exception:
                pass
            self._listener = None

    def _key_matches_trigger(self, key, key_name: str) -> bool:
        if key_name == self._trigger_key:
            return True
        try:
            if hasattr(key, 'vk') and key.vk == ord(self._trigger_key.upper()):
                return True
        except Exception:
            pass
        return False

    def _on_press(self, key):
        if not self._running:
            return
        key_name = self._key_name(key)
        if key_name is None:
            return

        fire_callback = False
        with self._lock:
            if self._callback_running:
                return

            is_modifier = False
            for mod_name, mod_keys in self.MODIFIER_KEY_MAP.items():
                if key in mod_keys or key_name == mod_name:
                    is_modifier = True
                    self._held_modifiers.add(mod_name)
                    if self._state == "IDLE" and self._modifiers and mod_name in self._modifiers:
                        self._state = "MODIFIERS_HELD"
                    break

            if is_modifier:
                return

            if self._state == "IDLE":
                return

            if self._key_matches_trigger(key, key_name):
                if self._modifiers and not self._modifiers.issubset(self._held_modifiers):
                    self._reset()
                    return
                if self._state == "MODIFIERS_HELD":
                    self._state = "WAITING_KEY"
                    self._start_timer()
                elif self._state == "WAITING_KEY":
                    self._cancel_timer()
                    self._state = "IDLE"
                    self._held_modifiers.clear()
                    fire_callback = True
                    self._callback_running = True
            else:
                if self._state == "WAITING_KEY":
                    self._cancel_timer()
                    self._state = "MODIFIERS_HELD"

        if fire_callback:
            try:
                self._callback()
            except Exception as e:
                write_error(e, "DoubleTapDetector.callback")
            finally:
                with self._lock:
                    self._callback_running = False

    def _on_release(self, key):
        if not self._running:
            return
        key_name = self._key_name(key)
        if key_name is None:
            return
        with self._lock:
            for mod_name, mod_keys in self.MODIFIER_KEY_MAP.items():
                if key in mod_keys or key_name == mod_name:
                    self._held_modifiers.discard(mod_name)
                    if mod_name in self._modifiers:
                        self._reset()
                    break

    def _key_name(self, key):
        try:
            return key.char.lower()
        except AttributeError:
            if hasattr(key, "name") and key.name:
                return key.name.lower()
            return None

    def _reset(self):
        self._state = "IDLE"
        self._held_modifiers.clear()
        self._cancel_timer()

    def _start_timer(self):
        self._cancel_timer()
        self._timer = threading.Timer(self._tap_timeout, self._on_timeout)
        self._timer.daemon = True
        self._timer.start()

    def _cancel_timer(self):
        if self._timer:
            self._timer.cancel()
            self._timer = None

    def _on_timeout(self):
        with self._lock:
            if self._state == "WAITING_KEY":
                if self._modifiers.issubset(self._held_modifiers):
                    self._state = "MODIFIERS_HELD"
                else:
                    self._state = "IDLE"


class HotkeyManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._listener: keyboard.GlobalHotKeys | None = None
        self._trigger_detector: DoubleTapDetector | None = None
        self._handlers: dict[str, Callable] = {}
        self._lock = threading.Lock()
        self._running = False
        atexit.register(self.stop)

    def start(self):
        if self._running:
            return
        self._running = True
        self._update_listener()

    def stop(self):
        self._running = False
        if self._trigger_detector:
            self._trigger_detector.stop()
            self._trigger_detector = None
        if self._listener:
            try:
                self._listener.stop()
            except Exception as e:
                write_error(e, "hotkeys.stop")
                pass
            self._listener = None

    def register(self, action: str, callback: Callable):
        self._handlers[action] = callback
        if self._running:
            self._update_listener()

    def unregister(self, action: str):
        self._handlers.pop(action, None)
        if self._running:
            self._update_listener()

    def refresh(self):
        if self._running:
            self._update_listener()

    def _update_listener(self):
        if self._listener:
            try:
                self._listener.stop()
            except Exception as e:
                write_error(e, "hotkeys._update_listener:stop")
                pass
            self._listener = None
        if self._trigger_detector:
            self._trigger_detector.stop()
            self._trigger_detector = None

        hotkey_map: dict[str, Callable] = {}

        key_trigger = config.get("trigger", "hotkey_trigger", default="ctrl+c+c")
        key_toggle = config.get("trigger", "hotkey_toggle_ball", default="ctrl+shift+b")

        if key_trigger and "trigger" in self._handlers:
            parsed = _parse_trigger_config(key_trigger)
            if parsed["is_double_tap"]:
                self._trigger_detector = DoubleTapDetector(
                    modifiers=parsed["modifiers"],
                    trigger_key=parsed["key"],
                    callback=self._handlers["trigger"],
                )
                self._trigger_detector.start()
            else:
                hotkey_map[self._normalize_hotkey(key_trigger)] = self._handlers["trigger"]

        if key_toggle and "toggle_ball" in self._handlers:
            hotkey_map[self._normalize_hotkey(key_toggle)] = self._handlers["toggle_ball"]

        if hotkey_map:
            try:
                self._listener = keyboard.GlobalHotKeys(hotkey_map)
                thread = threading.Thread(target=self._listener.run, daemon=True)
                thread.start()
            except Exception as e:
                write_error(e, "hotkeys._update_listener:create")
                self._listener = None

    @staticmethod
    def _normalize_hotkey(hotkey_str: str) -> str:
        if not hotkey_str:
            return ""
        parts = [p.strip() for p in hotkey_str.split("+")]
        normalized = []
        for p in parts:
            pl = p.lower()
            if pl in ("ctrl", "control"):
                normalized.append("<ctrl>")
            elif pl in ("alt",):
                normalized.append("<alt>")
            elif pl in ("shift",):
                normalized.append("<shift>")
            elif pl in ("cmd", "win", "super"):
                normalized.append("<cmd>")
            else:
                normalized.append(pl)
        return "+".join(normalized)


hotkey_manager = HotkeyManager()
