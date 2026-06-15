"""Unit tests for LLM client error handling: check_output_fit, _handle_error, _call_api."""
import time
import unittest
from unittest.mock import MagicMock, patch, call

from openai import (
    APIError,
    APIConnectionError,
    APITimeoutError,
    AuthenticationError,
    BadRequestError,
    RateLimitError,
)

from phraise.llm_client import (
    _call_api,
    _handle_error,
    _get_retry_after,
    check_output_fit,
)


def _fake_done(result, error):
    pass


def _make_model_config(**overrides):
    cfg = {
        "api_key": "sk-test",
        "api_base": "https://api.example.com/v1",
        "model_name": "test-model",
        "temperature": 0.3,
        "max_tokens": 4096,
    }
    cfg.update(overrides)
    return cfg


def _mock_http_response(headers=None):
    resp = MagicMock()
    resp.headers = headers or {}
    return resp


# ── check_output_fit ────────────────────────────────────────────────────


class TestCheckOutputFit(unittest.TestCase):

    def test_unknown_model_type_returns_false(self):
        ok, est, max_tok, warning = check_output_fit(
            "hello world", model_type="nonexistent_model"
        )
        self.assertFalse(ok)
        self.assertEqual(est, 0)
        self.assertEqual(max_tok, 0)
        self.assertIn("nonexistent_model", warning)

    def test_known_model_returns_true_for_short_text(self):
        with patch("phraise.llm_client._get_model_config") as mock_cfg:
            mock_cfg.return_value = {"max_tokens": 4096}
            ok, est, max_tok, warning = check_output_fit(
                "short text", model_type="model_1", mode="optimize"
            )
            self.assertTrue(ok)
            self.assertGreater(est, 0)
            self.assertEqual(warning, "")

    def test_large_text_returns_false_with_warning(self):
        long_text = "hello " * 5000
        with patch("phraise.llm_client._get_model_config") as mock_cfg:
            mock_cfg.return_value = {"max_tokens": 1024}
            ok, est, max_tok, warning = check_output_fit(
                long_text, model_type="model_1", mode="optimize"
            )
            self.assertFalse(ok)
            self.assertIn("tokens", warning.lower() or "")


# ── _handle_error ───────────────────────────────────────────────────────


class TestHandleError(unittest.TestCase):

    def setUp(self):
        self._lang_patch = patch("phraise.i18n.get_language", return_value="en")
        self._lang_patch.start()

    def tearDown(self):
        self._lang_patch.stop()

    def test_timeout_error_maps_correctly(self):
        exc = APITimeoutError(request=None)
        msg = _handle_error(exc)
        self.assertNotIn("request error", msg.lower())

    def test_authentication_error_maps_correctly(self):
        exc = AuthenticationError(
            message="invalid api key",
            response=_mock_http_response(),
            body={},
        )
        msg = _handle_error(exc)
        self.assertNotIn("request error", msg.lower())

    def test_rate_limit_error_maps_correctly(self):
        exc = RateLimitError(
            message="rate limit exceeded",
            response=_mock_http_response(),
            body={},
        )
        msg = _handle_error(exc)
        self.assertNotIn("request error", msg.lower())

    def test_connection_error_maps_correctly(self):
        exc = APIConnectionError(request=None)
        msg = _handle_error(exc)
        self.assertNotIn("request error", msg.lower())

    def test_bad_request_error_maps_to_generic(self):
        exc = BadRequestError(
            message="bad request body", response=_mock_http_response(), body={}
        )
        msg = _handle_error(exc)
        self.assertIn("Request error", msg)
        self.assertIn("bad request body", msg)

    def test_unknown_exception_falls_back_to_generic(self):
        exc = ValueError("something unexpected")
        msg = _handle_error(exc)
        self.assertIn("Request error", msg)


# ── _call_api retry ─────────────────────────────────────────────────────


