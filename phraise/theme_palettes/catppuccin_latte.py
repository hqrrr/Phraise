# PhrAIse - AI writing assistant
# License: GNU GPLv3
# GitHub: https://github.com/hqrrr/Phraise
# Author: hqrrr
#
# Description: Color palette definitions for the Catppuccin Latte theme.
"""Catppuccin Latte light theme palette.

Source: https://catppuccin.com/palette (Latte flavour)
"""

from phraise.theme import DEFAULT_SIZING, FullTheme

colors = {
    "bg": "#eff1f5",
    "bg_darker": "#e6e9ef",
    "surface": "#ccd0da",
    "surface_hover": "#c5c9d5",
    "border": "#bcc0cc",
    "text": "#4c4f69",
    "text_muted": "#5c5f77",
    "text_dim": "#8c8fa1",
    "accent": "#8839ef",
    "accent_hover": "#4f66cc",
    "red": "#d20f39",
    "red_hover": "#e64553",
    "orange": "#fe640b",
    "green": "#40a02b",
    "yellow": "#df8e1d",
    "white": "#ffffff",
    "grip": "#9ca0b0",
    "ball_border": "#4c4f69",
}

theme: FullTheme = {"colors": colors, "sizing": DEFAULT_SIZING}
