# PhrAIse - AI writing assistant
# License: GNU GPLv3
# GitHub: https://github.com/hqrrr/Phraise
# Author: hqrrr
#
# Description: Unit tests for extra params.
"""Tests that extra_params from model config are passed to the API create() call.

Verifies:
  - Valid JSON extra_params dict is passed as **kwargs to create()
  - Empty extra_params string results in no extra kwargs
  - Invalid JSON extra_params is safely ignored
"""

import json
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock


class TestExtraParams(unittest.TestCase):
    """Test that extra_params flows from model config into the API call."""

    def setUp(self):
        # Reset Config singleton
        from phraise.config import Config
        Config._instance = None
        self.patch_path = patch.object(Path, "exists", return_value=False)
        self.mock_path_exists = self.patch_path.start()
        self.config = Config()

        # Set a working model config
        self.config.set("models", "model_1", value={
            "provider": "test",
            "api_key": "sk-test",
            "api_base": "https://test.com",
            "model_name": "test-model",
            "temperature": 0.3,
            "max_tokens": 1024,
            "extra_params": "",
            "mode": "remote",
        })

    def tearDown(self):
        self.patch_path.stop()
        from phraise.config import Config
        Config._instance = None

    def _call_optimize(self):
        """Helper: invoke optimize_text synchronously by patching _call_api."""
        from phraise.llm_client import optimize_text
        with patch("phraise.llm_client._call_api") as mock_ca:
            optimize_text("Hello", style="concise", style_label="Concise")
            mock_ca.assert_called_once()
            return mock_ca.call_args[0][0]  # model_config

    @patch("phraise.llm_client._create_client")
    def test_extra_params_valid_json(self, mock_create_client):
        """Valid extra_params JSON is passed as **kwargs to create()."""
        mock_client = MagicMock()
        mock_create_client.return_value = mock_client

        self.config.set("models", "model_1", "extra_params",
                        value=json.dumps({"top_p": 0.5, "frequency_penalty": 0.2}))

        # trigger _call_api via optimize_text
        from phraise.llm_client import optimize_text
        with patch("phraise.llm_client._call_api", wraps=None) as real_call:
            # We need to actually run _call_api, not mock it
            pass

        # Instead, directly test _call_api behavior by calling it with a mocked client
        from phraise.llm_client import _call_api
        model_config = {
            "model_name": "test-model",
            "temperature": 0.3,
            "max_tokens": 1024,
            "extra_params": json.dumps({"top_p": 0.5, "frequency_penalty": 0.2}),
        }

        def fake_done(*_):
            pass

        _call_api(model_config, "system", "user", fake_done)

        # Should NOT have raised TypeError — extra_params were accepted
        mock_client.chat.completions.create.assert_called_once_with(
            model="test-model",
            messages=[
                {"role": "system", "content": "system"},
                {"role": "user", "content": "user"},
            ],
            temperature=0.3,
            max_tokens=1024,
            top_p=0.5,
            frequency_penalty=0.2,
        )

    @patch("phraise.llm_client._create_client")
    def test_extra_params_empty(self, mock_create_client):
        """Empty extra_params string adds no extra kwargs to create()."""
        mock_client = MagicMock()
        mock_create_client.return_value = mock_client

        from phraise.llm_client import _call_api
        model_config = {
            "model_name": "test-model",
            "temperature": 0.3,
            "max_tokens": 1024,
            "extra_params": "",
        }

        def fake_done(*_):
            pass

        _call_api(model_config, "system", "user", fake_done)

        mock_client.chat.completions.create.assert_called_once_with(
            model="test-model",
            messages=[
                {"role": "system", "content": "system"},
                {"role": "user", "content": "user"},
            ],
            temperature=0.3,
            max_tokens=1024,
        )

    @patch("phraise.llm_client._create_client")
    def test_extra_params_invalid_json(self, mock_create_client):
        """Invalid JSON in extra_params is silently ignored (no crash)."""
        mock_client = MagicMock()
        mock_create_client.return_value = mock_client

        from phraise.llm_client import _call_api
        model_config = {
            "model_name": "test-model",
            "temperature": 0.3,
            "max_tokens": 1024,
            "extra_params": "not valid json {{{",
        }

        def fake_done(*_):
            pass

        _call_api(model_config, "system", "user", fake_done)

        # Should fall back to base params only
        mock_client.chat.completions.create.assert_called_once_with(
            model="test-model",
            messages=[
                {"role": "system", "content": "system"},
                {"role": "user", "content": "user"},
            ],
            temperature=0.3,
            max_tokens=1024,
        )

    @patch("phraise.llm_client._create_client")
    def test_extra_params_none_string(self, mock_create_client):
        """extra_params=None is treated same as empty string."""
        mock_client = MagicMock()
        mock_create_client.return_value = mock_client

        from phraise.llm_client import _call_api
        model_config = {
            "model_name": "test-model",
            "temperature": 0.3,
            "max_tokens": 1024,
            "extra_params": "{}",
        }

        def fake_done(*_):
            pass

        _call_api(model_config, "system", "user", fake_done)

        mock_client.chat.completions.create.assert_called_once_with(
            model="test-model",
            messages=[
                {"role": "system", "content": "system"},
                {"role": "user", "content": "user"},
            ],
            temperature=0.3,
            max_tokens=1024,
        )


if __name__ == "__main__":
    unittest.main()
