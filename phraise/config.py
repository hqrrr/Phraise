import copy
import json
import os
import tempfile
import threading
from pathlib import Path
from typing import Any, Callable

from .error_log import write_error

APP_NAME = "PhrAIse"
_APPDATA = os.environ.get("APPDATA")
if _APPDATA is None:
    try:
        _APPDATA = str(Path.home() / "AppData" / "Roaming")
    except RuntimeError:
        _APPDATA = tempfile.gettempdir()
CONFIG_DIR = Path(_APPDATA) / APP_NAME
CONFIG_FILE = CONFIG_DIR / "settings.json"

DEFAULT_CONFIG: dict[str, Any] = {
    "models": {
        "model_1": {
            "provider": "",
            "api_base": "",
            "api_key": "",
            "model_name": "",
            "temperature": 0.3,
            "max_tokens": 4096,
            "extra_params": "",
            "mode": "remote",
        },
        "model_2": {
            "provider": "",
            "api_base": "",
            "api_key": "",
            "model_name": "",
            "temperature": 0.5,
            "max_tokens": 4096,
            "extra_params": "",
            "mode": "remote",
        },
    },
    "styles": [
        {"id": "concise", "label": "Concise", "prompt_keyword": "concise and brief"},
        {"id": "formal", "label": "Formal", "prompt_keyword": "formal and professional"},
        {"id": "natural", "label": "Natural", "prompt_keyword": "natural and fluent"},
    ],
    "floating_ball": {
        "position_x": 1800,
        "position_y": 500,
        "size": 30,
        "opacity": 0.50,
        "theme": "dark",
    },
    "floating_window": {
        "position_x": 1400,
        "position_y": 600,
        "width": 400,
        "height": 500,
        "opacity": 0.95,
        "always_on_top": True,
        "last_tab": "optimize",
        "last_style": "concise",
    },
    "trigger": {
        "hotkey_trigger": "ctrl+c+c",
        "hotkey_toggle_ball": "ctrl+shift+b",
    },
    "blacklist": [
        "powershell.exe", "cmd.exe", "WindowsTerminal.exe",
    ],
    "translation": {
        "source_lang": "auto",
        "target_lang": "zh-CN",
    },
    "appearance": {
        "theme": "dark",
        "custom_css": "",
    },
    "general": {
        "language": "en",
        "start_with_windows": False,
        "start_minimized": False,
        "replace_auto_close": False,
        "theme": "dark",
        "optimize_model": "",
        "translate_model": "",
    },
    "harper": {
        "dialect": "American",
        "linters": {
            "SpellCheck": True,
            "RepeatedWords": True,
            "LongSentences": False,
            "Spaces": True,
            "AnA": True,
            "UnclosedQuotes": True,
            "WrongApostrophe": True,
        },
        "timeout_secs": 30,
    },
}


class Config:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._data = None
                    cls._instance._listeners: list[Callable] = []
        return cls._instance

    def __init__(self):
        if self._data is None:
            self._load()

    def _load(self):
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                loaded.pop("whitelist", None)
                if "trigger" in loaded:
                    loaded["trigger"].pop("auto_on_pause", None)
                    loaded["trigger"].pop("pause_delay_ms", None)
                    if "hotkey_trigger" not in loaded["trigger"]:
                        old = loaded["trigger"].get("hotkey_optimize", "")
                        if not old:
                            old = loaded["trigger"].get("hotkey_translate", "")
                        if old:
                            loaded["trigger"]["hotkey_trigger"] = old
                    loaded["trigger"].pop("hotkey_optimize", None)
                    loaded["trigger"].pop("hotkey_translate", None)
                self._data = self._deep_merge(DEFAULT_CONFIG, loaded)
            except (json.JSONDecodeError, OSError):
                self._data = copy.deepcopy(DEFAULT_CONFIG)
                self.save()
        else:
            self._data = copy.deepcopy(DEFAULT_CONFIG)
            self.save()
        self._validate()

    def _save_unlocked(self):
        """Persist ``_data`` to disk atomically.

        Caller MUST hold ``self._lock``.  Writes to a ``.tmp`` sibling then
        uses ``os.replace()`` so that a crash mid-write never corrupts the
        real ``settings.json``.
        """
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        tmp = CONFIG_FILE.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self._data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, CONFIG_FILE)

    def save(self):
        with self._lock:
            self._save_unlocked()

    def get(self, *keys: str, default=None):
        node = self._data
        for k in keys:
            if isinstance(node, dict):
                node = node.get(k)
                if node is None:
                    return default
            else:
                return default
        return node

    def set(self, *keys: str, value):
        with self._lock:
            node = self._data
            for k in keys[:-1]:
                if k not in node:
                    node[k] = {}
                node = node[k]
            node[keys[-1]] = value
            self._save_unlocked()
        self._notify()

    def update_section(self, section: str, updates: dict):
        with self._lock:
            if section in self._data:
                self._data[section].update(updates)
            self._save_unlocked()
        self._notify()

    def add_listener(self, callback: Callable):
        self._listeners.append(callback)

    def remove_listener(self, callback: Callable):
        if callback in self._listeners:
            self._listeners.remove(callback)

    def _notify(self):
        for cb in self._listeners:
            try:
                cb()
            except Exception as e:
                write_error(e, "config._notify")
                pass

    @staticmethod
    def _deep_merge(base: dict, override: dict) -> dict:
        result = copy.deepcopy(base)
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = Config._deep_merge(result[key], value)
            else:
                result[key] = value
        return result

    def _validate(self):
        """Fix malformed config values with per-field fallbacks.

        Called after _deep_merge in _load() to ensure critical fields
        have correct types before they reach downstream consumers.
        """
        if "max_tokens" in self._data:
            val = self._data["max_tokens"]
            if type(val) is not int:
                write_error(
                    ValueError(
                        f"max_tokens has type {type(val).__name__}, "
                        f"expected int; using default 1024"
                    ),
                    "config._validate.max_tokens",
                )
                self._data["max_tokens"] = 1024

        if "models" in self._data:
            val = self._data["models"]
            if not isinstance(val, dict):
                write_error(
                    ValueError(
                        f"models has type {type(val).__name__}, "
                        f"expected dict; using default empty dict"
                    ),
                    "config._validate.models",
                )
                self._data["models"] = {}

        if "styles" in self._data:
            val = self._data["styles"]
            if not isinstance(val, list) or not val:
                write_error(
                    ValueError(
                        f"styles has type {type(val).__name__}, "
                        f"expected non-empty list; using defaults"
                    ),
                    "config._validate.styles",
                )
                self._data["styles"] = list(DEFAULT_CONFIG["styles"])

        if "general" in self._data and isinstance(self._data["general"], dict):
            for field in ("optimize_model", "translate_model"):
                val = self._data["general"].get(field)
                if val is not None and not isinstance(val, str):
                    write_error(
                        ValueError(
                            f"general.{field} has type {type(val).__name__}, "
                            f"expected str; defaulting to ''"
                        ),
                        f"config._validate.general.{field}",
                    )
                    self._data["general"][field] = ""

    def is_model_local(self, slot_name: str) -> bool:
        """Check if a model slot is configured for local (Harper) mode."""
        mode = self.get("models", slot_name, "mode", default="remote")
        return mode == "local"

    @property
    def data(self):
        return self._data


config = Config()
