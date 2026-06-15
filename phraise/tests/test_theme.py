"""RED-phase tests for the theme key contract, registry, and style generator output.

These tests assert the shape and behaviour of theme-related symbols.  They
are expected to FAIL until Tasks 10-12/22 implement the missing symbols
(``THEMES``, ``LEGACY_THEME_MAP``, ``resolve_theme_name``, etc.).

Collection must succeed *without* those symbols, so missing names are
accessed lazily via ``getattr`` / ``hasattr`` inside the test methods.
"""

import unittest

from PySide6.QtWidgets import QApplication

import phraise.theme as theme_mod
from phraise.theme import (
    DEFAULT_SIZING,
    MANDATORY_COLOR_KEYS,
    THEME_COLORS,
    ThemeSizing,
    apply_theme,
    generate_app_stylesheet,
    resolve_theme_name,
    theme_notifier,
)


# ── QApplication singleton for Qt widget tests ──────────────────────────────

class _QtTestBase(unittest.TestCase):
    """Base class that ensures a QApplication exists for stylesheet tests."""

    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance()
        if cls._app is None:
            cls._app = QApplication([])

    @classmethod
    def tearDownClass(cls) -> None:
        # Don't delete _app here; other test classes may reuse it.
        pass


# ── 1. TestThemeKeyContract ─────────────────────────────────────────────────

class TestThemeKeyContract(unittest.TestCase):
    """Verify the mandatory color key list and the default theme comply with it."""

    def test_mandatory_color_keys_length(self):
        self.assertEqual(
            len(MANDATORY_COLOR_KEYS), 17,
            "MANDATORY_COLOR_KEYS should have exactly 17 entries",
        )

    def test_default_theme_has_all_mandatory_keys(self):
        for key in MANDATORY_COLOR_KEYS:
            with self.subTest(key=key):
                self.assertIn(key, THEME_COLORS,
                              f"THEME_COLORS missing mandatory key {key!r}")

    def test_default_theme_has_no_extra_color_keys(self):
        extra = set(THEME_COLORS) - set(MANDATORY_COLOR_KEYS)
        self.assertFalse(
            extra,
            f"THEME_COLORS has extra keys not in MANDATORY_COLOR_KEYS: {extra}",
        )

    def test_all_default_colors_are_hex_strings(self):
        for key, value in THEME_COLORS.items():
            with self.subTest(key=key):
                self.assertTrue(
                    value.startswith("#"),
                    f"{key!r}: {value!r} does not start with '#'",
                )
                self.assertEqual(len(value), 7,
                                f"{key!r}: {value!r} should be #RRGGBB")

    def test_distinct_semantic_colors(self):
        """Semantic colors should differ from each other and from background."""
        self.assertNotEqual(THEME_COLORS["red"], THEME_COLORS["green"],
                            "red and green must be different")
        self.assertNotEqual(THEME_COLORS["orange"], THEME_COLORS["yellow"],
                            "orange and yellow must be different")
        self.assertNotEqual(THEME_COLORS["bg"], THEME_COLORS["text"],
                            "bg and text must be different")


# ── 2. TestThemeRegistry ────────────────────────────────────────────────────

