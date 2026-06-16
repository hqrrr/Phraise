# PhrAIse - AI writing assistant
# License: GNU GPLv3
# GitHub: https://github.com/hqrrr/Phraise
# Author: hqrrr
#
# Description: Color palette definitions for the GitHub Light theme.
"""GitHub Light theme palette.

Source: GitHub Primer design system
        https://primer.style/foundations/color
"""

from phraise.theme import DEFAULT_SIZING, FullTheme

colors = {
    "bg": "#ffffff",
    "bg_darker": "#f6f8fa",
    "surface": "#f6f8fa",
    "surface_hover": "#eaeef2",
    "border": "#d0d7de",
    "text": "#1f2328",
    "text_muted": "#656d76",
    "text_dim": "#8c959f",
    "accent": "#0969da",
    "accent_hover": "#0550ae",
    "red": "#cf222e",
    "red_hover": "#a40e26",
    "orange": "#e16f24",
    "green": "#1a7f37",
    "yellow": "#9a6700",
    "white": "#ffffff",
    "grip": "#afb8c1",
    "ball_border": "#24292f",
}

theme: FullTheme = {"colors": colors, "sizing": DEFAULT_SIZING}
