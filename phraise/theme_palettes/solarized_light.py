"""Solarized Light theme palette.

Source: Ethan Schoonover's Solarized colour scheme
        https://ethanschoonover.com/solarized/
"""

from phraise.theme import DEFAULT_SIZING, FullTheme

colors = {
    "bg": "#fdf6e3",
    "bg_darker": "#eee8d5",
    "surface": "#eee8d5",
    "surface_hover": "#93a1a1",
    "border": "#93a1a1",
    "text": "#657b83",
    "text_muted": "#586e75",
    "text_dim": "#839496",
    "accent": "#2aa198",
    "accent_hover": "#268bd2",
    "red": "#dc322f",
    "red_hover": "#cb4b16",
    "orange": "#cb4b16",
    "green": "#859900",
    "yellow": "#b58900",
    "white": "#002b36",
    "grip": "#93a1a1",
}

theme: FullTheme = {"colors": colors, "sizing": DEFAULT_SIZING}