class TestThemeRegistry(unittest.TestCase):
    """Verify the ``THEMES`` registry exists and has the expected shape.

    ``THEMES`` does not exist yet (Task 10+); these tests use lazy access
    so collection succeeds.  They will FAIL until it is implemented.
    """

    def test_themes_registry_exists(self):
        themes = getattr(theme_mod, "THEMES", None)
        self.assertIsNotNone(themes, "THEMES should exist in phraise.theme")
        self.assertIsInstance(themes, dict,
                              "THEMES should be a dict")

    def test_themes_registry_has_expected_length(self):
        themes = getattr(theme_mod, "THEMES", None)
        self.assertIsNotNone(themes, "THEMES should exist in phraise.theme")
        self.assertEqual(
            len(themes), 9,
            f"THEMES should contain exactly 9 themes, got {len(themes)}",
        )

    def test_every_theme_has_colors_and_sizing(self):
        themes = getattr(theme_mod, "THEMES", None)
        self.assertIsNotNone(themes, "THEMES should exist in phraise.theme")
        for name, entry in themes.items():
            with self.subTest(theme=name):
                self.assertIn("colors", entry,
                              f"Theme {name!r} missing 'colors'")
                self.assertIn("sizing", entry,
                              f"Theme {name!r} missing 'sizing'")
                self.assertIsInstance(entry["colors"], dict,
                                      f"Theme {name!r} 'colors' not a dict")
                self.assertIsInstance(entry["sizing"], dict,
                                      f"Theme {name!r} 'sizing' not a dict")

    def test_all_themes_have_identical_color_key_sets(self):
        themes = getattr(theme_mod, "THEMES", None)
        self.assertIsNotNone(themes, "THEMES should exist in phraise.theme")
        entries = list(themes.items())
        if not entries:
            self.skipTest("no themes to compare")
        first_name, first_theme = entries[0]
        first_keys = set(first_theme.get("colors", {}))
        for name, entry in entries[1:]:
            with self.subTest(theme=name):
                self.assertEqual(
                    set(entry.get("colors", {})), first_keys,
                    f"Theme {name!r} color keys differ from {first_name!r}",
                )

    def test_all_themes_have_identical_sizing_key_sets(self):
        themes = getattr(theme_mod, "THEMES", None)
        self.assertIsNotNone(themes, "THEMES should exist in phraise.theme")
        entries = list(themes.items())
        if not entries:
            self.skipTest("no themes to compare")
        first_name, first_theme = entries[0]
        first_keys = set(first_theme.get("sizing", {}))
        for name, entry in entries[1:]:
            with self.subTest(theme=name):
                self.assertEqual(
                    set(entry.get("sizing", {})), first_keys,
                    f"Theme {name!r} sizing keys differ from {first_name!r}",
                )

    def test_theme_color_sets_match_mandatory_keys(self):
        themes = getattr(theme_mod, "THEMES", None)
        self.assertIsNotNone(themes, "THEMES should exist in phraise.theme")
        mandatory = set(MANDATORY_COLOR_KEYS)
        for name, entry in themes.items():
            with self.subTest(theme=name):
                self.assertEqual(
                    set(entry.get("colors", {})), mandatory,
                    f"Theme {name!r} colors don't match MANDATORY_COLOR_KEYS",
                )

    def test_theme_sizing_keys_match_typing_definition(self):
        themes = getattr(theme_mod, "THEMES", None)
        self.assertIsNotNone(themes, "THEMES should exist in phraise.theme")
        expected_sizing_keys = set(ThemeSizing.__annotations__)
        for name, entry in themes.items():
            with self.subTest(theme=name):
                actual = set(entry.get("sizing", {}))
                self.assertEqual(
                    actual, expected_sizing_keys,
                    f"Theme {name!r} sizing keys don't match ThemeSizing",
                )


# ── 3. TestThemeKeyConsistency ──────────────────────────────────────────────

class TestThemeKeyConsistency(unittest.TestCase):
    """Cross-check that DEFAULT_SIZING matches the ThemeSizing typed dict."""

    def test_default_sizing_keys_match_typing_definition(self):
        expected = set(ThemeSizing.__annotations__)
        actual = set(DEFAULT_SIZING)
        self.assertEqual(
            actual, expected,
            f"DEFAULT_SIZING keys differ from ThemeSizing: "
            f"missing={expected - actual!r}, extra={actual - expected!r}",
        )

    def test_generate_app_stylesheet_with_default_theme_is_non_empty(self):
        css = generate_app_stylesheet(THEME_COLORS)
        self.assertIsInstance(css, str)
        self.assertTrue(css.strip(), "Generated stylesheet should not be empty")

    def test_generate_app_stylesheet_with_default_theme_contains_bg_color(self):
        css = generate_app_stylesheet(THEME_COLORS)
        self.assertIn(THEME_COLORS["bg"], css,
                      "Stylesheet should contain the theme background color")


# ── 4. TestStylesheetGeneration ─────────────────────────────────────────────

class TestStylesheetGeneration(_QtTestBase):
    """Verify ``generate_app_stylesheet`` produces valid CSS for each theme."""

    def test_generates_non_empty_css_for_default_theme(self):
        css = generate_app_stylesheet(THEME_COLORS)
        self.assertIsInstance(css, str)
        self.assertTrue(css.strip(), "Generated stylesheet is empty")

    def test_default_stylesheet_contains_key_selectors(self):
        css = generate_app_stylesheet(THEME_COLORS)
        for selector in ("QWidget", "QMenu", "QToolTip", "QScrollBar",
                          "QCheckBox", "QGroupBox"):
            with self.subTest(selector=selector):
                self.assertIn(selector, css,
                              f"Stylesheet missing {selector}")

    def test_all_registered_themes_produce_non_empty_stylesheet(self):
        themes = getattr(theme_mod, "THEMES", None)
        if themes is None:
            self.skipTest("THEMES does not exist yet")
        for name, entry in themes.items():
            with self.subTest(theme=name):
                css = generate_app_stylesheet(entry["colors"])
                self.assertIsInstance(css, str)
                self.assertTrue(css.strip(),
                                f"Theme {name!r} produced empty stylesheet")

    def test_all_registered_theme_stylesheets_contain_theme_bg_color(self):
        themes = getattr(theme_mod, "THEMES", None)
        if themes is None:
            self.skipTest("THEMES does not exist yet")
        for name, entry in themes.items():
            with self.subTest(theme=name):
                css = generate_app_stylesheet(entry["colors"])
                self.assertIn(entry["colors"]["bg"], css,
                              f"Theme {name!r} stylesheet missing its bg color")


