"""pyside6-storybook: a Storybook-like component explorer for PySide6."""

from importlib.metadata import PackageNotFoundError, version

from pyside6_storybook.app import run
from pyside6_storybook.controls import (
    BoolControl,
    ChoiceControl,
    ColorControl,
    Control,
    EnumControl,
    FileControl,
    FloatControl,
    IntControl,
    TextControl,
)
from pyside6_storybook.decorators import Decorator
from pyside6_storybook.discovery import LoadError, LoadResult, load_stories
from pyside6_storybook.registry import ActionSink, Layout, SizePreset, Story, StoryContext, StoryRegistry, default_registry, story
from pyside6_storybook.themes import BuiltinThemeProvider, ThemeProvider

try:
    __version__ = version("pyside6-storybook")
except PackageNotFoundError:
    __version__ = "0+unknown"

__all__ = [
    "ActionSink",
    "BoolControl",
    "BuiltinThemeProvider",
    "ChoiceControl",
    "ColorControl",
    "Control",
    "Decorator",
    "EnumControl",
    "FileControl",
    "FloatControl",
    "IntControl",
    "Layout",
    "LoadError",
    "LoadResult",
    "SizePreset",
    "Story",
    "StoryContext",
    "StoryRegistry",
    "TextControl",
    "ThemeProvider",
    "__version__",
    "default_registry",
    "load_stories",
    "run",
    "story",
]
