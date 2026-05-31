"""Centralized CSS theme system for PhrAIse.

All color constants, style generators, and the Theme class live here.
No other module should contain hardcoded hex color values.
"""

from typing import Any

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


# ── Style-sheet generators ──────────────────────────────────────────────────
#
# Every generator receives *theme* (a colour dict) as the first argument and
# returns a Qt style-sheet string.  Other parameters tweak the appearance.


def btn_style(theme: dict, hover_color: str | None = None) -> str:
    """Generic transparent push-button.

    *hover_color* may be a raw hex string (``"#f38ba8"``) or a theme key
    (``"accent"``).  Defaults to ``"surface_hover"``.
    """
    hc = _resolve_color(theme, hover_color) if hover_color else theme["surface_hover"]
    return (
        f"QPushButton {{ background: transparent; color: {theme['text_muted']}; "
        f"border: none; font-size: 14px; padding: 2px 6px; border-radius: 4px; }}"
        f"QPushButton:hover {{ background: {hc}; color: {theme['text']}; }}"
    )


def action_btn_style(theme: dict, bg: str) -> str:
    """Small action button with a solid background.

    *bg* may be a raw hex or a theme key.  Hover is always the accent-hover
    colour.
    """
    bg_color = _resolve_color(theme, bg)
    return (
        f"QPushButton {{ background: {bg_color}; color: {theme['text']}; "
        f"border: none; border-radius: 6px; font-size: 11px; font-weight: 500; "
        f"padding: 4px 10px; }}"
        f"QPushButton:hover {{ background: {theme['accent_hover']}; }}"
    )


def style_btn_style(theme: dict, active: bool) -> str:
    """Style-selector toggle button."""
    bg = theme["accent"] if active else theme["surface"]
    color = theme["white"] if active else theme["text_muted"]
    return (
        f"QPushButton {{ background: {bg}; color: {color}; border: none; "
        f"border-radius: 6px; font-size: 12px; font-weight: 500; "
        f"padding: 4px 10px; }}"
        f"QPushButton:hover {{ background: {theme['accent_hover']}; "
        f"color: {theme['white']}; }}"
    )


def combo_style(theme: dict) -> str:
    """QComboBox style."""
    return (
        f"QComboBox {{ background: {theme['surface']}; color: {theme['text']}; "
        f"border: 1px solid {theme['border']}; border-radius: 6px; "
        f"padding: 4px 24px 4px 10px; font-size: 12px; }}"
        f"QComboBox:hover {{ border-color: {theme['accent']}; }}"
        f"QComboBox::drop-down {{ subcontrol-origin: padding; subcontrol-position: top right; "
        f"width: 22px; border-left: 1px solid {theme['border']}; "
        f"border-top-right-radius: 6px; border-bottom-right-radius: 6px; }}"
        f"QComboBox::down-arrow {{ width: 10px; height: 10px; }}"
        f"QComboBox QAbstractItemView {{ background: {theme['surface']}; "
        f"color: {theme['text']}; selection-background-color: {theme['accent']}; "
        f"border: 1px solid {theme['border']}; border-radius: 4px; }}"
    )


def tab_style(theme: dict) -> str:
    """QTabWidget style."""
    return (
        f"QTabWidget::pane {{ border: none; background: {theme['bg']}; }}"
        f"QTabBar::tab {{ background: {theme['surface']}; "
        f"color: {theme['text_muted']}; padding: 8px 20px; "
        f"border: none; font-size: 13px; font-weight: 500; }}"
        f"QTabBar::tab:selected {{ background: {theme['accent']}; "
        f"color: {theme['white']}; }}"
        f"QTabBar::tab:hover:!selected {{ background: {theme['surface_hover']}; }}"
    )


def entry_style(theme: dict) -> str:
    """QLineEdit style."""
    return (
        f"QLineEdit {{ background: {theme['bg_darker']}; color: {theme['text']}; "
        f"border: 1px solid {theme['border']}; border-radius: 6px; "
        f"padding: 6px 10px; font-size: 12px; }}"
        f"QLineEdit:focus {{ border-color: {theme['accent']}; }}"
    )


