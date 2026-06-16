# PhrAIse - AI writing assistant
# License: GNU GPLv3
# GitHub: https://github.com/hqrrr/Phraise
# Author: hqrrr
#
# Description: Theme loading, resolution, and stylesheet generation.
"""Centralized CSS theme system for PhrAIse.

All color constants, style generators, and the Theme class live here.
No other module should contain hardcoded hex color values.
"""

from typing import TypedDict

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QApplication

# ── Theme type definitions ──────────────────────────────────────────────────

# Keys every color theme must provide, with their semantic UI roles.
MANDATORY_COLOR_KEYS: list[str] = [
    "bg",            # Main application background
    "bg_darker",     # Darker background for inputs and title bars
    "surface",       # Elevated surface background for cards and controls
    "surface_hover", # Hover state background for interactive surfaces
    "border",        # Default border color for frames and inputs
    "text",          # Primary text color
    "text_muted",    # Secondary/muted text color
    "text_dim",      # Tertiary/disabled text color
    "accent",        # Primary accent color for active/selected items
    "accent_hover",  # Hover state for accent-colored elements
    "red",           # Error/danger indicator color
    "red_hover",     # Hover state for red/danger elements
    "orange",        # Warning/highlight indicator color
    "green",         # Success/positive indicator color
    "yellow",        # Caution/neutral highlight color
    "white",         # Pure white for high-contrast text on accents
    "grip",          # Drag handle / resize grip color
]

# Mapping of theme color names to CSS hex values.
ThemeColors = dict[str, str]


class ThemeSizing(TypedDict):
    """Numeric sizing tokens used throughout the UI stylesheet generators."""
    # Font sizes (px)
    font_size_sm: int          # Small labels and action buttons
    font_size_base: int        # Default body/control text size
    font_size_md: int          # Tab labels and slightly emphasized text
    font_size_lg: int          # Larger button/label text

    # Font weights
    font_weight_normal: int    # Regular body text
    font_weight_medium: int    # Emphasized controls (tabs, buttons)
    font_weight_semibold: int  # Strong emphasis / headings

    # Button padding (px)
    padding_btn_v: int         # Vertical padding for generic push buttons
    padding_btn_h: int         # Horizontal padding for generic push buttons
    padding_action_btn_v: int  # Vertical padding for solid action buttons
    padding_action_btn_h: int  # Horizontal padding for solid action buttons
    padding_style_btn_v: int   # Vertical padding for style-selector buttons
    padding_style_btn_h: int   # Horizontal padding for style-selector buttons

    # Control padding (px)
    padding_combo: tuple[int, int, int, int]  # QComboBox padding (top, right, bottom, left)
    padding_entry: tuple[int, int]            # QLineEdit padding (vertical, horizontal)
    padding_tab: tuple[int, int]              # QTabBar tab padding (vertical, horizontal)
    padding_toast: tuple[int, int]            # Toast label padding (vertical, horizontal)
    padding_menu_item: tuple[int, int]        # QMenu item padding (vertical, horizontal)
    padding_text_edit: int                    # QTextEdit uniform padding
    padding_menu: int                         # QMenu internal padding
    padding_tooltip: tuple[int, int]          # QToolTip padding (vertical, horizontal)

    # Border radii (px)
    radius_sm: int             # Small radius (checkbox, scrollbars)
    radius_md: int             # Medium radius (buttons, menus, tooltips)
    radius_lg: int             # Large radius (cards, combo boxes, entries)
    radius_xl: int             # Extra-large radius (toasts)

    # Borders (px)
    border_width_default: int  # Standard 1px border for inputs and frames

    # Scrollbar (px)
    scrollbar_width: int       # Width of vertical/horizontal scrollbar track
    scrollbar_handle_min: int  # Minimum height/width of scrollbar handle

    # Checkbox (px)
    checkbox_indicator_size: int  # Width and height of QCheckBox indicator

    # Combo box (px)
    combo_dropdown_width: int  # Width of QComboBox drop-down subcontrol
    combo_arrow_size: int      # Width/height of QComboBox down-arrow

    # Group box (px)
    groupbox_margin_top: int   # Top margin reserved for QGroupBox title
    groupbox_padding_top: int  # Top padding inside QGroupBox
    groupbox_title_left: int   # Left offset of QGroupBox title
    groupbox_title_padding_h: int  # Horizontal padding around QGroupBox title

    # Button dimensions (px) -- not currently hardcoded in style generators
    button_width_sm: int       # Default small action button width
    button_height_sm: int      # Default small action button height
    button_width_md: int       # Default medium style button width
    button_height_md: int      # Default medium style button height


