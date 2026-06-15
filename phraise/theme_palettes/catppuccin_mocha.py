"""Catppuccin Mocha dark theme palette.

Source: https://catppuccin.com/palette (Mocha flavour)
"""

from phraise.theme import DEFAULT_SIZING, FullTheme

colors = {
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

theme: FullTheme = {"colors": colors, "sizing": DEFAULT_SIZING}
