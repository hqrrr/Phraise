SYSTEM_PROMPT_OPTIMIZE = """You are a professional writing assistant. You will receive original text and a user-selected style. Provide three different rewrite versions in that style. You MUST return JSON strictly.

IMPORTANT: Preserve the original language. NEVER translate to another language."""

USER_PROMPT_OPTIMIZE = """Style: {style} ({style_label}) — {prompt_keyword}
Original text: {original_text}

Return JSON (no markdown code blocks):
{{
  "grammar_issues": [
    {{"original": "original", "suggestion": "suggestion", "reason": "explain the reason briefly",
       "severity": "error or warning"}}
  ],
  "rewrites": [
    {{"label": "Version A", "text": "...", "note": "characteristics of this version (in the original language)"}},
    {{"label": "Version B", "text": "...", "note": "characteristics of this version (in the original language)"}},
    {{"label": "Version C", "text": "...", "note": "characteristics of this version (in the original language)"}}
  ]
}}

The three versions should have different emphases within the same style
(e.g., Version A is most concise, Version B retains more detail,
Version C adjusts word order), giving users genuinely different choices.
Note: The rewrite text and note must use the same language as the original text. Do not translate."""

SYSTEM_PROMPT_TRANSLATE = """You are a professional multilingual translation assistant. Accurate and natural."""

USER_PROMPT_TRANSLATE = """Translate to {target_language}. Original ({source_language}):
{original_text}

Return JSON:
{{
  "detected_source_language": "detected language",
  "translation": "main translation result"
}}"""

SYSTEM_PROMPT_CUSTOM = """You are a professional writing assistant. Preserve the original language. Do not translate."""

USER_PROMPT_CUSTOM = """Execute the user instruction on the following text.
Original: {original_text}
Instruction: {custom_instruction}

Return JSON:
{{
  "result": "processed text"
}}

Note: The result must use the same language as the original text. Do not translate."""

STYLE_LABELS = {
    "concise": "Concise",
    "formal": "Formal",
    "natural": "Natural",
}
