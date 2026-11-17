"""``ContrastItem``: the text contrast of one story in one theme (internal)."""

from __future__ import annotations

from pathlib import Path

import pytest

from pyside6_storybook.checks.rules import RULE_CONTRAST
from pyside6_storybook.registry import Story
from pyside6_storybook.testing.story_item import story_report_info
from pyside6_storybook.testing.storybook_item import StorybookItem
from pyside6_storybook_pytest import SESSION_KEY


class ContrastItem(StorybookItem):
    """Renders one story in one theme and checks the contrast of its text, or skips when the story opts out of the rule.

    Attributes:
        story: The story to check.
        theme: The theme to render it in.
    """

    def __init__(self, *, parent: pytest.Collector, story: Story, theme: str) -> None:
        """Create the item; its node id is ``storybook::<story id>[<theme>-contrast]``.

        Args:
            parent: The ``storybook`` collector.
            story: The story to check.
            theme: The theme to render it in.
        """
        super().__init__(parent=parent, suffix=f"{story.id}[{theme}-contrast]")
        self.story = story
        self.theme = theme
        reason = story.checks_ignore.get(RULE_CONTRAST)
        if reason is not None:
            # A skip marker, not pytest.skip() in runtest: the story is not rendered, and -rs reports the story's file and line.
            self.add_marker(pytest.mark.skip(reason=f"{RULE_CONTRAST} ignored: {reason}"))

    def runtest(self) -> None:
        """Render the story in its theme and fail on every text that is too faint."""
        self.config.stash[SESSION_KEY].check_contrast(self.story, self.theme)

    def reportinfo(self) -> tuple[str | Path, int | None, str]:
        """Return the story function's file and line, and ``story <id> [<theme>-contrast]``."""
        return story_report_info(self.story, self.path, f"story {self.story.id} [{self.theme}-contrast]")


__all__ = ["ContrastItem"]
