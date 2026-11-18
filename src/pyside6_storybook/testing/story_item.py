"""``StoryItem``: one story rendered in one theme (internal). The checks of later milestones add more item kinds beside it."""

from __future__ import annotations

import inspect
from pathlib import Path

import pytest

from pyside6_storybook.registry import Story
from pyside6_storybook.testing.storybook_item import StorybookItem
from pyside6_storybook_pytest import SESSION_KEY


class StoryItem(StorybookItem):
    """Renders one story in one theme and fails on an error in the story, a non-widget result, or an unexcused Qt warning.

    Attributes:
        story: The story to render.
        theme: The theme to render it in.
    """

    def __init__(self, *, parent: pytest.Collector, story: Story, theme: str) -> None:
        """Create the item; its node id is ``storybook::<story id>[<theme>]``.

        Args:
            parent: The ``storybook`` collector.
            story: The story to render.
            theme: The theme to render it in.
        """
        super().__init__(parent=parent, suffix=f"{story.id}[{theme}]")
        self.story = story
        self.theme = theme

    def runtest(self) -> None:
        """Render the story in its theme and delete it again."""
        self.config.stash[SESSION_KEY].check_story(self.story, self.theme)

    def reportinfo(self) -> tuple[str | Path, int | None, str]:
        """Return the story function's file and line, and ``story <id> [<theme>]``."""
        function = inspect.unwrap(self.story.function)
        try:
            file = inspect.getsourcefile(function)
            line: int | None = inspect.getsourcelines(function)[1] - 1
        except (TypeError, OSError):
            file, line = None, None
        return file or self.path, line, f"story {self.story.id} [{self.theme}]"


__all__ = ["StoryItem"]
