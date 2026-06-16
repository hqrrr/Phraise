# PhrAIse - AI writing assistant
# License: GNU GPLv3
# GitHub: https://github.com/hqrrr/Phraise
# Author: hqrrr
#
# Description: Color palette definitions for the One Light theme.
"""One Light theme palette.

Source: Atom One Light syntax theme
        https://github.com/atom/one-light-syntax
"""

from phraise.theme import DEFAULT_SIZING, FullTheme

colors = {
    "bg": "#fafafa",
    "bg_darker": "#f0f0f0",
    "surface": "#e5e5e6",
    "surface_hover": "#dbdbdc",
    "border": "#c2c2c3",
    "text": "#383a42",
    "text_muted": "#696c77",
    "text_dim": "#a0a1a7",
    "accent": "#2563eb",
    "accent_hover": "#016a9e",
    "red": "#d32f2f",
    "red_hover": "#ca1243",
    "orange": "#d19a66",
    "green": "#50a14f",
    "yellow": "#c18401",
    "white": "#ffffff",
    "grip": "#c2c2c3",
    "ball_border": "#383a42",
}

theme: FullTheme = {"colors": colors, "sizing": DEFAULT_SIZING}
