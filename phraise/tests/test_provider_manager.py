"""Tests for provider_manager fetch/filter/cache/fallback logic."""

import json
import os
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from phraise import provider_manager
from phraise.provider_manager import (
    CACHE_TTL_SECONDS,
    LOCAL_PROVIDERS,
    fetch_providers_from_api,
    get_providers,
    init_providers,
    reset_providers,
    _load_cache,
    _merge_providers,
    _save_cache,
)


class TestLocalProviders(unittest.TestCase):
    """LOCAL_PROVIDERS fallback list."""

    def test_local_providers_have_required_fields(self):
        for p in LOCAL_PROVIDERS:
            self.assertIn("id", p)
            self.assertIn("label", p)
            self.assertIn("api_base", p)
            self.assertTrue(p["api_base"].startswith(("http://", "https://")))

    def test_local_providers_known_keys(self):
        ids = {p["id"] for p in LOCAL_PROVIDERS}
        for key in ("openai", "claude", "gemini", "deepseek", "openrouter",
                    "kimi", "glm", "qwen", "siliconflow", "groq", "together"):
            self.assertIn(key, ids)

    def test_local_providers_no_duplicate_ids(self):
        ids = [p["id"] for p in LOCAL_PROVIDERS]
        self.assertEqual(len(ids), len(set(ids)))

    def test_get_providers_returns_local_fallback(self):
        reset_providers()
        providers = get_providers()
        self.assertEqual(len(providers), len(LOCAL_PROVIDERS))
        ids = {p["id"] for p in providers}
        self.assertIn("openai", ids)


class TestFetchProviders(unittest.TestCase):
    """Network fetch from models.dev."""

    def test_fetch_success_filters_api_null(self):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "openai": {"id": "openai", "name": "OpenAI", "api": None},
            "deepseek": {"id": "deepseek", "name": "DeepSeek", "api": "https://api.deepseek.com/v1"},
        }
        mock_response.raise_for_status = MagicMock()
        with patch("phraise.provider_manager.httpx.get", return_value=mock_response):
            result = fetch_providers_from_api(timeout=5)
        self.assertIsNotNone(result)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["id"], "deepseek")

    def test_fetch_success_maps_fields(self):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "deepseek": {"id": "deepseek", "name": "DeepSeek", "api": "https://api.deepseek.com/v1"},
        }
        mock_response.raise_for_status = MagicMock()
        with patch("phraise.provider_manager.httpx.get", return_value=mock_response):
            result = fetch_providers_from_api(timeout=5)
        self.assertIsNotNone(result)
        p = result[0]
        self.assertEqual(p["id"], "deepseek")
        self.assertEqual(p["label"], "DeepSeek")
        self.assertEqual(p["api_base"], "https://api.deepseek.com/v1")

    def test_fetch_invalid_api_base_excluded(self):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "bad": {"id": "bad", "name": "Bad", "api": "not-a-url"},
            "good": {"id": "good", "name": "Good", "api": "https://example.com/v1"},
        }
        mock_response.raise_for_status = MagicMock()
        with patch("phraise.provider_manager.httpx.get", return_value=mock_response):
            result = fetch_providers_from_api(timeout=5)
        self.assertIsNotNone(result)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["id"], "good")

    def test_fetch_empty_providers_returns_none(self):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "openai": {"id": "openai", "name": "OpenAI", "api": None},
        }
        mock_response.raise_for_status = MagicMock()
        with patch("phraise.provider_manager.httpx.get", return_value=mock_response):
            result = fetch_providers_from_api(timeout=5)
        self.assertIsNone(result)

    def test_fetch_timeout_returns_none(self):
        with patch("phraise.provider_manager.httpx.get", side_effect=TimeoutError):
            result = fetch_providers_from_api(timeout=5)
        self.assertIsNone(result)

    def test_fetch_http_error_returns_none(self):
        import httpx
        with patch("phraise.provider_manager.httpx.get", side_effect=httpx.HTTPError("fail")):
            result = fetch_providers_from_api(timeout=5)
        self.assertIsNone(result)

    def test_fetch_invalid_json_returns_none(self):
        mock_response = MagicMock()
        mock_response.json.side_effect = json.JSONDecodeError("fail", "", 0)
        mock_response.raise_for_status = MagicMock()
        with patch("phraise.provider_manager.httpx.get", return_value=mock_response):
            result = fetch_providers_from_api(timeout=5)
        self.assertIsNone(result)