# A complete theme bundles a color palette with its sizing tokens.
FullTheme = dict[str, ThemeColors | ThemeSizing]


# Cross-platform UI font stack; Segoe UI + Microsoft YaHei UI keeps Latin and
# Simplified Chinese glyphs harmonious at small sizes.
FONT_FAMILY_UI = (
    '"Segoe UI", "Microsoft YaHei UI", "PingFang SC", '
    '"Hiragino Sans GB", "Source Han Sans SC", sans-serif'
)
FONT_FAMILY_MONO = (
    '"Consolas", "Microsoft YaHei Mono", "Source Han Sans SC", '
    '"Courier New", monospace'
)

# ── Default sizing values (extracted from style generators) ─────────────────
DEFAULT_SIZING: ThemeSizing = {
    "font_size_sm": 12,
    "font_size_base": 13,
    "font_size_md": 14,
    "font_size_lg": 15,
    "font_weight_normal": 400,
    "font_weight_medium": 500,
    "font_weight_semibold": 600,
    "padding_btn_v": 2,
    "padding_btn_h": 6,
    "padding_action_btn_v": 4,
    "padding_action_btn_h": 10,
    "padding_style_btn_v": 4,
    "padding_style_btn_h": 10,
    "padding_combo": (4, 24, 4, 10),
    "padding_entry": (6, 10),
    "padding_tab": (8, 20),
    "padding_toast": (4, 12),
    "padding_menu_item": (6, 24),
    "padding_text_edit": 4,
    "padding_menu": 4,
    "padding_tooltip": (4, 8),
    "radius_sm": 3,
    "radius_md": 4,
    "radius_lg": 6,
    "radius_xl": 8,
    "border_width_default": 1,
    "scrollbar_width": 8,
    "scrollbar_handle_min": 20,
    "checkbox_indicator_size": 16,
    "combo_dropdown_width": 22,
    "combo_arrow_size": 10,
    "groupbox_margin_top": 8,
    "groupbox_padding_top": 16,
    "groupbox_title_left": 10,
    "groupbox_title_padding_h": 4,
    "button_width_sm": 60,
    "button_height_sm": 24,
    "button_width_md": 80,
    "button_height_md": 28,
}

# Palette modules import DEFAULT_SIZING/FullTheme from this module, so they
# must be imported after those names are defined above.
from phraise.theme_palettes import (  # noqa: E402
    catppuccin_latte,
    catppuccin_mocha,
    github_light,
    monokai,
    nord_dark,
    one_dark_pro,
    one_light,
    solarized_dark,
    solarized_light,
)

# ── Catppuccin Mocha color palette ──────────────────────────────────────────

THEME_COLORS: dict[str, str] = {
    "bg": "#1e1e2e",
    "bg_darker": "#181825",
    "surface": "#313244",
    "surface_hover": "#45475a",
    "border": "#45475a",
    "text": "#cdd6f4",
    "text_muted": "#a6adc8",
    "text_dim": "#6c7086",
    "accent": "#6c5ce7",
    "accent_hover": "#7c6cf7",
    "red": "#f38ba8",
    "red_hover": "#f06292",
    "orange": "#fab387",
    "green": "#a6e3a1",
    "yellow": "#f9e2af",
    "white": "#ffffff",
    "grip": "#585b70",
}

DEFAULT_THEME = THEME_COLORS


# ── Theme registry ────────────────────────────────────────────────────────────────

