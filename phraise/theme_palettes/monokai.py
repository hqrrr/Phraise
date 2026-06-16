# PhrAIse - AI writing assistant
# License: GNU GPLv3
# GitHub: https://github.com/hqrrr/Phraise
# Author: hqrrr
#
# Description: Color palette definitions for the Monokai theme.
"""Monokai dark theme palette.

Source: Wimer Hazenberg's Monokai colour scheme
        https://monokai.pro/
"""

from phraise.theme import DEFAULT_SIZING, FullTheme

colors = {
    "bg": "#272822",
    "bg_darker": "#1e1f1c",
    "surface": "#3e3d32",
    "surface_hover": "#49483e",
    "border": "#75715e",
    "text": "#f8f8f2",
    "text_muted": "#a59f85",
    "text_dim": "#75715e",
    "accent": "#ff5c8a",
    "accent_hover": "#fd971f",
    "red": "#ff4d8d",
    "red_hover": "#ff80ab",
    "orange": "#fd971f",
    "green": "#a6e22e",
    "yellow": "#e6db74",
    "white": "#f8f8f2",
    "grip": "#75715e",
    "ball_border": "#1d1e19",
}

theme: FullTheme = {"colors": colors, "sizing": DEFAULT_SIZING}
