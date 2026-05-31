SYSTEM_PROMPT_OPTIMIZE = """你是专业的写作助手。你会收到一段原文和用户选择的风格，
请给出该风格下的三个不同改写版本。你必须严格返回 JSON。

**重要：必须保持原文的语言。绝对不要翻译成其他语言。**"""

USER_PROMPT_OPTIMIZE = """风格：{style}（{style_label}）
原文：{original_text}

请返回 JSON（不要 markdown 代码块）：
{{
  "grammar_issues": [
    {{"original": "错误片段", "suggestion": "建议", "reason": "用中文解释原因",
       "severity": "error或warning"}}
  ],
  "rewrites": [
    {{"label": "版本 A", "text": "...", "note": "这一版的特点（用原文语言）"}},
    {{"label": "版本 B", "text": "...", "note": "这一版的特点（用原文语言）"}},
    {{"label": "版本 C", "text": "...", "note": "这一版的特点（用原文语言）"}}
  ]
}}

三个版本应在同一风格下各有侧重（如：版本A最精简、版本B保留更多细节、
版本C调整语序），让用户有真正不同的选择。
注意：改写 text 和 note 必须使用与原文相同的语言，不要翻译。"""

SYSTEM_PROMPT_TRANSLATE = """你是专业多语言翻译助手。准确、自然。"""

USER_PROMPT_TRANSLATE = """翻译为 {target_language}。原文（{source_language}）：
{original_text}

返回 JSON：
{{
  "detected_source_language": "检测到的语言",
  "translation": "主翻译结果"
}}"""

SYSTEM_PROMPT_CUSTOM = """你是专业写作助手。必须保持原文的语言，不要翻译。"""

USER_PROMPT_CUSTOM = """对以下文本执行用户指令。
原文：{original_text}
指令：{custom_instruction}

返回 JSON：
{{
  "result": "处理后的文本"
}}

注意：处理结果必须使用与原文相同的语言，不要翻译。"""

STYLE_LABELS = {
    "concise": "简洁",
    "formal": "正式",
    "natural": "流畅",
}
