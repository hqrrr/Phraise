# PhrAIse - AI writing assistant
# License: GNU GPLv3
# GitHub: https://github.com/hqrrr/Phraise
# Author: hqrrr
#
# Description: Color palette definitions for the Nord Dark theme.
"""Nord dark theme palette.

Source: Arctic Ice Studio's Nord colour palette
        https://www.nordtheme.com/docs/colors-and-palettes
"""

from phraise.theme import DEFAULT_SIZING, FullTheme

colors = {
    "bg": "#2e3440",
    "bg_darker": "#3b4252",
    "surface": "#3b4252",
    "surface_hover": "#434c5e",
    "border": "#4c566a",
    "text": "#d8dee9",
    "text_muted": "#81a1c1",
    "text_dim": "#616e88",
    "accent": "#88c0d0",
    "accent_hover": "#5e81ac",
    "red": "#bf616a",
    "red_hover": "#d08770",
    "orange": "#d08770",
    "green": "#a3be8c",
    "yellow": "#ebcb8b",
    "white": "#eceff4",
    "grip": "#4c566a",
}

theme: FullTheme = {"colors": colors, "sizing": DEFAULT_SIZING}
