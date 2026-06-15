"""Translation integrity tests for the i18n module.

These tests verify that every translation key is complete, that non-brand
strings are actually translated, and that the ``t()`` fallback/formatting chain
behaves correctly. They are intended to fail until the missing translations and
untranslated labels in ``phraise/i18n.py`` are fixed.
"""

import pytest

from phraise.config import DEFAULT_CONFIG
from phraise.i18n import SUPPORTED_LANGUAGES, TRANSLATIONS, t
from phraise.provider_manager import LOCAL_PROVIDERS


# Brand/provider ids where an identical English and Chinese label is acceptable.
_IDENTICAL_LABEL_WHITELIST = frozenset(
    [
        "openai",
        "claude",
        "gemini",
        "deepseek",
        "openrouter",
        "siliconflow",
        "groq",
        "together",
        "fireworks",
        "perplexity",
        "xai",
        "mistral",
        "cohere",
        "voyageai",
        "hyperbolic",
    ]
)


def test_every_translation_key_has_required_languages():
    """Every key in TRANSLATIONS must define both 'en' and 'zh-CN'."""
    missing = []
    for key, translations in TRANSLATIONS.items():
        for lang in SUPPORTED_LANGUAGES:
            if lang not in translations:
                missing.append((key, lang))
    assert not missing, f"Missing language entries: {missing}"


def test_non_brand_translations_are_not_identical():
    """Non-brand strings must differ between English and Chinese.

    Provider names in ``_IDENTICAL_LABEL_WHITELIST`` are allowed to be the same
    because they are brand names.
    """
    whitelist_keys = {f"provider.{pid}" for pid in _IDENTICAL_LABEL_WHITELIST}
    identical = []
    for key, translations in TRANSLATIONS.items():
        if key in whitelist_keys:
            continue
        en = translations.get("en")
        zh = translations.get("zh-CN")
        if en is not None and zh is not None and en == zh:
            identical.append(key)
    assert not identical, f"Untranslated (identical en/zh-CN) keys: {identical}"


def test_missing_key_returns_key():
    """``t()`` must fall back to the key itself when no translation exists."""
    assert t("nonexistent_key") == "nonexistent_key"


def test_optimize_tab_chinese():
    """An explicit zh-CN request returns the Chinese value."""
    assert t("fw.tab.optimize", lang="zh-CN") == "优化"


def test_optimize_tab_english():
    """An explicit en request returns the English value."""
    assert t("fw.tab.optimize", lang="en") == "Optimize"


def test_optimize_tab_unknown_language_falls_back_to_english():
    """Requesting an unsupported language falls back to the English value."""
    assert t("fw.tab.optimize", lang="fr") == "Optimize"


@pytest.mark.parametrize(
    "lang, expected",
    [
        ("en", "Fetched 3 model(s)"),
        ("zh-CN", "已获取 3 个模型"),
    ],
)
def test_format_substitution(lang, expected):
    """Placeholder substitution works in both supported languages."""
    assert t("settings.status.models_fetched", lang=lang, count=3) == expected


def test_every_local_provider_has_translation_key():
    """Each provider id in LOCAL_PROVIDERS must have a provider.{id} key."""
    missing = []
    for provider in LOCAL_PROVIDERS:
        key = f"provider.{provider['id']}"
        if key not in TRANSLATIONS:
            missing.append(key)
    assert not missing, f"Missing provider translation keys: {missing}"


def test_every_default_style_has_translation_key():
    """Each default style id must have a style.{id} key."""
    missing = []
    for style in DEFAULT_CONFIG["styles"]:
        key = f"style.{style['id']}"
        if key not in TRANSLATIONS:
            missing.append(key)
    assert not missing, f"Missing style translation keys: {missing}"