class TestCallApiRetry(unittest.TestCase):

    def setUp(self):
        self.patches = [
            patch("phraise.llm_client._create_client"),
            patch("phraise.llm_client._parse_json_response", return_value={"key": "val"}),
            patch("phraise.llm_client.t", side_effect=lambda k, **kw: k),
        ]
        self.mock_client_factory = self.patches[0].start()
        self.mock_parse = self.patches[1].start()
        self.mock_t = self.patches[2].start()

        self.mock_client = MagicMock()
        self.mock_client_factory.return_value = self.mock_client

        self.model_config = _make_model_config()

    def tearDown(self):
        for p in self.patches:
            p.stop()

    def test_success_first_attempt_no_retry(self):
        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(
                message=MagicMock(content='{"key": "val"}'),
                finish_reason="stop",
            )
        ]
        self.mock_client.chat.completions.create.return_value = mock_response

        results = []
        _call_api(
            self.model_config,
            "sys",
            "user",
            on_done=lambda r, e: results.append((r, e)),
        )
        time.sleep(0.05)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0][1], None)
        self.assertEqual(self.mock_client.chat.completions.create.call_count, 1)

    def test_rate_limit_retry_succeeds(self):
        rl_exc = RateLimitError(
            message="rate limit",
            response=_mock_http_response(),
            body={},
        )

        mock_success = MagicMock()
        mock_success.choices = [
            MagicMock(
                message=MagicMock(content='{"key": "val"}'),
                finish_reason="stop",
            )
        ]

        self.mock_client.chat.completions.create.side_effect = [
            rl_exc,
            mock_success,
        ]

        results = []
        with patch("phraise.llm_client.time.sleep", return_value=None) as mock_sleep:
            _call_api(
                self.model_config,
                "sys",
                "user",
                on_done=lambda r, e: results.append((r, e)),
            )
        time.sleep(0.05)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0][1], None)
        self.assertEqual(self.mock_client.chat.completions.create.call_count, 2)
        mock_sleep.assert_called_once_with(1.0)

    def test_rate_limit_exhausted_all_retries(self):
        rl_exc = RateLimitError(
            message="rate limit",
            response=_mock_http_response(),
            body={},
        )
        self.mock_client.chat.completions.create.side_effect = rl_exc

        results = []
        with patch("phraise.llm_client.time.sleep", return_value=None) as mock_sleep:
            _call_api(
                self.model_config,
                "sys",
                "user",
                on_done=lambda r, e: results.append((r, e)),
            )
        time.sleep(0.05)
        self.assertEqual(len(results), 1)
        self.assertIsNone(results[0][0])
        self.assertIsNotNone(results[0][1])
        self.assertEqual(self.mock_client.chat.completions.create.call_count, 3)
        self.assertEqual(mock_sleep.call_count, 2)
        mock_sleep.assert_has_calls([call(1.0), call(2.0)])

    def test_retry_after_header_respected(self):
        rl_exc = RateLimitError(
            message="rate limit",
            response=_mock_http_response({"Retry-After": "5.5"}),
            body={},
        )

        mock_success = MagicMock()
        mock_success.choices = [
            MagicMock(
                message=MagicMock(content='{"key": "val"}'),
                finish_reason="stop",
            )
        ]

        self.mock_client.chat.completions.create.side_effect = [
            rl_exc,
            mock_success,
        ]

        results = []
        with patch("phraise.llm_client.time.sleep", return_value=None) as mock_sleep:
            _call_api(
                self.model_config,
                "sys",
                "user",
                on_done=lambda r, e: results.append((r, e)),
            )
        time.sleep(0.05)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0][1], None)
        mock_sleep.assert_called_once_with(5.5)

    def test_non_rate_limit_error_does_not_retry(self):
        exc = APITimeoutError(request=None)
        self.mock_client.chat.completions.create.side_effect = exc

        results = []
        with patch("phraise.llm_client.time.sleep", return_value=None) as mock_sleep:
            _call_api(
                self.model_config,
                "sys",
                "user",
                on_done=lambda r, e: results.append((r, e)),
            )
        time.sleep(0.05)
        self.assertEqual(len(results), 1)
        self.assertIsNone(results[0][0])
        self.assertIsNotNone(results[0][1])
        self.assertEqual(self.mock_client.chat.completions.create.call_count, 1)
        mock_sleep.assert_not_called()

    def test_content_filter_handled(self):
        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(
                message=MagicMock(content="blocked"),
                finish_reason="content_filter",
            )
        ]
        self.mock_client.chat.completions.create.return_value = mock_response

        results = []
        _call_api(
            self.model_config,
            "sys",
            "user",
            on_done=lambda r, e: results.append((r, e)),
        )
        time.sleep(0.05)
        self.assertEqual(len(results), 1)
        self.assertIsNone(results[0][0])
        self.assertIn("content_filter", results[0][1])


# ── _get_retry_after ────────────────────────────────────────────────────


class TestGetRetryAfter(unittest.TestCase):

    def test_retry_after_header_parsed(self):
        exc = RateLimitError(
            message="rl",
            response=_mock_http_response({"Retry-After": "10"}),
            body={},
        )
        self.assertEqual(_get_retry_after(exc), 10.0)

    def test_lowercase_header_parsed(self):
        exc = RateLimitError(
            message="rl",
            response=_mock_http_response({"retry-after": "3.5"}),
            body={},
        )
        self.assertEqual(_get_retry_after(exc), 3.5)

    def test_no_header_returns_none(self):
        exc = RateLimitError(
            message="rl",
            response=_mock_http_response({}),
            body={},
        )
        self.assertIsNone(_get_retry_after(exc))

    def test_no_response_returns_none(self):
        exc = MagicMock(spec=RateLimitError)
        del exc.response
        self.assertIsNone(_get_retry_after(exc))
