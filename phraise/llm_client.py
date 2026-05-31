import json
import re
import threading
from collections.abc import Callable

import httpx
from openai import OpenAI

from .config import config
from .prompts import (
    SYSTEM_PROMPT_OPTIMIZE,
    SYSTEM_PROMPT_TRANSLATE,
    SYSTEM_PROMPT_CUSTOM,
    USER_PROMPT_OPTIMIZE,
    USER_PROMPT_TRANSLATE,
    USER_PROMPT_CUSTOM,
)


def _safe_format(template: str, **kwargs) -> str:
    escaped = {}
    for k, v in kwargs.items():
        if isinstance(v, str):
            escaped[k] = v.replace("{", "{{").replace("}", "}}")
        else:
            escaped[k] = v
    return template.format(**escaped)


def _get_model_config(model_type: str = "fast") -> dict | None:
    if model_type == "fast":
        return config.get("models", "fast")
    elif model_type == "quality":
        return config.get("models", "quality")
    elif model_type.startswith("custom:"):
        idx = int(model_type.split(":")[1])
        customs = config.get("models", "custom_models", default=[])
        if 0 <= idx < len(customs):
            return customs[idx]
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
    style_label: str = "简洁",
    model_type: str = "fast",
    on_stream: Callable[[str], None] | None = None,
    on_done: Callable[[dict | None, str | None], None] | None = None,
):
    model_config = _get_model_config(model_type)
    if not model_config:
        if on_done:
            on_done(None, "未找到模型配置，请在设置中检查。")
        return

    if not model_config.get("api_key"):
        if on_done:
            on_done(None, "API Key 未设置，请在设置中配置。")
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
    model_type: str = "fast",
    on_stream: Callable[[str], None] | None = None,
    on_done: Callable[[dict | None, str | None], None] | None = None,
):
    model_config = _get_model_config(model_type)
    if not model_config:
        if on_done:
            on_done(None, "未找到模型配置，请在设置中检查。")
        return

    if not model_config.get("api_key"):
        if on_done:
            on_done(None, "API Key 未设置，请在设置中配置。")
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
    model_type: str = "fast",
    on_stream: Callable[[str], None] | None = None,
    on_done: Callable[[dict | None, str | None], None] | None = None,
):
    model_config = _get_model_config(model_type)
    if not model_config:
        if on_done:
            on_done(None, "未找到模型配置，请在设置中检查。")
        return

    if not model_config.get("api_key"):
        if on_done:
            on_done(None, "API Key 未设置，请在设置中配置。")
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
        parsed = _parse_json_response(content)

        if parsed is None:
            if on_done:
                on_done(None, content)
        else:
            if on_done:
                on_done(parsed, None)

    except Exception as e:
        error_msg = _handle_error(e)
        if on_done:
            on_done(None, error_msg)


def _parse_json_response(content: str) -> dict | None:
    content = content.strip()

    m = re.search(r'```(?:json)?\s*([\s\S]*?)```', content)
    if m:
        content = m.group(1).strip()

    for match in re.finditer(r'\{', content):
        start = match.start()
        depth = 0
        for i in range(start, len(content)):
            if content[i] == '{':
                depth += 1
            elif content[i] == '}':
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(content[start:i + 1])
                    except json.JSONDecodeError:
                        break
                    break
    return None


def _handle_error(e: Exception) -> str:
    msg = str(e).lower()
    if "timeout" in msg or "timed out" in msg:
        return "请求超时，请检查网络或切换模型"
    if "401" in msg or "unauthorized" in msg or "invalid api key" in msg:
        return "API Key 错误，请在设置中检查"
    if "402" in msg or "insufficient" in msg or "quota" in msg or "billing" in msg:
        return "API 额度不足"
    if "connection" in msg or "connect" in msg or "network" in msg:
        return "网络连接失败，请检查网络设置"
    return f"请求出错：{str(e)[:200]}"


def test_connection(provider: str, api_base: str, api_key: str, model_name: str) -> tuple[bool, str]:
    if not api_key.strip():
        return False, "API Key 未设置"
    if not api_base.strip():
        return False, "API Base 未设置"
    if not model_name.strip():
        return False, "模型名称未设置"
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
        return True, "连接成功"
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