THEMES: dict[str, FullTheme] = {
    "Catppuccin Mocha": catppuccin_mocha.theme,
    "One Dark Pro": one_dark_pro.theme,
    "Solarized Dark": solarized_dark.theme,
    "Nord Dark": nord_dark.theme,
    "Monokai": monokai.theme,
    "Catppuccin Latte": catppuccin_latte.theme,
    "Solarized Light": solarized_light.theme,
    "GitHub Light": github_light.theme,
    "One Light": one_light.theme,
}

_DARK_THEMES: frozenset[str] = frozenset({
    "Catppuccin Mocha",
    "One Dark Pro",
    "Solarized Dark",
    "Nord Dark",
    "Monokai",
})


LEGACY_THEME_MAP: dict[str, str] = {"dark": "Catppuccin Mocha"}


def resolve_theme_name(config_value: str) -> str:
    """Resolve a config-stored value to a canonical theme name.

    Handles legacy names (e.g. ``"dark"``) via *LEGACY_THEME_MAP* and
    validates against registered *THEMES*.  Falls back to
    ``"Catppuccin Mocha"`` when the value is unknown.
    """
    if config_value in LEGACY_THEME_MAP:
        return LEGACY_THEME_MAP[config_value]
    if config_value in THEMES:
        return config_value
    return "Catppuccin Mocha"


def get_theme(name: str) -> FullTheme:
    """Return the theme named *name*, or fall back to Catppuccin Mocha."""
    return THEMES.get(name, THEMES["Catppuccin Mocha"])


def list_themes() -> list[str]:
    """Return sorted list of all registered theme names."""
    return sorted(THEMES)


def is_dark_theme(name: str) -> bool:
    """Return True if *name* is a dark theme, False otherwise."""
    return name in _DARK_THEMES


# ── Helpers ──────────────────────────────────────────────────────────────────


def _resolve_color(theme: dict, value: str) -> str:
    """Return the actual color for *value*.

    If *value* starts with ``"#"`` it is treated as a raw hex colour and
    returned as-is.  Otherwise it is looked up in *theme*.
    """
    if value.startswith("#"):
        return value
    return theme.get(value, value)


def rgba(hex_color: str, alpha: int) -> str:
    """Convert a hex colour to an ``rgba(r, g, b, a)`` string.

    Example: ``rgba("#1e1e2e", 200)`` → ``"rgba(30, 30, 46, 200)"``.
    """
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r}, {g}, {b}, {alpha})"


def _px(value: int | tuple[int, ...]) -> str:
    """Format a sizing token value as a CSS pixel string.

    Scalars become ``"Npx"``; tuples become space-separated ``"Apx Bpx ..."``.
    """
    if isinstance(value, tuple):
        return " ".join(f"{v}px" for v in value)
    return f"{value}px"


# ── Style-sheet generators ──────────────────────────────────────────────────
#
# Every generator receives *theme* (a colour dict) as the first argument and
# returns a Qt style-sheet string.  Other parameters tweak the appearance.


def btn_style(theme: dict, hover_color: str | None = None,
              sizing: ThemeSizing | None = None) -> str:
    """Generic transparent push-button.

    *hover_color* may be a raw hex string (``"#f38ba8"``) or a theme key
    (``"accent"``).  Defaults to ``"surface_hover"``.
    """
    s = sizing if sizing is not None else DEFAULT_SIZING
    hc = _resolve_color(theme, hover_color) if hover_color else theme["surface_hover"]
    return (
        f"QPushButton {{ background: transparent; color: {theme['text_muted']}; "
        f"border: none; font-size: {_px(s['font_size_md'])}; "
        f"padding: {_px(s['padding_btn_v'])} {_px(s['padding_btn_h'])}; "
        f"border-radius: {_px(s['radius_sm'])}; }}"
        f"QPushButton:hover {{ background: {hc}; color: {theme['text']}; }}"
    )


