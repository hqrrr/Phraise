"""One Dark Pro dark theme palette.

Source: Atom / VS Code One Dark Pro theme
        https://github.com/Binaryify/OneDark-Pro
"""

from phraise.theme import DEFAULT_SIZING, FullTheme

colors = {
    "bg": "#282c34",
    "bg_darker": "#21252b",
    "surface": "#3e4451",
    "surface_hover": "#4b5363",
    "border": "#3e4451",
    "text": "#abb2bf",
    "text_muted": "#828997",
    "text_dim": "#5c6370",
    "accent": "#61afef",
    "accent_hover": "#528bcc",
    "red": "#e06c75",
    "red_hover": "#be5046",
    "orange": "#d19a66",
    "green": "#98c379",
    "yellow": "#e5c07b",
    "white": "#ffffff",
    "grip": "#4b5363",
}

theme: FullTheme = {"colors": colors, "sizing": DEFAULT_SIZING}
