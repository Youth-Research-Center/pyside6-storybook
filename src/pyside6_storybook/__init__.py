"""pyside6-storybook: a Storybook-like component explorer for PySide6."""

from importlib.metadata import PackageNotFoundError, version

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
from pyside6_storybook.registry import Layout, SizePreset, Story, StoryContext, StoryRegistry, default_registry, story

try:
    __version__ = version("pyside6-storybook")
except PackageNotFoundError:
    __version__ = "0+unknown"

__all__ = [
    "BoolControl",
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
    "__version__",
    "default_registry",
    "load_stories",
    "story",
]
