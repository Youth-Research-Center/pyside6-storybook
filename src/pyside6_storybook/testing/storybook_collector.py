"""``StorybookCollector``: the collector node that holds every storybook item (internal)."""

from __future__ import annotations

import pytest

from pyside6_storybook_pytest import SESSION_KEY

COLLECTOR_NAME = "storybook"
"""The collector's name and node id. Each item's node id is ``storybook::<name>``."""


class StorybookCollector(pytest.Collector):
    """The parent of the story, load-error and configuration items; a child of the pytest session with the node id ``storybook``."""

    def collect(self) -> list[pytest.Item]:
        """Return the items: one per story and theme, one per load error, or a single configuration item."""
        return self.config.stash[SESSION_KEY].collect_items(self)

    @classmethod
    def attach(cls, session: pytest.Session) -> StorybookCollector:
        """Create the collector under the pytest session.

        Args:
            session: The pytest session.

        Returns:
            The collector, with the node id ``storybook``, so the items' ids (``storybook::<id>[<theme>]``) parse as ``--lf`` expects.
        """
        return cls.from_parent(session, name=COLLECTOR_NAME, nodeid=COLLECTOR_NAME)


__all__ = ["COLLECTOR_NAME", "StorybookCollector"]