def action_btn_style(theme: dict, bg: str,
                     sizing: ThemeSizing | None = None) -> str:
    """Small action button with a solid background.

    *bg* may be a raw hex or a theme key.  Hover is always the accent-hover
    colour.
    """
    s = sizing if sizing is not None else DEFAULT_SIZING
    bg_color = _resolve_color(theme, bg)
    return (
        f"QPushButton {{ background: {bg_color}; color: {theme['text']}; "
        f"border: none; border-radius: {_px(s['radius_md'])}; "
        f"font-size: {_px(s['font_size_sm'])}; "
        f"font-weight: {s['font_weight_medium']}; "
        f"padding: {_px(s['padding_action_btn_v'])} {_px(s['padding_action_btn_h'])}; }}"
        f"QPushButton:hover {{ background: {theme['accent_hover']}; }}"
    )


def style_btn_style(theme: dict, active: bool,
                    sizing: ThemeSizing | None = None) -> str:
    """Style-selector toggle button."""
    s = sizing if sizing is not None else DEFAULT_SIZING
    bg = theme["accent"] if active else theme["surface"]
    color = theme["white"] if active else theme["text_muted"]
    return (
        f"QPushButton {{ background: {bg}; color: {color}; border: none; "
        f"border-radius: {_px(s['radius_md'])}; "
        f"font-size: {_px(s['font_size_base'])}; "
        f"font-weight: {s['font_weight_medium']}; "
        f"padding: {_px(s['padding_style_btn_v'])} {_px(s['padding_style_btn_h'])}; }}"
        f"QPushButton:hover {{ background: {theme['accent_hover']}; "
        f"color: {theme['white']}; }}"
    )


def combo_style(theme: dict, sizing: ThemeSizing | None = None) -> str:
    """QComboBox style."""
    s = sizing if sizing is not None else DEFAULT_SIZING
    return (
        f"QComboBox {{ background: {theme['surface']}; color: {theme['text']}; "
        f"border: {_px(s['border_width_default'])} solid {theme['border']}; "
        f"border-radius: {_px(s['radius_lg'])}; "
        f"padding: {_px(s['padding_combo'])}; "
        f"font-size: {_px(s['font_size_base'])}; }}"
        f"QComboBox:hover {{ border-color: {theme['accent']}; }}"
        f"QComboBox::drop-down {{ subcontrol-origin: padding; subcontrol-position: top right; "
        f"width: {_px(s['combo_dropdown_width'])}; "
        f"border-left: {_px(s['border_width_default'])} solid {theme['border']}; "
        f"border-top-right-radius: {_px(s['radius_lg'])}; "
        f"border-bottom-right-radius: {_px(s['radius_lg'])}; }}"
        f"QComboBox::down-arrow {{ width: {_px(s['combo_arrow_size'])}; "
        f"height: {_px(s['combo_arrow_size'])}; }}"
        f"QComboBox QAbstractItemView {{ background: {theme['surface']}; "
        f"color: {theme['text']}; selection-background-color: {theme['accent']}; "
        f"border: {_px(s['border_width_default'])} solid {theme['border']}; "
        f"border-radius: {_px(s['radius_md'])}; }}"
    )


def tab_style(theme: dict, sizing: ThemeSizing | None = None) -> str:
    """QTabWidget style."""
    s = sizing if sizing is not None else DEFAULT_SIZING
    return (
        f"QTabWidget::pane {{ border: none; background: {theme['bg']}; }}"
        f"QTabBar::tab {{ background: {theme['surface']}; "
        f"color: {theme['text_muted']}; "
        f"padding: {_px(s['padding_tab'])}; "
        f"border: none; font-size: {_px(s['font_size_md'])}; "
        f"font-weight: {s['font_weight_medium']}; }}"
        f"QTabBar::tab:selected {{ background: {theme['accent']}; "
        f"color: {theme['white']}; }}"
        f"QTabBar::tab:hover:!selected {{ background: {theme['surface_hover']}; }}"
    )


def entry_style(theme: dict, sizing: ThemeSizing | None = None) -> str:
    """QLineEdit style."""
    s = sizing if sizing is not None else DEFAULT_SIZING
    return (
        f"QLineEdit {{ background: {theme['bg_darker']}; color: {theme['text']}; "
        f"border: {_px(s['border_width_default'])} solid {theme['border']}; "
        f"border-radius: {_px(s['radius_lg'])}; "
        f"padding: {_px(s['padding_entry'])}; "
        f"font-size: {_px(s['font_size_base'])}; }}"
        f"QLineEdit:focus {{ border-color: {theme['accent']}; }}"
    )


