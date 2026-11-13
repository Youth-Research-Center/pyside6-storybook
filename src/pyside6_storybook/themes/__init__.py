"""The built-in themes: one module per theme definition, plus ``BuiltinThemes``, which applies them."""

from pyside6_storybook.themes.builtin_themes import BUILTIN_THEME_NAMES, BuiltinThemes
from pyside6_storybook.themes.dark_theme import DARK_THEME, dark_palette
from pyside6_storybook.themes.light_theme import LIGHT_THEME, light_palette
from pyside6_storybook.themes.theme_definition import ThemeDefinition

__all__ = [
    "BUILTIN_THEME_NAMES",
    "DARK_THEME",
    "LIGHT_THEME",
    "BuiltinThemes",
    "ThemeDefinition",
    "dark_palette",
    "light_palette",
]
