"""``SnapshotItem``: the screenshot of one story in one theme, compared with its baseline (internal)."""

from __future__ import annotations

from pathlib import Path

import pytest

from pyside6_storybook.checks.rules import RULE_SNAPSHOT
from pyside6_storybook.registry import Story
from pyside6_storybook.testing.story_item import story_report_info
from pyside6_storybook.testing.storybook_item import StorybookItem
from pyside6_storybook_pytest import SESSION_KEY


class SnapshotItem(StorybookItem):
    """Renders one story in one theme and compares a screenshot with its baseline, or skips when the story opts out of the rule.

    Attributes:
        story: The story to check.
        theme: The theme to render it in.
    """

    def __init__(self, *, parent: pytest.Collector, story: Story, theme: str) -> None:
        """Create the item; its node id is ``storybook::<story id>[<theme>-snapshot]``.

        Args:
            parent: The ``storybook`` collector.
            story: The story to check.
            theme: The theme to render it in.
        """
        super().__init__(parent=parent, suffix=f"{story.id}[{theme}-snapshot]")
        self.story = story
        self.theme = theme
        reason = story.checks_ignore.get(RULE_SNAPSHOT)
        if reason is not None:
            # A skip marker, not pytest.skip() in runtest: the story is not rendered, and -rs reports the story's file and line.
            self.add_marker(pytest.mark.skip(reason=f"{RULE_SNAPSHOT} ignored: {reason}"))

    def runtest(self) -> None:
        """Render the story in its theme and compare it with its baseline, or write the baseline with ``--storybook-update-snapshots``."""
        self.config.stash[SESSION_KEY].check_snapshot(self.story, self.theme)

    def reportinfo(self) -> tuple[str | Path, int | None, str]:
        """Return the story function's file and line, and ``story <id> [<theme>-snapshot]``."""
        return story_report_info(self.story, self.path, f"story {self.story.id} [{self.theme}-snapshot]")


__all__ = ["SnapshotItem"]