class TestMergeProviders(unittest.TestCase):
    """Merge fetched and local providers."""

    def test_fetched_overrides_local(self):
        local = [{"id": "deepseek", "label": "Old DeepSeek", "api_base": "https://old.example.com"}]
        fetched = [{"id": "deepseek", "label": "DeepSeek", "api_base": "https://api.deepseek.com/v1"}]
        merged = _merge_providers(fetched, local)
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]["label"], "DeepSeek")

    def test_local_fills_gaps(self):
        local = [{"id": "openai", "label": "OpenAI", "api_base": "https://api.openai.com/v1"}]
        fetched = [{"id": "deepseek", "label": "DeepSeek", "api_base": "https://api.deepseek.com/v1"}]
        merged = _merge_providers(fetched, local)
        ids = {p["id"] for p in merged}
        self.assertEqual(ids, {"openai", "deepseek"})


class TestCache(unittest.TestCase):
    """Disk cache read/write."""

    def setUp(self):
        self._original_cache_file = provider_manager.CACHE_FILE
        self._tmp_dir = tempfile.TemporaryDirectory()
        provider_manager.CACHE_FILE = Path(self._tmp_dir.name) / "providers_cache.json"
        reset_providers()

    def tearDown(self):
        provider_manager.CACHE_FILE = self._original_cache_file
        self._tmp_dir.cleanup()
        reset_providers()

    def test_cache_roundtrip(self):
        providers = [{"id": "x", "label": "X", "api_base": "https://x.com/v1"}]
        _save_cache(providers)
        loaded = _load_cache()
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded[0]["id"], "x")

    def test_cache_expired_returns_none(self):
        providers = [{"id": "x", "label": "X", "api_base": "https://x.com/v1"}]
        _save_cache(providers)
        old_time = time.time() - CACHE_TTL_SECONDS - 1
        payload = {"cached_at": old_time, "providers": providers}
        with open(provider_manager.CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(payload, f)
        loaded = _load_cache()
        self.assertIsNone(loaded)

    def test_cache_bad_providers_skipped(self):
        payload = {"cached_at": time.time(), "providers": [{"id": "bad", "api_base": "nope"}]}
        with open(provider_manager.CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(payload, f)
        loaded = _load_cache()
        self.assertIsNone(loaded)

    def test_get_providers_uses_cache(self):
        providers = [{"id": "cached", "label": "Cached", "api_base": "https://cached.com/v1"}]
        _save_cache(providers)
        reset_providers()
        _save_cache(providers)
        result = get_providers()
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["id"], "cached")


class TestInitProviders(unittest.TestCase):
    """Async background refresh."""

    def setUp(self):
        self._original_cache_file = provider_manager.CACHE_FILE
        self._tmp_dir = tempfile.TemporaryDirectory()
        provider_manager.CACHE_FILE = Path(self._tmp_dir.name) / "providers_cache.json"
        reset_providers()

    def tearDown(self):
        provider_manager.CACHE_FILE = self._original_cache_file
        self._tmp_dir.cleanup()
        reset_providers()

    def test_init_providers_merges_fetched(self):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "deepseek": {"id": "deepseek", "name": "DeepSeek", "api": "https://api.deepseek.com/v1"},
        }
        mock_response.raise_for_status = MagicMock()
        callback_called = threading.Event()

        def callback():
            callback_called.set()

        with patch("phraise.provider_manager.httpx.get", return_value=mock_response):
            init_providers(callback=callback)
            callback_called.wait(timeout=5)

        providers = get_providers()
        ids = {p["id"] for p in providers}
        self.assertIn("deepseek", ids)
        self.assertIn("openai", ids)

    def test_init_providers_falls_back_to_local(self):
        import httpx
        callback_called = threading.Event()

        def callback():
            callback_called.set()

        with patch("phraise.provider_manager.httpx.get", side_effect=httpx.HTTPError("fail")):
            init_providers(callback=callback)
            callback_called.wait(timeout=5)

        providers = get_providers()
        self.assertEqual(len(providers), len(LOCAL_PROVIDERS))


if __name__ == "__main__":
    unittest.main()
