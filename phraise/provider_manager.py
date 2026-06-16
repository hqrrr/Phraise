# PhrAIse - AI writing assistant
# License: GNU GPLv3
# GitHub: https://github.com/hqrrr/Phraise
# Author: hqrrr
#
# Description: LLM provider and model list management.
"""Dynamic provider list management.

Fetches the latest OpenAI-compatible provider list from models.dev and falls
back to a curated local list when the network is unavailable. The provider list
is cached on disk so it is available immediately on subsequent launches.
"""

from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path
from typing import Any, Callable

import httpx

from .config import CONFIG_DIR
from .dispatch import run_on_main
from .error_log import write_error


CACHE_FILE = CONFIG_DIR / "providers_cache.json"
CACHE_TTL_SECONDS = 24 * 60 * 60  # 24 hours
FETCH_TIMEOUT_SECONDS = 10.0

# Curated local fallback of common OpenAI-compatible providers.
# This list is used when models.dev cannot be reached and no fresh cache exists.
LOCAL_PROVIDERS: list[dict[str, str]] = [
    {"id": "openai", "label": "OpenAI", "api_base": "https://api.openai.com/v1"},
    {"id": "claude", "label": "Claude (Anthropic)", "api_base": "https://api.anthropic.com/v1"},
    {"id": "gemini", "label": "Gemini (Google)", "api_base": "https://generativelanguage.googleapis.com/v1beta/openai/"},
    {"id": "deepseek", "label": "DeepSeek", "api_base": "https://api.deepseek.com/v1"},
    {"id": "openrouter", "label": "OpenRouter", "api_base": "https://openrouter.ai/api/v1"},
    {"id": "kimi", "label": "Kimi (Moonshot)", "api_base": "https://api.moonshot.cn/v1"},
    {"id": "glm", "label": "GLM (Zhipu)", "api_base": "https://open.bigmodel.cn/api/paas/v4"},
    {"id": "qwen", "label": "Qwen (Tongyi)", "api_base": "https://dashscope.aliyuncs.com/compatible-mode/v1"},
    {"id": "siliconflow", "label": "SiliconFlow", "api_base": "https://api.siliconflow.cn/v1"},
    {"id": "groq", "label": "Groq", "api_base": "https://api.groq.com/openai/v1"},
    {"id": "together", "label": "Together AI", "api_base": "https://api.together.xyz/v1"},
    {"id": "fireworks", "label": "Fireworks AI", "api_base": "https://api.fireworks.ai/inference/v1"},
    {"id": "perplexity", "label": "Perplexity", "api_base": "https://api.perplexity.ai"},
    {"id": "xai", "label": "xAI (Grok)", "api_base": "https://api.x.ai/v1"},
    {"id": "mistral", "label": "Mistral AI", "api_base": "https://api.mistral.ai/v1"},
    {"id": "cohere", "label": "Cohere", "api_base": "https://api.cohere.ai/compatibility/v1"},
    {"id": "voyageai", "label": "Voyage AI", "api_base": "https://api.voyageai.com/v1"},
    {"id": "hyperbolic", "label": "Hyperbolic", "api_base": "https://api.hyperbolic.xyz/v1"},
]

_PROVIDER_LOCK = threading.Lock()
_PROVIDER_STATE: list[dict[str, str]] | None = None
_INIT_STARTED = False


def _is_valid_api_base(value: Any) -> bool:
    """Return True if value looks like an HTTP(S) base URL."""
    if not isinstance(value, str):
        return False
    return value.startswith(("http://", "https://"))


def _sort_providers(providers: list[dict[str, str]]) -> list[dict[str, str]]:
    """Sort providers alphabetically by label, stable by id."""
    return sorted(providers, key=lambda p: (p.get("label", "").lower(), p.get("id", "")))


def _load_cache() -> list[dict[str, str]] | None:
    """Load provider list from disk cache if it exists and is not stale."""
    try:
        if not CACHE_FILE.exists():
            return None
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            payload = json.load(f)
        cached_at = payload.get("cached_at")
        if not isinstance(cached_at, (int, float)):
            return None
        if time.time() - cached_at > CACHE_TTL_SECONDS:
            return None
        providers = payload.get("providers")
        if not isinstance(providers, list):
            return None
        valid: list[dict[str, str]] = []
        for p in providers:
            if isinstance(p, dict) and _is_valid_api_base(p.get("api_base")):
                valid.append(
                    {
                        "id": str(p.get("id", "")),
                        "label": str(p.get("label", "")),
                        "api_base": str(p.get("api_base", "")),
                    }
                )
        return valid if valid else None
    except (OSError, json.JSONDecodeError):
        return None