def text_edit_style(theme: dict, sizing: ThemeSizing | None = None) -> str:
    """QTextEdit style."""
    s = sizing if sizing is not None else DEFAULT_SIZING
    return (
        f"QTextEdit {{ background: {theme['bg_darker']}; color: {theme['text']}; "
        f"border: {_px(s['border_width_default'])} solid {theme['border']}; "
        f"border-radius: {_px(s['radius_lg'])}; "
        f"font-size: {_px(s['font_size_base'])}; "
        f"padding: {_px(s['padding_text_edit'])}; }}"
    )


def card_style(theme: dict, radius: int | None = None,
               sizing: ThemeSizing | None = None) -> str:
    """Card QFrame style.  *radius* overrides the sizing token."""
    s = sizing if sizing is not None else DEFAULT_SIZING
    r = radius if radius is not None else s["radius_lg"]
    return (
        f"QFrame {{ background: {theme['surface']}; "
        f"border: 1px solid {theme['border']}; border-radius: {r}px; }}"
    )


def toast_style(theme: dict, sizing: ThemeSizing | None = None) -> str:
    """Toast notification QLabel style."""
    s = sizing if sizing is not None else DEFAULT_SIZING
    return (
        f"QLabel {{ background: {theme['surface_hover']}; color: {theme['text']}; "
        f"border-radius: {_px(s['radius_xl'])}; "
        f"padding: {_px(s['padding_toast'])}; }}"
    )


def titlebar_style(theme: dict, radius: int,
                    sizing: ThemeSizing | None = None) -> str:
    """Title-bar widget style (uses top border radii)."""
    return (
        f"background: {theme['bg_darker']}; "
        f"border-top-left-radius: {radius}px; "
        f"border-top-right-radius: {radius}px;"
    )


def bottom_bar_style(theme: dict, radius: int,
                      sizing: ThemeSizing | None = None) -> str:
    """Bottom-bar widget style (uses bottom border radii)."""
    return (
        f"background: {theme['bg_darker']}; "
        f"border-bottom-left-radius: {radius}px; "
        f"border-bottom-right-radius: {radius}px;"
    )


def scroll_area_style(theme: dict, sizing: ThemeSizing | None = None) -> str:
    """QScrollArea style."""
    return "QScrollArea { border: none; background: transparent; }"


def label_style(theme: dict, color_key: str, extra: str = "",
                 sizing: ThemeSizing | None = None) -> str:
    """Generic label style.

    *color_key* is a theme key (e.g. ``"text"``, ``"text_muted"``).
    *extra* is any additional CSS appended to the rule.
    """
    color = theme.get(color_key, color_key)
    base = f"color: {color}; background: transparent;"
    if extra:
        return f"{base} {extra}"
    return base


def separator_style(theme: dict, sizing: ThemeSizing | None = None) -> str:
    """QFrame HLine separator colour."""
    return f"color: {theme['border']};"


# ── Application-level stylesheet ────────────────────────────────────────────


