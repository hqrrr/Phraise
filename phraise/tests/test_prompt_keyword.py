# PhrAIse - AI writing assistant
# License: GNU GPLv3
# GitHub: https://github.com/hqrrr/Phraise
# Author: hqrrr
#
# Description: Unit tests for prompt keyword.
"""Tests that prompt_keyword from style config is wired into optimize_text prompts.

Verifies:
  - prompt_keyword appears in the generated user_message
  - Fallback to style id when prompt_keyword is missing
"""

import threading as _real_threading
import unittest
from pathlib import Path
from unittest.mock import patch


class _SyncThread:
    """Mimics threading.Thread but runs target synchronously on start()."""

    def __init__(self, *args, **kwargs):
        self._target = kwargs.pop("target", None)
        self._args = kwargs.pop("args", ())
        self._kwargs = kwargs.pop("kwargs", {})
        # swallow remaining kwargs (daemon, name, etc.)

    def start(self):
        if self._target is not None:
            self._target(*self._args, **self._kwargs)

    def join(self, timeout=None):
        pass


class TestPromptKeyword(unittest.TestCase):
    """Test that prompt_keyword flows from style config into LLM prompts."""

    def setUp(self):
        from phraise.config import Config
        Config._instance = None
        self.patch_path = patch.object(Path, "exists", return_value=False)
        self.mock_path_exists = self.patch_path.start()
        self.config = Config()

    def tearDown(self):
        self.patch_path.stop()
        from phraise.config import Config
        Config._instance = None

    @patch("phraise.llm_client._call_api")
    @patch("phraise.llm_client.threading.Thread", new=_SyncThread)
    def test_prompt_keyword_included_in_user_message(self, mock_call_api):
        """prompt_keyword='concise and brief' appears in the formatted user_message."""
        self.config.set("styles", value=[
            {"id": "concise", "label": "Concise", "prompt_keyword": "concise and brief"},
        ])
        self.config.set("models", "model_1", value={
            "provider": "test", "api_key": "sk-test", "api_base": "https://test.com",
            "model_name": "test-model", "temperature": 0.3, "max_tokens": 1024,
            "extra_params": "", "mode": "remote",
        })

        from phraise.llm_client import optimize_text
        optimize_text("Hello world", style="concise", style_label="Concise")

        mock_call_api.assert_called_once()
        _args = mock_call_api.call_args
        # args = (model_config, system_prompt, user_message, on_done)
        user_message = _args[0][2]
        self.assertIn("concise and brief", user_message)

    @patch("phraise.llm_client._call_api")
    @patch("phraise.llm_client.threading.Thread", new=_SyncThread)
    def test_prompt_keyword_fallback_to_style_id(self, mock_call_api):
        """When prompt_keyword is absent, the style id itself is used."""
        self.config.set("styles", value=[
            {"id": "concise", "label": "Concise"},  # no prompt_keyword field
        ])
        self.config.set("models", "model_1", value={
            "provider": "test", "api_key": "sk-test", "api_base": "https://test.com",
            "model_name": "test-model", "temperature": 0.3, "max_tokens": 1024,
            "extra_params": "", "mode": "remote",
        })

        from phraise.llm_client import optimize_text
        optimize_text("Hello world", style="concise", style_label="Concise")

        mock_call_api.assert_called_once()
        _args = mock_call_api.call_args
        user_message = _args[0][2]
        self.assertIn("concise", user_message)

    @patch("phraise.llm_client._call_api")
    @patch("phraise.llm_client.threading.Thread", new=_SyncThread)
    def test_prompt_keyword_no_styles_config(self, mock_call_api):
        """When styles list is empty, falls back to style id."""
        self.config.set("styles", value=[])
        self.config.set("models", "model_1", value={
            "provider": "test", "api_key": "sk-test", "api_base": "https://test.com",
            "model_name": "test-model", "temperature": 0.3, "max_tokens": 1024,
            "extra_params": "", "mode": "remote",
        })

        from phraise.llm_client import optimize_text
        optimize_text("Hello world", style="formal", style_label="Formal")

        mock_call_api.assert_called_once()
        _args = mock_call_api.call_args
        user_message = _args[0][2]
        self.assertIn("formal", user_message)


if __name__ == "__main__":
    unittest.main()
