"""The built-in themes: one module per theme definition, plus the ``ThemeProvider`` protocol and ``BuiltinThemeProvider``, which applies them."""

from pyside6_storybook.themes.builtin_theme_provider import BUILTIN_THEME_NAMES, BuiltinThemeProvider
from pyside6_storybook.themes.dark_theme import DARK_THEME, dark_palette
from pyside6_storybook.themes.light_theme import LIGHT_THEME, light_palette
from pyside6_storybook.themes.provider import ThemeProvider
from pyside6_storybook.themes.theme_definition import ThemeDefinition

__all__ = [
    "BUILTIN_THEME_NAMES",
    "DARK_THEME",
    "LIGHT_THEME",
    "BuiltinThemeProvider",
    "ThemeDefinition",
    "ThemeProvider",
    "dark_palette",
    "light_palette",
]
