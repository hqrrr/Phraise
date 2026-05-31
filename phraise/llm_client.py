import json
import re
import threading
from collections.abc import Callable

import httpx
from openai import OpenAI

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
        return True, 0, 0, ""
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
    escaped = {}
    for k, v in kwargs.items():
        if isinstance(v, str):
            escaped[k] = v.replace("{", "{{").replace("}", "}}")
        else:
            escaped[k] = v
    return template.format(**escaped)


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
        timeout=httpx.Timeout(30.0),
    )


def optimize_text(
    original_text: str,
    style: str = "concise",
    style_label: str = "Concise",
    model_type: str = "model_1",
    on_stream: Callable[[str], None] | None = None,
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
        USER_PROMPT_OPTIMIZE,
        style=style,
        style_label=style_label,
        original_text=original_text,
    )

    thread = threading.Thread(
        target=_call_api,
        args=(model_config, SYSTEM_PROMPT_OPTIMIZE, user_message, on_stream, on_done),
        daemon=True,
    )
    thread.start()


def translate_text(
    original_text: str,
    source_lang: str = "auto",
    target_lang: str = "zh-CN",
    model_type: str = "model_1",
    on_stream: Callable[[str], None] | None = None,
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
        args=(model_config, SYSTEM_PROMPT_TRANSLATE, user_message, on_stream, on_done),
        daemon=True,
    )
    thread.start()


def custom_instruction(
    original_text: str,
    instruction: str,
    model_type: str = "model_1",
    on_stream: Callable[[str], None] | None = None,
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
        USER_PROMPT_CUSTOM,
        original_text=original_text,
        custom_instruction=instruction,
    )

    thread = threading.Thread(
        target=_call_api,
        args=(model_config, SYSTEM_PROMPT_CUSTOM, user_message, on_stream, on_done),
        daemon=True,
    )
    thread.start()


def _call_api(
    model_config: dict,
    system_prompt: str,
    user_message: str,
    on_stream: Callable[[str], None] | None,
    on_done: Callable[[dict | None, str | None], None] | None,
):
    try:
        client = _create_client(model_config)
        response = client.chat.completions.create(
            model=model_config.get("model_name", ""),
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            temperature=model_config.get("temperature", 0.3),
            max_tokens=model_config.get("max_tokens", 1024),
        )

        content = response.choices[0].message.content or ""
        finish_reason = response.choices[0].finish_reason or ""
        parsed = _parse_json_response(content)

        if parsed is None:
            if on_done:
                on_done(None, content)
        else:
            if finish_reason == "length":
                parsed["_truncated"] = True
            if on_done:
                on_done(parsed, None)

    except Exception as e:
        error_msg = _handle_error(e)
        if on_done:
            on_done(None, error_msg)


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
    best = None
    best_len = 0
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
                obj_len = end - start + 1
                if obj_len > best_len:
                    best = obj
                    best_len = obj_len
            except json.JSONDecodeError:
                pass
    return best


def _handle_error(e: Exception) -> str:
    msg = str(e).lower()
    if "timeout" in msg or "timed out" in msg:
        return t("llm.error.timeout")
    if "401" in msg or "unauthorized" in msg or "invalid api key" in msg:
        return t("llm.error.bad_api_key")
    if "402" in msg or "insufficient" in msg or "quota" in msg or "billing" in msg:
        return t("llm.error.quota")
    if "connection" in msg or "connect" in msg or "network" in msg:
        return t("llm.error.network")
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
        response = client.chat.completions.create(
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
