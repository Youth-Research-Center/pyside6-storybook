"""``A11yItem``: one accessibility rule checked on one story (internal)."""

from __future__ import annotations

from pathlib import Path

import pytest

from pyside6_storybook.registry import Story
from pyside6_storybook.testing.story_item import story_report_info
from pyside6_storybook.testing.storybook_item import StorybookItem
from pyside6_storybook_pytest import SESSION_KEY


class A11yItem(StorybookItem):
    """Renders one story and runs one accessibility rule on it, or skips when the story opts out of the rule.

    Attributes:
        story: The story to check.
        rule: The rule, ``"name"`` or ``"focus"``.
    """

    def __init__(self, *, parent: pytest.Collector, story: Story, rule: str) -> None:
        """Create the item; its node id is ``storybook::<story id>[a11y-<rule>]``.

        Args:
            parent: The ``storybook`` collector.
            story: The story to check.
            rule: The rule to check.
        """
        super().__init__(parent=parent, suffix=f"{story.id}[a11y-{rule}]")
        self.story = story
        self.rule = rule

    def runtest(self) -> None:
        """Skip with the story's reason when it ignores the rule; otherwise render it and fail on every issue the rule finds."""
        reason = self.story.checks_ignore.get(self.rule)
        if reason is not None:
            pytest.skip(f"{self.rule} ignored: {reason}")
        self.config.stash[SESSION_KEY].check_accessibility(self.story, self.rule)

    def reportinfo(self) -> tuple[str | Path, int | None, str]:
        """Return the story function's file and line, and ``story <id> [a11y-<rule>]``."""
        return story_report_info(self.story, self.path, f"story {self.story.id} [a11y-{self.rule}]")


__all__ = ["A11yItem"]
