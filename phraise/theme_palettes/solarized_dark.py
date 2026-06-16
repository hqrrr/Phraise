# PhrAIse - AI writing assistant
# License: GNU GPLv3
# GitHub: https://github.com/hqrrr/Phraise
# Author: hqrrr
#
# Description: Color palette definitions for the Solarized Dark theme.
"""Solarized Dark theme palette.

Source: Ethan Schoonover's Solarized colour scheme
        https://ethanschoonover.com/solarized/
"""

from phraise.theme import DEFAULT_SIZING, FullTheme

colors = {
    "bg": "#002b36",
    "bg_darker": "#073642",
    "surface": "#073642",
    "surface_hover": "#586e75",
    "border": "#586e75",
    "text": "#839496",
    "text_muted": "#93a1a1",
    "text_dim": "#657b83",
    "accent": "#2aa198",
    "accent_hover": "#3aa0e0",
    "red": "#b71c1c",
    "red_hover": "#cb4b16",
    "orange": "#cb4b16",
    "green": "#859900",
    "yellow": "#b58900",
    "white": "#fdf6e3",
    "grip": "#586e75",
    "ball_border": "#001f27",
}

theme: FullTheme = {"colors": colors, "sizing": DEFAULT_SIZING}