def generate_app_stylesheet(theme: dict,
                            sizing: ThemeSizing | None = None) -> str:
    """Return a QApplication-level stylesheet built from *theme*."""
    s = sizing if sizing is not None else DEFAULT_SIZING
    return f"""
        QWidget {{
            background-color: {theme["bg"]};
            color: {theme["text"]};
            font-family: {FONT_FAMILY_UI};
            font-size: {_px(s['font_size_base'])};
        }}
        QMenu {{
            background-color: {theme["surface"]};
            color: {theme["text"]};
            border: {_px(s['border_width_default'])} solid {theme["border"]};
            border-radius: {_px(s['radius_md'])};
            padding: {_px(s['padding_menu'])};
        }}
        QMenu::item {{
            padding: {_px(s['padding_menu_item'])};
            border-radius: {_px(s['radius_md'])};
        }}
        QMenu::item:selected {{
            background-color: {theme["accent"]};
        }}
        QToolTip {{
            background-color: {theme["surface"]};
            color: {theme["text"]};
            border: {_px(s['border_width_default'])} solid {theme["border"]};
            border-radius: {_px(s['radius_md'])};
            padding: {_px(s['padding_tooltip'])};
        }}
        QScrollBar:vertical {{
            background: {theme["bg"]};
            width: {_px(s['scrollbar_width'])};
            border-radius: {_px(s['radius_sm'])};
        }}
        QScrollBar::handle:vertical {{
            background: {theme["surface_hover"]};
            border-radius: {_px(s['radius_sm'])};
            min-height: {_px(s['scrollbar_handle_min'])};
        }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
            height: 0px;
        }}
        QScrollBar:horizontal {{
            background: {theme["bg"]};
            height: {_px(s['scrollbar_width'])};
            border-radius: {_px(s['radius_sm'])};
        }}
        QScrollBar::handle:horizontal {{
            background: {theme["surface_hover"]};
            border-radius: {_px(s['radius_sm'])};
            min-width: {_px(s['scrollbar_handle_min'])};
        }}
        QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
            width: 0px;
        }}
        QCheckBox {{
            color: {theme["text"]};
        }}
        QCheckBox::indicator {{
            width: {_px(s['checkbox_indicator_size'])};
            height: {_px(s['checkbox_indicator_size'])};
            border: {_px(s['border_width_default'])} solid {theme["border"]};
            border-radius: {_px(s['radius_sm'])};
            background: {theme["bg_darker"]};
        }}
        QCheckBox::indicator:checked {{
            background: {theme["accent"]};
            border-color: {theme["accent"]};
        }}
        QGroupBox {{
            color: {theme["text"]};
            border: {_px(s['border_width_default'])} solid {theme["border"]};
            border-radius: {_px(s['radius_lg'])};
            margin-top: {_px(s['groupbox_margin_top'])};
            padding-top: {_px(s['groupbox_padding_top'])};
        }}
        QGroupBox::title {{
            subcontrol-origin: margin;
            left: {_px(s['groupbox_title_left'])};
            padding: 0 {_px(s['groupbox_title_padding_h'])};
        }}
    """


# ── Theme application helpers ───────────────────────────────────────────────


def apply_theme(name: str, app: QApplication | None = None,
                custom_css: str = "") -> str:
    """Resolve, build, and apply a stylesheet for *name*.

    *custom_css* is appended last so it always has highest precedence.  The
    resolved canonical name is broadcast via ``theme_notifier``.
    """
    resolved_name = resolve_theme_name(name)
    theme = get_theme(resolved_name)
    stylesheet = generate_app_stylesheet(theme["colors"]) + "\n" + custom_css
    if app is not None:
        app.setStyleSheet(stylesheet)
    theme_notifier.set_theme(resolved_name)
    return resolved_name


# ── Theme notifier ───────────────────────────────────────────────────────────


class ThemeNotifier(QObject):
    """Emits ``theme_changed`` whenever the active theme is switched.

    Module-level singleton ``theme_notifier`` is created at import time so
    that any consumer can connect without worrying about lifecycle.
    """

    theme_changed = Signal(str)

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self.current_theme: str = "Catppuccin Mocha"

    def set_theme(self, name: str) -> None:
        self.current_theme = name
        self.theme_changed.emit(name)


theme_notifier = ThemeNotifier()


# ── Theme class ─────────────────────────────────────────────────────────────


class Theme:
    """Thin wrapper around a colour dictionary for convenience."""

    def __init__(self, colors: dict[str, str] | None = None):
        self._colors = dict(colors) if colors else dict(DEFAULT_THEME)

    @property
    def colors(self) -> dict[str, str]:
        return self._colors

    def __getitem__(self, key: str) -> str:
        return self._colors[key]

    def get(self, key: str, default: str = "") -> str:
        return self._colors.get(key, default)

    def stylesheet(self) -> str:
        return generate_app_stylesheet(self._colors)
