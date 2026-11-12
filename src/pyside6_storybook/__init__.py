"""pyside6-storybook: a Storybook-like component explorer for PySide6."""

from importlib.metadata import PackageNotFoundError, version

from pyside6_storybook.controls import BoolControl, ChoiceControl, Control, FloatControl, IntControl, TextControl
from pyside6_storybook.registry import Story, StoryContext, StoryRegistry, default_registry, story

try:
    __version__ = version("pyside6-storybook")
except PackageNotFoundError:
    __version__ = "0+unknown"

__all__ = [
    "BoolControl",
    "ChoiceControl",
    "Control",
    "FloatControl",
    "IntControl",
    "Story",
    "StoryContext",
    "StoryRegistry",
    "TextControl",
    "__version__",
    "default_registry",
    "story",
]
