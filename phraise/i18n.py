"""Centralized i18n (internationalization) module for PhrAIse.

All user-facing strings are defined here in English and Simplified Chinese.
Use ``t(key, **kwargs)`` to retrieve a translated string.
"""

from .config import config

# ── Supported languages ────────────────────────────────────────────────────

SUPPORTED_LANGUAGES: dict[str, str] = {
    "en": "English",
    "zh-CN": "简体中文",
}

DEFAULT_LANGUAGE = "en"

# ── Translation source/target language metadata ─────────────────────────────
#
# Each entry is (display_name, language_code).
# Display names are shown in dropdowns; codes are sent to the LLM.

SOURCE_LANGUAGES: list[tuple[str, str]] = [
    ("Auto-detect", "auto"),
    ("Chinese (Simplified)", "zh-CN"),
    ("English (US)", "en-US"),
    ("English (UK)", "en-GB"),
    ("Japanese", "ja"),
    ("Korean", "ko"),
    ("French", "fr"),
    ("German", "de"),
    ("Spanish", "es"),
    ("Russian", "ru"),
    ("Portuguese", "pt"),
]

TARGET_LANGUAGES: list[tuple[str, str]] = [
    ("Chinese (Simplified)", "zh-CN"),
    ("English (US)", "en-US"),
    ("English (UK)", "en-GB"),
    ("Japanese", "ja"),
    ("Korean", "ko"),
    ("French", "fr"),
    ("German", "de"),
    ("Spanish", "es"),
    ("Russian", "ru"),
    ("Portuguese", "pt"),
]


def display_to_code(display_name: str) -> str:
    """Convert a display name back to its language code."""
    for dname, code in SOURCE_LANGUAGES + TARGET_LANGUAGES:
        if dname == display_name:
            return code
    return display_name  # fallback


def code_to_display(code: str) -> str:
    """Convert a language code to its display name."""
    for dname, c in SOURCE_LANGUAGES + TARGET_LANGUAGES:
        if c == code:
            return dname
    return code  # fallback


# ── Translation dictionary ──────────────────────────────────────────────────