def _save_cache(providers: list[dict[str, str]]) -> None:
    """Persist provider list to disk cache atomically."""
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        tmp = CACHE_FILE.with_suffix(".tmp")
        payload = {"cached_at": time.time(), "providers": providers}
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        os.replace(tmp, CACHE_FILE)
    except (OSError, TypeError) as e:
        write_error(e, "provider_manager._save_cache")


def _merge_providers(
    fetched: list[dict[str, str]], local: list[dict[str, str]]
) -> list[dict[str, str]]:
    """Merge fetched and local providers. Fetched entries win by id."""
    merged: dict[str, dict[str, str]] = {}
    for p in local:
        merged[p["id"]] = p
    for p in fetched:
        merged[p["id"]] = p
    return list(merged.values())


def fetch_providers_from_api(timeout: float = FETCH_TIMEOUT_SECONDS) -> list[dict[str, str]] | None:
    """Fetch provider list from models.dev.

    Returns a list of providers with explicit OpenAI-compatible base URLs, or
    None if the request fails or no usable providers are found.
    """
    try:
        response = httpx.get("https://models.dev/api.json", timeout=timeout)
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, dict):
            return None
        fetched: list[dict[str, str]] = []
        for provider_id, info in data.items():
            if not isinstance(info, dict):
                continue
            api_base = info.get("api")
            if not _is_valid_api_base(api_base):
                continue
            name = info.get("name") or provider_id
            fetched.append(
                {
                    "id": str(provider_id),
                    "label": str(name),
                    "api_base": str(api_base),
                }
            )
        return fetched if fetched else None
    except Exception as e:
        write_error(e, "provider_manager.fetch_providers_from_api")
        return None


def get_providers() -> list[dict[str, str]]:
    """Return the current provider list, initializing from cache/fallback if needed.

    Thread-safe. Does not block on network I/O; use init_providers() to refresh
    asynchronously from the network.
    """
    global _PROVIDER_STATE
    with _PROVIDER_LOCK:
        if _PROVIDER_STATE is None:
            cached = _load_cache()
            if cached is not None:
                _PROVIDER_STATE = _sort_providers(cached)
            else:
                _PROVIDER_STATE = _sort_providers(list(LOCAL_PROVIDERS))
        return list(_PROVIDER_STATE)


def _set_providers(providers: list[dict[str, str]]) -> None:
    """Replace the in-memory provider list and persist to cache."""
    global _PROVIDER_STATE
    sorted_providers = _sort_providers(providers)
    with _PROVIDER_LOCK:
        _PROVIDER_STATE = sorted_providers
    _save_cache(sorted_providers)


def init_providers(callback: Callable[[], None] | None = None) -> None:
    """Start a background fetch from models.dev and refresh the provider list.

    The callback, if provided, is invoked on the main thread after the merge.
    Safe to call multiple times; only one fetch is active at a time.
    """
    global _INIT_STARTED
    with _PROVIDER_LOCK:
        if _INIT_STARTED:
            return
        _INIT_STARTED = True

    def _do_fetch():
        try:
            fetched = fetch_providers_from_api()
            local = list(LOCAL_PROVIDERS)
            if fetched is not None:
                merged = _merge_providers(fetched, local)
                _set_providers(merged)
            if callback is not None:
                run_on_main(callback)
        except Exception as e:
            write_error(e, "provider_manager.init_providers")
            if callback is not None:
                run_on_main(callback)

    threading.Thread(target=_do_fetch, daemon=True).start()


def reset_providers() -> None:
    """Reset the in-memory provider list and clear disk cache.

    Intended primarily for tests.
    """
    global _PROVIDER_STATE, _INIT_STARTED
    with _PROVIDER_LOCK:
        _PROVIDER_STATE = None
        _INIT_STARTED = False
    try:
        if CACHE_FILE.exists():
            CACHE_FILE.unlink()
    except OSError:
        pass