# ── 5. TestSizingTokenTypes ─────────────────────────────────────────────────

class TestSizingTokenTypes(unittest.TestCase):
    """Verify DEFAULT_SIZING token counts, value types, and positivity."""

    def test_default_sizing_length(self):
        self.assertGreaterEqual(
            len(DEFAULT_SIZING), 15,
            f"DEFAULT_SIZING has {len(DEFAULT_SIZING)} entries, expected >= 15",
        )

    def test_all_sizing_values_are_positive(self):
        for key, value in DEFAULT_SIZING.items():
            with self.subTest(key=key):
                if isinstance(value, (int, float)):
                    self.assertGreater(value, 0,
                                       f"{key!r} ({value}) should be > 0")
                elif isinstance(value, tuple):
                    for i, v in enumerate(value):
                        self.assertGreater(v, 0,
                                           f"{key!r}[{i}] ({v}) should be > 0")
                # Ignore other types (shouldn't happen with ThemeSizing)

    def test_sizing_values_are_ints_or_tuples_of_ints(self):
        for key, value in DEFAULT_SIZING.items():
            with self.subTest(key=key):
                if isinstance(value, tuple):
                    for v in value:
                        self.assertIsInstance(
                            v, int,
                            f"{key!r} tuple element {v!r} should be int",
                        )
                else:
                    self.assertIsInstance(
                        value, int,
                        f"{key!r} ({value!r}) should be int or tuple[int,...]",
                    )

    def test_known_sizing_defaults(self):
        self.assertEqual(DEFAULT_SIZING["font_size_base"], 12)
        self.assertEqual(DEFAULT_SIZING["font_weight_normal"], 400)
        self.assertEqual(DEFAULT_SIZING["padding_btn_v"], 2)
        self.assertEqual(DEFAULT_SIZING["radius_lg"], 6)
        self.assertEqual(DEFAULT_SIZING["border_width_default"], 1)
        self.assertEqual(DEFAULT_SIZING["scrollbar_width"], 8)
        self.assertEqual(DEFAULT_SIZING["scrollbar_handle_min"], 20)
        self.assertEqual(DEFAULT_SIZING["checkbox_indicator_size"], 16)

    def test_font_weight_ordering(self):
        """Font weights should be in increasing order."""
        self.assertLess(DEFAULT_SIZING["font_weight_normal"],
                        DEFAULT_SIZING["font_weight_medium"])
        self.assertLess(DEFAULT_SIZING["font_weight_medium"],
                        DEFAULT_SIZING["font_weight_semibold"])

    def test_radius_ordering(self):
        """Border radii should be in increasing order."""
        self.assertLess(DEFAULT_SIZING["radius_sm"],
                        DEFAULT_SIZING["radius_md"])
        self.assertLess(DEFAULT_SIZING["radius_md"],
                        DEFAULT_SIZING["radius_lg"])
        self.assertLess(DEFAULT_SIZING["radius_lg"],
                        DEFAULT_SIZING["radius_xl"])

    def test_font_size_ordering(self):
        """Font sizes should be non-decreasing."""
        self.assertLessEqual(DEFAULT_SIZING["font_size_sm"],
                             DEFAULT_SIZING["font_size_base"])
        self.assertLessEqual(DEFAULT_SIZING["font_size_base"],
                             DEFAULT_SIZING["font_size_md"])
        self.assertLessEqual(DEFAULT_SIZING["font_size_md"],
                             DEFAULT_SIZING["font_size_lg"])


# ── 6. TestBackwardsCompat ──────────────────────────────────────────────────