def text_edit_style(theme: dict) -> str:
    """QTextEdit style."""
    return (
        f"QTextEdit {{ background: {theme['bg_darker']}; color: {theme['text']}; "
        f"border: 1px solid {theme['border']}; border-radius: 6px; "
        f"font-size: 12px; padding: 4px; }}"
    )


def card_style(theme: dict, radius: int = 6) -> str:
    """Card QFrame style.  *radius* defaults to 6 px."""
    return (
        f"QFrame {{ background: {theme['surface']}; "
        f"border: 1px solid {theme['border']}; border-radius: {radius}px; }}"
    )


def toast_style(theme: dict) -> str:
    """Toast notification QLabel style."""
    return (
        f"QLabel {{ background: {theme['surface_hover']}; color: {theme['text']}; "
        f"border-radius: 8px; padding: 4px 12px; }}"
    )


def titlebar_style(theme: dict, radius: int) -> str:
    """Title-bar widget style (uses top border radii)."""
    return (
        f"background: {theme['bg_darker']}; "
        f"border-top-left-radius: {radius}px; "
        f"border-top-right-radius: {radius}px;"
    )


def bottom_bar_style(theme: dict, radius: int) -> str:
    """Bottom-bar widget style (uses bottom border radii)."""
    return (
        f"background: {theme['bg_darker']}; "
        f"border-bottom-left-radius: {radius}px; "
        f"border-bottom-right-radius: {radius}px;"
    )


def scroll_area_style(theme: dict) -> str:
    """QScrollArea style."""
    return "QScrollArea { border: none; background: transparent; }"


def label_style(theme: dict, color_key: str, extra: str = "") -> str:
    """Generic label style.

    *color_key* is a theme key (e.g. ``"text"``, ``"text_muted"``).
    *extra* is any additional CSS appended to the rule.
    """
    color = theme.get(color_key, color_key)
    base = f"color: {color}; background: transparent;"
    if extra:
        return f"{base} {extra}"
    return base


def separator_style(theme: dict) -> str:
    """QFrame HLine separator colour."""
    return f"color: {theme['border']};"


# ── Application-level stylesheet ────────────────────────────────────────────


def generate_app_stylesheet(theme: dict) -> str:
    """Return a QApplication-level stylesheet built from *theme*."""
    return f"""
        QWidget {{
            background-color: {theme["bg"]};
            color: {theme["text"]};
        }}
        QMenu {{
            background-color: {theme["surface"]};
            color: {theme["text"]};
            border: 1px solid {theme["border"]};
            border-radius: 4px;
            padding: 4px;
        }}
        QMenu::item {{
            padding: 6px 24px;
            border-radius: 4px;
        }}
        QMenu::item:selected {{
            background-color: {theme["accent"]};
        }}
        QToolTip {{
            background-color: {theme["surface"]};
            color: {theme["text"]};
            border: 1px solid {theme["border"]};
            border-radius: 4px;
            padding: 4px 8px;
        }}
        QScrollBar:vertical {{
            background: {theme["bg"]};
            width: 8px;
            border-radius: 4px;
        }}
        QScrollBar::handle:vertical {{
            background: {theme["surface_hover"]};
            border-radius: 4px;
            min-height: 20px;
        }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
            height: 0px;
        }}
        QScrollBar:horizontal {{
            background: {theme["bg"]};
            height: 8px;
            border-radius: 4px;
        }}
        QScrollBar::handle:horizontal {{
            background: {theme["surface_hover"]};
            border-radius: 4px;
            min-width: 20px;
        }}
        QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
            width: 0px;
        }}
        QCheckBox {{
            color: {theme["text"]};
        }}
        QCheckBox::indicator {{
            width: 16px;
            height: 16px;
            border: 1px solid {theme["border"]};
            border-radius: 3px;
            background: {theme["bg_darker"]};
        }}
        QCheckBox::indicator:checked {{
            background: {theme["accent"]};
            border-color: {theme["accent"]};
        }}
        QGroupBox {{
            color: {theme["text"]};
            border: 1px solid {theme["border"]};
            border-radius: 6px;
            margin-top: 8px;
            padding-top: 16px;
        }}
        QGroupBox::title {{
            subcontrol-origin: margin;
            left: 10px;
            padding: 0 4px;
        }}
    """


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