TRANSLATIONS: dict[str, dict[str, str]] = {
    # ── App / Tray / Menus ──────────────────────────────────────────────
    "app.tray.show_ball": {
        "en": "Show Floating Ball",
        "zh-CN": "显示悬浮球",
    },
    "app.tray.hide_ball": {
        "en": "Hide Floating Ball",
        "zh-CN": "隐藏悬浮球",
    },
    "app.tray.settings": {
        "en": "Settings...",
        "zh-CN": "设置...",
    },
    "app.tray.quit": {
        "en": "Quit PhrAIse",
        "zh-CN": "退出 PhrAIse",
    },
    "app.tray.quit_short": {
        "en": "Quit",
        "zh-CN": "退出",
    },

    # ── Floating Window ─────────────────────────────────────────────────
    "fw.tab.optimize": {
        "en": "Optimize",
        "zh-CN": "优化",
    },
    "fw.tab.translate": {
        "en": "Translate",
        "zh-CN": "翻译",
    },
    "fw.label.style": {
        "en": "Style:",
        "zh-CN": "风格：",
    },
    "fw.label.grammar_expanded": {
        "en": "Grammar Check ▼",
        "zh-CN": "语法检查 ▼",
    },
    "fw.label.grammar_collapsed": {
        "en": "Grammar Check ▶",
        "zh-CN": "语法检查 ▶",
    },
    "fw.label.rewrites": {
        "en": "Rewrite Versions:",
        "zh-CN": "改写版本：",
    },
    "fw.label.corrected_text": {
        "en": "Corrected Text:",
        "zh-CN": "修正后文本：",
    },
    "fw.label.harper_style_disabled": {
        "en": "Style selection is for AI models only",
        "zh-CN": "风格选择仅适用于 AI 模型",
    },
    "fw.label.custom_instruction": {
        "en": "Custom Instruction:",
        "zh-CN": "自定义指令：",
    },
    "fw.label.source_lang": {
        "en": "Source:",
        "zh-CN": "源语言：",
    },
    "fw.label.target_lang": {
        "en": "Target:",
        "zh-CN": "目标语言：",
    },
    "fw.label.translation_result": {
        "en": "Translation:",
        "zh-CN": "翻译结果：",
    },
    "fw.btn.replace": {
        "en": "Replace",
        "zh-CN": "替换",
    },
    "fw.btn.copy": {
        "en": "Copy",
        "zh-CN": "复制",
    },
    "fw.btn.generate": {
        "en": "Generate",
        "zh-CN": "生成",
    },
    "fw.btn.replace_original": {
        "en": "Replace Original",
        "zh-CN": "替换原文",
    },
    "fw.loading": {
        "en": "Loading...",
        "zh-CN": "加载中...",
    },
    "fw.no_issues": {
        "en": "No issues found ✓",
        "zh-CN": "未发现问题 ✓",
    },
    "fw.no_more_versions": {
        "en": "No more versions",
        "zh-CN": "暂无更多版本",
    },
    "fw.no_result": {
        "en": "No result",
        "zh-CN": "无结果",
    },
    "fw.toast.replaced": {
        "en": "Replaced",
        "zh-CN": "已替换",
    },
    "fw.toast.replace_failed": {
        "en": "Replace failed, please paste manually",
        "zh-CN": "替换失败，请手动粘贴",
    },
    "fw.toast.copied": {
        "en": "Copied",
        "zh-CN": "已复制",
    },
    "fw.toast.no_model_configured": {
        "en": "No model configured. Please set up a model in Settings first.",
        "zh-CN": "未配置模型，请先在设置中配置模型。",
    },
    "fw.toast.truncated": {
        "en": "Response truncated, try switching models or shorten text",
        "zh-CN": "⚠ 响应被截断，建议切换模型或缩短文本",
    },

    # ── Settings Panel ──────────────────────────────────────────────────
    "settings.title": {
        "en": "Settings - PhrAIse",
        "zh-CN": "设置 - PhrAIse",
    },
    "settings.tab.models": {
        "en": "Models",
        "zh-CN": "模型",
    },
    "settings.tab.styles": {
        "en": "Styles",
        "zh-CN": "样式",
    },
    "settings.tab.triggers": {
        "en": "Triggers",
        "zh-CN": "触发",
    },
    "settings.tab.appearance": {
        "en": "Appearance",
        "zh-CN": "外观",
    },
    "settings.tab.language": {
        "en": "Language",
        "zh-CN": "语言",
    },
    "settings.btn.save": {
        "en": "Save and Close",
        "zh-CN": "保存并关闭",
    },
    "settings.section.model_assignment": {
        "en": "Model Assignment",
        "zh-CN": "功能模型分配",
    },
    "settings.label.optimize_model": {
        "en": "Optimize Model:",
        "zh-CN": "优化模型：",
    },
    "settings.label.translate_model": {
        "en": "Translate Model:",
        "zh-CN": "翻译模型：",
    },
    "settings.model.one": {
        "en": "Model 1",
        "zh-CN": "模型一",
    },
    "settings.model.two": {
        "en": "Model 2",
        "zh-CN": "模型二",
    },
    "settings.model.not_selected": {
        "en": "-- Not selected --",
        "zh-CN": "-- 未选择 --",
    },
    "settings.model.harper": {
        "en": "Local (Harper)",
        "zh-CN": "本地 (Harper)",
    },
    "settings.label.provider": {
        "en": "Provider:",
        "zh-CN": "Provider:",
    },
    "settings.label.api_base": {
        "en": "API Base:",
        "zh-CN": "API Base:",
    },
    "settings.label.api_key": {
        "en": "API Key:",
        "zh-CN": "API Key:",
    },
    "settings.label.model_name": {
        "en": "Model Name:",
        "zh-CN": "Model Name:",
    },
    "settings.label.temperature": {
        "en": "Temperature:",
        "zh-CN": "Temperature:",
    },
    "settings.label.max_tokens": {
        "en": "Max Tokens:",
        "zh-CN": "Max Tokens:",
    },
    "settings.label.extra_params": {
        "en": "Extra Params:",
        "zh-CN": "额外参数：",
    },
    "settings.placeholder.extra_params": {
        "en": 'JSON format, e.g.: {"reasoning_effort":"medium"}',
        "zh-CN": 'JSON格式, 如: {"reasoning_effort":"medium"}',
    },
    "settings.placeholder.model_name": {
        "en": "Click 'Fetch Models' to retrieve model list...",
        "zh-CN": "点击 '获取模型' 获取模型列表...",
    },
    "settings.btn.fetch_models": {
        "en": "Fetch Models",
        "zh-CN": "获取模型",
    },
    "settings.tooltip.precise": {
        "en": "Precise",
        "zh-CN": "精确",
    },
    "settings.tooltip.creative": {
        "en": "Creative",
        "zh-CN": "创意",
    },
    "settings.btn.test_connection": {
        "en": "Test Connection",
        "zh-CN": "测试连接",
    },
    "settings.section.custom_models": {
        "en": "Custom Models",
        "zh-CN": "自定义模型",
    },
    "settings.btn.add_model": {
        "en": "Add Model",
        "zh-CN": "添加模型",
    },
    "settings.btn.edit": {
        "en": "Edit",
        "zh-CN": "编辑",
    },
    "settings.btn.delete": {
        "en": "Delete",
        "zh-CN": "删除",
    },
    "settings.dialog.edit_model": {
        "en": "Edit Custom Model",
        "zh-CN": "编辑自定义模型",
    },
    "settings.dialog.add_model": {
        "en": "Add Custom Model",
        "zh-CN": "添加自定义模型",
    },
    "settings.provider_custom": {
        "en": "Custom (manual entry)",
        "zh-CN": "自定义 (手动输入)",
    },
    "settings.btn.cancel": {
        "en": "Cancel",
        "zh-CN": "取消",
    },
    "settings.btn.save_dialog": {
        "en": "Save",
        "zh-CN": "保存",
    },
    "settings.status.testing": {
        "en": "Testing...",
        "zh-CN": "正在测试...",
    },
    "settings.status.fetching": {
        "en": "Fetching model list...",
        "zh-CN": "正在获取模型列表...",
    },
    "settings.status.no_models": {
        "en": "No models found",
        "zh-CN": "未获取到模型",
    },
    "settings.status.models_fetched": {
        "en": "Fetched {count} model(s)",
        "zh-CN": "已获取 {count} 个模型",
    },
    "settings.provider_search": {
        "en": "Type to search providers...",
        "zh-CN": "输入搜索提供商...",
    },
    "settings.status.providers_loading": {
        "en": "Loading provider list...",
        "zh-CN": "正在加载提供商列表...",
    },
    "settings.status.providers_loaded": {
        "en": "Loaded {count} providers",
        "zh-CN": "已加载 {count} 个提供商",
    },
    "settings.status.providers_fetch_failed": {
        "en": "Using local provider list",
        "zh-CN": "使用本地提供商列表",
    },
    "settings.section.preset_styles": {
        "en": "Preset Styles",
        "zh-CN": "预设风格",
    },
    "settings.header.style_label": {
        "en": "Name",
        "zh-CN": "名称",
    },
    "settings.header.style_keyword": {
        "en": "Prompt Keyword",
        "zh-CN": "提示关键词",
    },
    "settings.btn.add_style": {
        "en": "+ Add Style",
        "zh-CN": "+ 添加风格",
    },
    "settings.section.hotkeys": {
        "en": "Hotkey Settings",
        "zh-CN": "快捷键设置",
    },
    "settings.label.trigger_hotkey": {
        "en": "Trigger Hotkey:",
        "zh-CN": "触发快捷键：",
    },
    "settings.placeholder.trigger_hotkey": {
        "en": "e.g.: ctrl+c+c or ctrl+shift+o",
        "zh-CN": "例如: ctrl+c+c 或 ctrl+shift+o",
    },
    "settings.label.toggle_ball": {
        "en": "Toggle Ball:",
        "zh-CN": "切换悬浮球：",
    },
    "settings.placeholder.hotkey": {
        "en": "e.g.: ctrl+shift+o",
        "zh-CN": "例如: ctrl+shift+o",
    },
    "settings.status.invalid_format": {
        "en": "Invalid format",
        "zh-CN": "⚠ 格式无效",
    },
    "settings.section.general": {
        "en": "General Settings",
        "zh-CN": "常规设置",
    },
    "settings.label.theme": {
        "en": "Theme:",
        "zh-CN": "主题：",
    },
    "settings.theme.dark": {
        "en": "Dark (Catppuccin Mocha)",
        "zh-CN": "暗色 (Catppuccin Mocha)",
    },
    "settings.checkbox.auto_start": {
        "en": "Start with Windows",
        "zh-CN": "开机自启",
    },
    "settings.checkbox.start_minimized": {
        "en": "Start minimized",
        "zh-CN": "启动时最小化",
    },
    "settings.checkbox.auto_close": {
        "en": "Auto-close after replace",
        "zh-CN": "替换后自动关闭悬浮窗",
    },
    "settings.restart_required": {
        "en": "\u26a0 Restart required for changes to take effect",
        "zh-CN": "\u26a0 需重启软件后生效",
    },
    "settings.section.ball": {
        "en": "Floating Ball Settings",
        "zh-CN": "悬浮球设置",
    },
    "settings.label.opacity": {
        "en": "Opacity (0.1-1.0):",
        "zh-CN": "透明度 (0.1-1.0):",
    },
    "settings.label.ball_size": {
        "en": "Size (px):",
        "zh-CN": "大小 (px):",
    },
    "settings.label.custom_css": {
        "en": "Custom CSS:",
        "zh-CN": "自定义 CSS:",
    },
    "settings.placeholder.css": {
        "en": "/* ── Custom CSS template — uncomment and modify ──────────────\n * Examples:\n * QPushButton { border-radius: 8px; }\n * QComboBox { border: 2px solid rgb(108,92,231); }\n * QTextEdit { background: rgb(17,17,27); }\n * ──────────────────────────────────────────────────────── */",
        "zh-CN": "/* ── 自定义 CSS 模板 — 取消注释即可修改 ──────────────\n * 示例：\n * QPushButton { border-radius: 8px; }\n * QComboBox { border: 2px solid rgb(108,92,231); }\n * QTextEdit { background: rgb(17,17,27); }\n * ──────────────────────────────────────────────────────── */",
    },
    "settings.btn.validate": {
        "en": "Validate",
        "zh-CN": "验证",
    },
    "settings.btn.preview": {
        "en": "Preview",
        "zh-CN": "预览",
    },
    "settings.preview.text": {
        "en": "Preview Text Example",
        "zh-CN": "预览文本示例",
    },
    "settings.preview.button": {
        "en": "Sample Button",
        "zh-CN": "示例按钮",
    },
    "settings.css.ok": {
        "en": "✓ CSS syntax OK",
        "zh-CN": "✓ CSS 语法正确",
    },
    "settings.css.bracket_mismatch": {
        "en": "✗ Bracket mismatch",
        "zh-CN": "✗ 括号不匹配",
    },
    "settings.dialog.format_error": {
        "en": "Format Error",
        "zh-CN": "格式错误",
    },
    "settings.error.invalid_json": {
        "en": "Model \"{model}\" extra params JSON is invalid. Please check and try again.",
        "zh-CN": "\"{model}\" 模型的额外参数 JSON 格式无效，请检查后重试。",
    },
    "settings.error.invalid_hotkey": {
        "en": "Hotkey format is invalid. Please check and try again.",
        "zh-CN": "快捷键格式无效，请检查后重试。",
    },
    "settings.error.invalid_number": {
        "en": "\"{field}\" is not a valid number. Please enter a numeric value.",
        "zh-CN": "\"{field}\" 不是有效的数字，请输入数值。",
    },
    "settings.label.language": {
        "en": "UI Language:",
        "zh-CN": "界面语言：",
    },
    "settings.section.harper": {
        "en": "Harper Settings",
        "zh-CN": "Harper 设置",
    },
    "settings.label.harper_dialect": {
        "en": "English Dialect:",
        "zh-CN": "英语方言：",
    },
    "harper.error.binary_not_found": {
        "en": "Harper not available, using remote model.",
        "zh-CN": "Harper 不可用，使用远程模型。",
    },
    "harper.error.process_crash": {
        "en": "Harper process error, using remote model.",
        "zh-CN": "Harper 进程错误，使用远程模型。",
    },
    "harper.error.timeout": {
        "en": "Harper check timed out, using remote model.",
        "zh-CN": "Harper 检查超时，使用远程模型。",
    },
    "harper.error.text_too_large": {
        "en": "Text too large for local grammar check (>120KB). Using remote model.",
        "zh-CN": "文本过大，超出本地语法检查限制(>120KB)。使用远程模型。",
    },
    "settings.label.language_desc": {
        "en": "Changes take effect immediately across all windows.",
        "zh-CN": "更改会立即在所有窗口中生效。",
    },

    # ── LLM Client ──────────────────────────────────────────────────────
    "llm.error.no_config": {
        "en": "Model configuration not found. Please check settings.",
        "zh-CN": "未找到模型配置，请在设置中检查。",
    },
    "llm.error.no_api_key": {
        "en": "API Key not set. Please configure in settings.",
        "zh-CN": "API Key 未设置，请在设置中配置。",
    },
    "llm.error.unknown_model_type": {
        "en": "Unknown model type '{model_type}'. Please check settings.",
        "zh-CN": "未知模型类型 '{model_type}'，请在设置中检查。",
    },
    "llm.error.timeout": {
        "en": "Request timed out. Please check network or switch model.",
        "zh-CN": "请求超时，请检查网络或切换模型",
    },
    "llm.error.bad_api_key": {
        "en": "API Key error. Please check in settings.",
        "zh-CN": "API Key 错误，请在设置中检查",
    },
    "llm.error.quota": {
        "en": "API quota exceeded.",
        "zh-CN": "API 额度不足",
    },
    "llm.error.network": {
        "en": "Network connection failed. Please check network settings.",
        "zh-CN": "网络连接失败，请检查网络设置",
    },
    "llm.error.request": {
        "en": "Request error: {detail}",
        "zh-CN": "请求出错：{detail}",
    },
    "llm.error.content_filter": {
        "en": "Response was filtered by the provider's content policy.",
        "zh-CN": "响应被提供商的内容策略过滤。",
    },
    "llm.error.empty_instruction": {
        "en": "Instruction cannot be empty.",
        "zh-CN": "指令不能为空。",
    },
    "llm.error.token_warning": {
        "en": (
            "Input text is long (~{input_tok} tokens). "
            "Estimated output ~{estimated_output} tokens exceeds limit of {max_tok}. "
            "Consider shortening text or adjusting settings."
        ),
        "zh-CN": (
            "输入文本较长（约{input_tok} tokens），"
            "预计输出约{estimated_output} tokens，超出设置{max_tok}。"
            "建议缩短文本或修改设置。"
        ),
    },
    "llm.validate.no_api_key": {
        "en": "API Key not set",
        "zh-CN": "API Key 未设置",
    },
    "llm.validate.no_api_base": {
        "en": "API Base not set",
        "zh-CN": "API Base 未设置",
    },
    "llm.validate.no_model": {
        "en": "Model name not set",
        "zh-CN": "模型名称未设置",
    },
    "llm.status.connected": {
        "en": "Connected",
        "zh-CN": "连接成功",
    },

    # ── Style Labels ────────────────────────────────────────────────────
    "style.concise": {
        "en": "Concise",
        "zh-CN": "简洁",
    },
    "style.formal": {
        "en": "Formal",
        "zh-CN": "正式",
    },
    "style.natural": {
        "en": "Natural",
        "zh-CN": "流畅",
    },

    # ── Provider Labels ─────────────────────────────────────────────────
    "provider.kimi": {
        "en": "Kimi (Moonshot)",
        "zh-CN": "Kimi (月之暗面)",
    },
    "provider.glm": {
        "en": "GLM (Zhipu)",
        "zh-CN": "GLM (智谱)",
    },
    "provider.qwen": {
        "en": "Qwen (Tongyi)",
        "zh-CN": "Qwen (通义千问)",
    },
    "provider.groq": {
        "en": "Groq",
        "zh-CN": "Groq",
    },
    "provider.together": {
        "en": "Together AI",
        "zh-CN": "Together AI",
    },
    "provider.fireworks": {
        "en": "Fireworks AI",
        "zh-CN": "Fireworks AI",
    },
    "provider.perplexity": {
        "en": "Perplexity",
        "zh-CN": "Perplexity",
    },
    "provider.xai": {
        "en": "xAI (Grok)",
        "zh-CN": "xAI (Grok)",
    },
    "provider.mistral": {
        "en": "Mistral AI",
        "zh-CN": "Mistral AI",
    },
    "provider.cohere": {
        "en": "Cohere",
        "zh-CN": "Cohere",
    },
    "provider.voyageai": {
        "en": "Voyage AI",
        "zh-CN": "Voyage AI",
    },
    "provider.hyperbolic": {
        "en": "Hyperbolic",
        "zh-CN": "Hyperbolic",
    },
}


# ── Listener system ────────────────────────────────────────────────────────

_listeners: list = []


def add_listener(callback):
    """Register a callback to be called when the language changes."""
    if callback not in _listeners:
        _listeners.append(callback)


def remove_listener(callback):
    """Unregister a listener."""
    if callback in _listeners:
        _listeners.remove(callback)


def _notify_listeners():
    """Notify all registered listeners of a language change."""
    for cb in _listeners:
        try:
            cb()
        except Exception:
            pass


def set_language(lang: str):
    """Set the active language and notify listeners."""
    config.set("general", "language", value=lang)
    _notify_listeners()


def get_language() -> str:
    """Return the current UI language code."""
    return config.get("general", "language", default=DEFAULT_LANGUAGE)


def t(key: str, lang: str | None = None, **kwargs) -> str:
    """Return the translated string for *key* in the specified language.

    Falls back to English, then to the key itself.
    """
    if lang is None:
        lang = get_language()

    translations = TRANSLATIONS.get(key)
    if translations is None:
        return key

    text = translations.get(lang) or translations.get(DEFAULT_LANGUAGE) or key

    if kwargs:
        try:
            text = text.format(**kwargs)
        except (KeyError, ValueError):
            pass

    return text
