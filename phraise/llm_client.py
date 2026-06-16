# PhrAIse - AI writing assistant
# License: GNU GPLv3
# GitHub: https://github.com/hqrrr/Phraise
# Author: hqrrr
#
# Description: OpenAI-compatible API client for LLM requests.
import json
import re
import threading
import time
from collections.abc import Callable

import httpx
from openai import (
    APIError,
    APIConnectionError,
    APITimeoutError,
    AuthenticationError,
    BadRequestError,
    OpenAI,
    RateLimitError,
)

from .config import config
from .i18n import t

from .prompts import (
    SYSTEM_PROMPT_OPTIMIZE,
    SYSTEM_PROMPT_TRANSLATE,
    SYSTEM_PROMPT_CUSTOM,
    USER_PROMPT_OPTIMIZE,
    USER_PROMPT_TRANSLATE,
    USER_PROMPT_CUSTOM,
)


# ── Token estimation ──────────────────────────────────────────────────────

_CJK_RANGES = [
    (0x4E00, 0x9FFF), (0x3400, 0x4DBF), (0xF900, 0xFAFF),
    (0x3040, 0x309F), (0x30A0, 0x30FF), (0xAC00, 0xD7AF),
]


def _is_cjk(ch: str) -> bool:
    cp = ord(ch)
    return any(lo <= cp <= hi for lo, hi in _CJK_RANGES)


def estimate_tokens(text: str) -> int:
    """Estimate token count using character-type heuristics.

    CJK characters ≈ 1.5 chars/token, others ≈ 4 chars/token.
    Accuracy: ±15% for mixed Chinese/English text.
    """
    if not isinstance(text, str):
        return 0
    if not text:
        return 0
    cjk = sum(1 for ch in text if _is_cjk(ch))
    non_cjk = len(text) - cjk
    return max(1, int(cjk / 1.5 + non_cjk / 4.0))


def check_output_fit(
    input_text: str,
    model_type: str = "model_1",
    mode: str = "optimize",
) -> tuple[bool, int, int, str]:
    """Check if the expected output fits within the model's max_tokens.

    Returns (ok, estimated_output, max_tokens, warning_message).
    If *ok* is False, *warning_message* is non-empty.
    """
    model_config = _get_model_config(model_type)
    if not model_config:
        return False, 0, 0, t("llm.error.unknown_model_type", model_type=model_type)
    max_tok = model_config.get("max_tokens", 4096)
    input_tok = estimate_tokens(input_text)

    if mode == "optimize":
        estimated_output = int(input_tok * 3.5) + 200
    elif mode == "translate":
        estimated_output = int(input_tok * 1.3) + 100
    else:
        estimated_output = int(input_tok * 1.5) + 100

    threshold = int(max_tok * 0.85)
    if estimated_output > threshold:
        return False, estimated_output, max_tok, t(
            "llm.error.token_warning",
            input_tok=input_tok,
            estimated_output=estimated_output,
            max_tok=max_tok,
        )
    return True, estimated_output, max_tok, ""


def _safe_format(template: str, **kwargs) -> str:
    """Format a template string with keyword arguments.

    Python's str.format() does NOT re-process braces in substituted
    values — only braces in the template itself are interpreted as
    format fields.  Therefore no escaping of kwargs is needed.
    """
    return template.format(**kwargs)


def _get_model_config(model_type: str = "model_1") -> dict | None:
    if model_type == "model_1":
        return config.get("models", "model_1")
    elif model_type == "model_2":
        return config.get("models", "model_2")
    return None


def _create_client(model_config: dict) -> OpenAI:
    return OpenAI(
        api_key=model_config.get("api_key", ""),
        base_url=model_config.get("api_base", ""),
        timeout=httpx.Timeout(model_config.get("timeout", 30.0)),
    )


def optimize_text(
    original_text: str,
    style: str = "concise",
    style_label: str = "Concise",
    model_type: str = "model_1",
    on_done: Callable[[dict | None, str | None], None] | None = None,
):
    model_config = _get_model_config(model_type)
    if not model_config:
        if on_done:
            on_done(None, t("llm.error.no_config"))
        return

    if not model_config.get("api_key"):
        if on_done:
            on_done(None, t("llm.error.no_api_key"))
        return

    prompt_keyword = style
    for sc in config.get("styles", default=[]):
        if sc.get("id") == style:
            prompt_keyword = sc.get("prompt_keyword", style)
            break

    user_message = _safe_format(
        USER_PROMPT_OPTIMIZE,
        style=style,
        style_label=style_label,
        prompt_keyword=prompt_keyword,
        original_text=original_text,
    )

    thread = threading.Thread(
        target=_call_api,
        args=(model_config, SYSTEM_PROMPT_OPTIMIZE, user_message, on_done),
        daemon=True,
    )
    thread.start()


def translate_text(
    original_text: str,
    source_lang: str = "auto",
    target_lang: str = "zh-CN",
    model_type: str = "model_1",
    on_done: Callable[[dict | None, str | None], None] | None = None,
):
    model_config = _get_model_config(model_type)
    if not model_config:
        if on_done:
            on_done(None, t("llm.error.no_config"))
        return

    if not model_config.get("api_key"):
        if on_done:
            on_done(None, t("llm.error.no_api_key"))
        return

    user_message = _safe_format(
        USER_PROMPT_TRANSLATE,
        source_language=source_lang,
        target_language=target_lang,
        original_text=original_text,
    )

    thread = threading.Thread(
        target=_call_api,
        args=(model_config, SYSTEM_PROMPT_TRANSLATE, user_message, on_done),
        daemon=True,
    )
    thread.start()


