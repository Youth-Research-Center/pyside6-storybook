"""Built-in story decorators: functions that wrap a story's widget, passed to ``@story(decorators=[...])``."""

from pyside6_storybook.decorators.fixed_size import fixed_size
from pyside6_storybook.decorators.frame import frame
from pyside6_storybook.decorators.padding import padding
from pyside6_storybook.registry.story_context import Decorator

__all__ = ["Decorator", "fixed_size", "frame", "padding"]
