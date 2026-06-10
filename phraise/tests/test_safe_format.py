"""TDD validation for _safe_format(): does it correctly preserve user text with
curly braces through Python .format() templating, or corrupt it?

Metis review flagged this as a potential bug — tests settle definitively.
"""

import unittest
from phraise.llm_client import _safe_format


class TestSafeFormatPreservesBraces(unittest.TestCase):
    """Every test verifies a specific edge case of brace preservation."""

    # ── Baseline (no braces in value) ────────────────────────────────────

    def test_no_braces_passthrough(self):
        """Plain text without braces passes through unchanged."""
        result = _safe_format("Hello {name}", name="World")
        self.assertEqual(result, "Hello World")

    def test_multiple_kwargs_no_braces(self):
        """Multiple plain values all interpolate correctly."""
        result = _safe_format("{a} {b} {c}", a="x", b="y", c="z")
        self.assertEqual(result, "x y z")

    # ── Single brace pairs ───────────────────────────────────────────────

    def test_simple_curly_braces_preserved(self):
        """User text with {curly} braces is preserved verbatim."""
        result = _safe_format("Result: {text}", text="hello {world}")
        self.assertEqual(result, "Result: hello {world}")

    def test_multiple_brace_pairs_in_value(self):
        """Multiple brace pairs in a single value all preserved."""
        result = _safe_format("Got: {val}", val="a{b}c{d}e")
        self.assertEqual(result, "Got: a{b}c{d}e")

    def test_adjacent_braces(self):
        """Adjacent closing/opening braces preserved."""
        result = _safe_format("X: {x}", x="}{")
        self.assertEqual(result, "X: }{")

    # ── JSON / code snippets ─────────────────────────────────────────────

    def test_json_snippet_preserved(self):
        """JSON with curly braces survives formatting."""
        result = _safe_format("Data: {data}", data='{"key": "value"}')
        self.assertEqual(result, 'Data: {"key": "value"}')

    def test_fstring_pattern_preserved(self):
        """f-string literal in user text is preserved."""
        result = _safe_format("Got: {text}", text='f"Hello {name}"')
        self.assertEqual(result, 'Got: f"Hello {name}"')

    def test_template_literal_preserved(self):
        """User text that looks like a Python format string is preserved."""
        result = _safe_format(
            "Prompt: {prompt}",
            prompt="Return {count} items from {collection}",
        )
        self.assertEqual(result, "Prompt: Return {count} items from {collection}")

    # ── Empty / numbered braces ──────────────────────────────────────────

    def test_empty_braces_preserved(self):
        """Empty {} braces that would be positional in .format() are safe."""
        result = _safe_format("Val: {val}", val="{}")
        self.assertEqual(result, "Val: {}")

    def test_numbered_braces_preserved(self):
        """Numbered {0} {1} braces are preserved."""
        result = _safe_format("Val: {val}", val="{0} and {1}")
        self.assertEqual(result, "Val: {0} and {1}")

    def test_format_spec_braces_preserved(self):
        """Format specifiers like {x:.2f} in user text are preserved."""
        result = _safe_format("Stats: {s}", s="avg {value:.2f}")
        self.assertEqual(result, "Stats: avg {value:.2f}")

    # ── Name collision / injection attempt ───────────────────────────────

    def test_value_matches_placeholder_name(self):
        """User text containing {text} when {text} is the placeholder name
        must NOT be reinterpreted as a format field."""
        result = _safe_format("Result: {text}", text="{text}")
        self.assertEqual(result, "Result: {text}")

    def test_value_matches_original_text_placeholder(self):
        """Simulates real prompt: original_text containing {original_text}."""
        result = _safe_format(
            "Original text: {original_text}\nStyle: {style}",
            original_text="{original_text} and {style}",
            style="concise",
        )
        self.assertEqual(
            result,
            "Original text: {original_text} and {style}\nStyle: concise",
        )

    # ── Unmatched / imbalanced braces ────────────────────────────────────

    def test_opening_brace_without_closing(self):
        """Unmatched opening brace in user text is preserved."""
        result = _safe_format("X: {x}", x="hello {world")
        self.assertEqual(result, "X: hello {world")

    def test_closing_brace_without_opening(self):
        """Unmatched closing brace in user text is preserved."""
        result = _safe_format("X: {x}", x="hello world}")
        self.assertEqual(result, "X: hello world}")

    def test_odd_number_of_braces(self):
        """Odd number of braces (3 opening, 3 closing) is preserved."""
        result = _safe_format("X: {x}", x="pre {{{ inside }}} post")
        self.assertEqual(result, "X: pre {{{ inside }}} post")

    # ── Template already has doubled braces (real prompt scenario) ───────

    def test_real_template_scenario(self):
        """Simulates USER_PROMPT_OPTIMIZE: template has {{ for JSON structure,
        user text contains curly braces."""
        template = "Return JSON:\n{{\n  \"key\": \"{original_text}\"\n}}"
        result = _safe_format(template, original_text="hello {name} [data]")
        self.assertEqual(
            result,
            'Return JSON:\n{\n  "key": "hello {name} [data]"\n}',
        )

    def test_real_template_arbitrary_braces(self):
        """Simulates USER_PROMPT_CUSTOM with complex user text."""
        template = (
            "Execute the user instruction on the following text.\n"
            "Original: {original_text}\n"
            "Instruction: {custom_instruction}\n\n"
            "Return JSON:\n{{\n  \"result\": \"processed text\"\n}}"
        )
        result = _safe_format(
            template,
            original_text="The set S = {x | x > 0} is unbounded.",
            custom_instruction='Output as JSON: {"values": [...]}',
        )
        expected = (
            "Execute the user instruction on the following text.\n"
            "Original: The set S = {x | x > 0} is unbounded.\n"
            'Instruction: Output as JSON: {"values": [...]}\n'
            '\n'
            'Return JSON:\n{\n  "result": "processed text"\n}'
        )
        self.assertEqual(result, expected)

    # ── Multiple kwargs all with braces ──────────────────────────────────

    def test_multiple_kwargs_all_with_braces(self):
        """Every kwarg value contains braces — all must be preserved."""
        result = _safe_format(
            "{a} | {b} | {c}",
            a="x{y}",
            b="u{v}",
            c="p{q}",
        )
        self.assertEqual(result, "x{y} | u{v} | p{q}")

    # ── Non-string kwargs pass through untouched ─────────────────────────

    def test_non_string_kwargs_untouched(self):
        """Non-string values (int, float, None) are not escaped."""
        result = _safe_format(
            "Count: {count}, Ratio: {ratio}, Null: {null}",
            count=42,
            ratio=3.14,
            null=None,
        )
        self.assertEqual(result, "Count: 42, Ratio: 3.14, Null: None")

    def test_mixed_string_and_non_string(self):
        """Mixed string (with braces) and non-string kwargs."""
        result = _safe_format(
            "{label}: {value}",
            label="Score{bonus}",
            value=100,
        )
        self.assertEqual(result, "Score{bonus}: 100")

    # ── Explicit double-brace in user input (user literally wrote {{) ────

    def test_user_literally_wrote_double_braces(self):
        """If user text itself contains the double-brace escaping sequence
        {{ }}, it should survive correctly (not be reinterpreted)."""
        result = _safe_format(
            "Output: {text}",
            text=r"Use \verb|{{x}}| for literal braces in LaTeX",
        )
        # {{ in user text → {{{{ after escaping → {{ after .format() = correct
        self.assertEqual(
            result,
            r"Output: Use \verb|{{x}}| for literal braces in LaTeX",
        )


if __name__ == "__main__":
    unittest.main()