def custom_instruction(
    original_text: str,
    instruction: str,
    model_type: str = "model_1",
    on_done: Callable[[dict | None, str | None], None] | None = None,
):
    if not instruction or not instruction.strip():
        if on_done:
            on_done(None, t("llm.error.empty_instruction"))
        return

    model_config = _get_model_config(model_type)
    if not model_config:
        if on_done:
            on_done(None, t("llm.error.no_config"))
        return

    if not model_config.get("api_key"):
        if on_done:
            on_done(None, t("llm.error.no_api_key"))
        return

    user_message = _safe_format(
        USER_PROMPT_CUSTOM,
        original_text=original_text,
        custom_instruction=instruction,
    )

    thread = threading.Thread(
        target=_call_api,
        args=(model_config, SYSTEM_PROMPT_CUSTOM, user_message, on_done),
        daemon=True,
    )
    thread.start()


def _call_api(
    model_config: dict,
    system_prompt: str,
    user_message: str,
    on_done: Callable[[dict | None, str | None], None] | None,
):
    client = _create_client(model_config)
    max_retries = 3
    delays = [1.0, 2.0, 4.0]

    extra_params_raw = model_config.get("extra_params", "{}")
    extra_params: dict = {}
    if extra_params_raw:
        try:
            extra_params = json.loads(extra_params_raw)
        except json.JSONDecodeError:
            pass

    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                model=model_config.get("model_name", ""),
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
                temperature=model_config.get("temperature", 0.3),
                max_tokens=model_config.get("max_tokens", 1024),
                **extra_params,
            )

            finish_reason = response.choices[0].finish_reason or ""

            if finish_reason == "content_filter":
                if on_done:
                    on_done(None, t("llm.error.content_filter"))
                return

            content = response.choices[0].message.content or ""
            parsed = _parse_json_response(content)

            if parsed is None:
                if on_done:
                    on_done(None, content)
            else:
                if finish_reason == "length":
                    parsed["_truncated"] = True
                if on_done:
                    on_done(parsed, None)
            return

        except RateLimitError as e:
            if attempt < max_retries - 1:
                retry_after = _get_retry_after(e)
                delay = retry_after if retry_after is not None else delays[attempt]
                time.sleep(delay)
                continue
            error_msg = _handle_error(e)
            if on_done:
                on_done(None, error_msg)
            return

        except Exception as e:
            error_msg = _handle_error(e)
            if on_done:
                on_done(None, error_msg)
            return


def _get_retry_after(exc: RateLimitError) -> float | None:
    try:
        response = getattr(exc, "response", None)
        if response is None:
            return None
        headers = getattr(response, "headers", {})
        val = headers.get("Retry-After") or headers.get("retry-after")
        if val is None:
            return None
        return float(val)
    except (TypeError, ValueError, AttributeError):
        return None


def _parse_json_response(content: str) -> dict | None:
    content = content.strip()

    result = _try_parse_json(content)
    if result is not None:
        return result

    m = re.search(r'```\s*(?:json)?\s*\n?([\s\S]*)```', content)
    if m:
        result = _try_parse_json(m.group(1).strip())
        if result is not None:
            return result

    return None


def _try_parse_json(content: str) -> dict | None:
    for match in re.finditer(r'\{', content):
        start = match.start()
        depth = 0
        in_string = False
        escape_next = False
        end = -1
        for i in range(start, len(content)):
            ch = content[i]
            if escape_next:
                escape_next = False
                continue
            if ch == '\\' and in_string:
                escape_next = True
                continue
            if ch == '"':
                in_string = not in_string
            elif not in_string:
                if ch == '{':
                    depth += 1
                elif ch == '}':
                    depth -= 1
                    if depth == 0:
                        end = i
                        break
        if end >= 0:
            try:
                obj = json.loads(content[start:end + 1])
                return obj
            except json.JSONDecodeError:
                pass
    return None


def _handle_error(e: Exception) -> str:
    """Map OpenAI SDK exception types to user-facing error messages."""
    if isinstance(e, APITimeoutError):
        return t("llm.error.timeout")
    if isinstance(e, AuthenticationError):
        return t("llm.error.bad_api_key")
    if isinstance(e, RateLimitError):
        return t("llm.error.quota")
    if isinstance(e, APIConnectionError):
        return t("llm.error.network")
    if isinstance(e, BadRequestError):
        return t("llm.error.request", detail=str(e)[:200])
    if isinstance(e, APIError):
        return t("llm.error.request", detail=str(e)[:200])
    return t("llm.error.request", detail=str(e)[:200])


def test_connection(provider: str, api_base: str, api_key: str, model_name: str) -> tuple[bool, str]:
    if not api_key.strip():
        return False, t("llm.validate.no_api_key")
    if not api_base.strip():
        return False, t("llm.validate.no_api_base")
    if not model_name.strip():
        return False, t("llm.validate.no_model")
    try:
        client = OpenAI(
            api_key=api_key.strip(),
            base_url=api_base.strip(),
            timeout=httpx.Timeout(10.0),
        )
        client.chat.completions.create(
            model=model_name.strip(),
            messages=[{"role": "user", "content": "hi"}],
            max_tokens=10,
        )
        return True, t("llm.status.connected")
    except Exception as e:
        return False, _handle_error(e)


def list_models(api_base: str, api_key: str) -> tuple[list[str] | None, str | None]:
    try:
        client = OpenAI(
            api_key=api_key.strip(),
            base_url=api_base.strip(),
            timeout=httpx.Timeout(10.0),
        )
        models = client.models.list()
        names = sorted([m.id for m in models])
        return names, None
    except Exception as e:
        return None, _handle_error(e)
