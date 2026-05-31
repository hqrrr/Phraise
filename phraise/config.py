import json
import os
import threading
from pathlib import Path
from typing import Any, Callable

from .error_log import write_error

APP_NAME = "PhrAIse"
CONFIG_DIR = Path(os.environ["APPDATA"]) / APP_NAME
CONFIG_FILE = CONFIG_DIR / "settings.json"

DEFAULT_CONFIG: dict[str, Any] = {
    "models": {
        "model_1": {
            "provider": "gemini",
            "api_base": "https://generativelanguage.googleapis.com/v1beta/openai/",
            "api_key": "",
            "model_name": "gemini-2.0-flash",
            "temperature": 0.3,
            "max_tokens": 4096,
            "extra_params": "",
        },
        "model_2": {
            "provider": "deepseek",
            "api_base": "https://api.deepseek.com/v1",
            "api_key": "",
            "model_name": "deepseek-chat",
            "temperature": 0.5,
            "max_tokens": 8192,
            "extra_params": "",
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
        "optimize_model": "model_1",
        "translate_model": "model_2",
    },
}


class Config:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
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
                self._data = dict(DEFAULT_CONFIG)
                self.save()
        else:
            self._data = dict(DEFAULT_CONFIG)
            self.save()

    def save(self):
        with self._lock:
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(self._data, f, ensure_ascii=False, indent=2)

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
        node = self._data
        for k in keys[:-1]:
            if k not in node:
                node[k] = {}
            node = node[k]
        node[keys[-1]] = value
        self.save()
        self._notify()

    def update_section(self, section: str, updates: dict):
        if section in self._data:
            self._data[section].update(updates)
        self.save()
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
        result = dict(base)
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = Config._deep_merge(result[key], value)
            else:
                result[key] = value
        return result

    @property
    def data(self):
        return self._data


config = Config()