class TestBackwardsCompat(unittest.TestCase):
    """Verify backwards-compatibility symbols exist and are correct.

    ``LEGACY_THEME_MAP``, ``resolve_theme_name``, and related symbols do
    not exist yet; accessed lazily so collection succeeds.  These tests
    will FAIL (RED) until implementation is added.
    """

    def test_legacy_theme_map_exists(self):
        legacy = getattr(theme_mod, "LEGACY_THEME_MAP", None)
        self.assertIsNotNone(legacy,
                             "LEGACY_THEME_MAP should exist in phraise.theme")
        self.assertIsInstance(legacy, dict,
                              "LEGACY_THEME_MAP should be a dict")

    def test_legacy_theme_map_dark_maps_to_catppuccin_mocha(self):
        legacy = getattr(theme_mod, "LEGACY_THEME_MAP", None)
        self.assertIsNotNone(legacy,
                             "LEGACY_THEME_MAP should exist in phraise.theme")
        self.assertIn("dark", legacy,
                      "LEGACY_THEME_MAP should contain 'dark' key")
        self.assertEqual(
            legacy["dark"], "Catppuccin Mocha",
            "'dark' should map to 'Catppuccin Mocha'",
        )

    def test_legacy_theme_map_has_no_light_entry(self):
        legacy = getattr(theme_mod, "LEGACY_THEME_MAP", None)
        self.assertIsNotNone(legacy,
                             "LEGACY_THEME_MAP should exist in phraise.theme")
        self.assertNotIn("light", legacy,
                         "LEGACY_THEME_MAP should NOT contain 'light' key")

    def test_resolve_theme_name_exists(self):
        fn = getattr(theme_mod, "resolve_theme_name", None)
        self.assertIsNotNone(fn,
                             "resolve_theme_name should exist in phraise.theme")
        self.assertTrue(callable(fn),
                        "resolve_theme_name should be callable")

    def test_get_theme_exists(self):
        fn = getattr(theme_mod, "get_theme", None)
        self.assertIsNotNone(fn,
                             "get_theme should exist in phraise.theme")
        self.assertTrue(callable(fn),
                        "get_theme should be callable")

    def test_list_themes_exists(self):
        fn = getattr(theme_mod, "list_themes", None)
        self.assertIsNotNone(fn,
                             "list_themes should exist in phraise.theme")
        self.assertTrue(callable(fn),
                        "list_themes should be callable")

    def test_is_dark_theme_exists(self):
        fn = getattr(theme_mod, "is_dark_theme", None)
        self.assertIsNotNone(fn,
                             "is_dark_theme should exist in phraise.theme")
        self.assertTrue(callable(fn),
                        "is_dark_theme should be callable")

    def test_apply_theme_exists(self):
        fn = getattr(theme_mod, "apply_theme", None)
        self.assertIsNotNone(fn,
                             "apply_theme should exist in phraise.theme")
        self.assertTrue(callable(fn),
                        "apply_theme should be callable")

    def test_theme_notifier_exists(self):
        obj = getattr(theme_mod, "theme_notifier", None)
        self.assertIsNotNone(obj,
                             "theme_notifier should exist in phraise.theme")


# ── Self-check: module-level imports must all resolve ───────────────────────

class TestModuleImports(unittest.TestCase):
    """Ensure the symbols we import at module level actually resolve."""

    def test_imported_symbols_exist(self):
        # These are top-level imports; if they didn't exist, collection
        # would have already failed.  Still good to assert explicitly.
        self.assertIsNotNone(MANDATORY_COLOR_KEYS)
        self.assertIsNotNone(THEME_COLORS)
        self.assertIsNotNone(DEFAULT_SIZING)
        self.assertIsNotNone(generate_app_stylesheet)
        self.assertIsNotNone(ThemeSizing)
        self.assertIsNotNone(apply_theme)
        self.assertIsNotNone(resolve_theme_name)
        self.assertIsNotNone(theme_notifier)


# ── 8. TestThemeEdgeCases ────────────────────────────────────────────────────

class TestThemeEdgeCases(unittest.TestCase):
    """Edge-case and contract tests for theme resolution and application."""

    def test_resolve_unknown_theme_falls_back_to_catppuccin_mocha(self):
        result = resolve_theme_name("not-a-theme")
        self.assertEqual(result, "Catppuccin Mocha")

    def test_apply_theme_with_empty_custom_css(self):
        result = apply_theme("GitHub Light", custom_css="")
        self.assertEqual(result, "GitHub Light")

    def test_rapid_theme_switching_updates_notifier(self):
        apply_theme("One Dark Pro")
        self.assertEqual(theme_notifier.current_theme, "One Dark Pro")

        apply_theme("GitHub Light")
        self.assertEqual(theme_notifier.current_theme, "GitHub Light")

        apply_theme("Catppuccin Mocha")
        self.assertEqual(theme_notifier.current_theme, "Catppuccin Mocha")
