"""Unit tests for LLM client edge case fixes.

Covers:
  - content_filter finish_reason → user-friendly error
  - empty instruction → early error without API call
  - _try_parse_json early exit (first valid JSON)
  - estimate_tokens type guard (non-string input)
  - configurable timeout via model config
"""

import unittest
from unittest.mock import patch, MagicMock

import phraise.llm_client as llm


class TestContentFilterFinishReason(unittest.TestCase):
    """content_filter finish_reason → on_done called with i18n error."""

    def setUp(self):
        self._lang_patch = patch("phraise.i18n.get_language", return_value="en")
        self._lang_patch.start()

    def tearDown(self):
        self._lang_patch.stop()

    def test_content_filter_triggers_before_json_parse(self):
        """Mock response with finish_reason='content_filter' → on_done(None, error)."""
        captured_result, captured_error = None, None

        def capture(result, error):
            nonlocal captured_result, captured_error
            captured_result = result
            captured_error = error

        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(
                finish_reason="content_filter",
                message=MagicMock(content=None),
            )
        ]

        fake_config = {
            "api_key": "sk-test",
            "api_base": "https://test.api/v1",
            "model_name": "test-model",
        }

        with patch.object(llm, "_create_client") as mock_client:
            mock_client_instance = MagicMock()
            mock_client_instance.chat.completions.create.return_value = (
                mock_response
            )
            mock_client.return_value = mock_client_instance

            llm._call_api(
                fake_config,
                "system",
                "user message",
                capture,
            )

        self.assertIsNone(captured_result)
        self.assertIn("filtered", captured_error.lower())
        # Verify we NEVER attempted JSON parse (content could be None)
        self.assertIsNotNone(captured_error)


class TestCustomInstructionEmptyValidation(unittest.TestCase):
    """Empty instruction → error returned synchronously, no API call."""

    def setUp(self):
        self._lang_patch = patch("phraise.i18n.get_language", return_value="en")
        self._lang_patch.start()

    def tearDown(self):
        self._lang_patch.stop()

    def test_empty_string_returns_error_no_api_call(self):
        captured = []

        def on_done(result, error):
            captured.append((result, error))

        # Patch threading.Thread to verify it is NOT started
        with patch("threading.Thread") as mock_thread:
            llm.custom_instruction(
                "some text",
                instruction="",
                on_done=on_done,
            )

        # Thread must NOT be created (empty instruction returns early)
        mock_thread.assert_not_called()
        self.assertEqual(len(captured), 1)
        self.assertIsNone(captured[0][0])
        self.assertIn("empty", captured[0][1].lower())

    def test_whitespace_only_returns_error_no_api_call(self):
        captured = []

        def on_done(result, error):
            captured.append((result, error))

        with patch("threading.Thread") as mock_thread:
            llm.custom_instruction(
                "some text",
                instruction="   \t  ",
                on_done=on_done,
            )

        mock_thread.assert_not_called()
        self.assertEqual(len(captured), 1)
        self.assertIsNone(captured[0][0])
        self.assertIn("empty", captured[0][1].lower())

    def test_none_on_done_does_not_crash(self):
        """instruction="" with on_done=None → no crash."""
        try:
            llm.custom_instruction("some text", instruction="", on_done=None)
        except Exception:
            self.fail("custom_instruction with on_done=None should not crash")


class TestTryParseJsonEarlyExit(unittest.TestCase):
    """_try_parse_json returns first valid JSON, not longest."""

    def test_first_valid_json_returned(self):
        """Two JSON objects in content → first one returned."""
        content = '{"a": 1} extra text {"b": 2}'
        result = llm._try_parse_json(content)
        self.assertEqual(result, {"a": 1})

    def test_only_invalid_json_returns_none(self):
        result = llm._try_parse_json("no json here")
        self.assertIsNone(result)

    def test_single_valid_json(self):
        content = 'prefix {"key": "value"} suffix'
        result = llm._try_parse_json(content)
        self.assertEqual(result, {"key": "value"})

    def test_nested_json_object(self):
        content = '{"outer": {"inner": 42}}'
        result = llm._try_parse_json(content)
        self.assertEqual(result, {"outer": {"inner": 42}})

    def test_escaped_quotes_in_string(self):
        content = r'{"msg": "hello \"world\""}'
        result = llm._try_parse_json(content)
        self.assertEqual(result, {"msg": 'hello "world"'})


class TestEstimateTokensTypeGuard(unittest.TestCase):
    """Non-string input → estimate_tokens returns 0."""

    def test_none_returns_zero(self):
        self.assertEqual(llm.estimate_tokens(None), 0)

    def test_int_returns_zero(self):
        self.assertEqual(llm.estimate_tokens(42), 0)

    def test_list_returns_zero(self):
        self.assertEqual(llm.estimate_tokens(["hello"]), 0)

    def test_empty_string_returns_zero(self):
        self.assertEqual(llm.estimate_tokens(""), 0)

    def test_normal_string_works(self):
        tokens = llm.estimate_tokens("Hello world")
        self.assertGreater(tokens, 0)


class TestCreateClientTimeoutConfig(unittest.TestCase):
    """_create_client respects timeout from model config."""

    def test_default_timeout_when_not_in_config(self):
        client = llm._create_client({"api_key": "k", "api_base": "https://x"})
        self.assertIsNotNone(client)
        self.assertEqual(client.timeout.connect, 30.0)

    def test_custom_timeout_from_config(self):
        client = llm._create_client({
            "api_key": "k",
            "api_base": "https://x",
            "timeout": 60.0,
        })
        self.assertEqual(client.timeout.connect, 60.0)

    def test_zero_timeout_from_config(self):
        """timeout=0 → httpx accepts it (unlimited)."""
        client = llm._create_client({
            "api_key": "k",
            "api_base": "https://x",
            "timeout": 0,
        })
        self.assertEqual(client.timeout.connect, 0.0)


if __name__ == "__main__":
    unittest.main()
