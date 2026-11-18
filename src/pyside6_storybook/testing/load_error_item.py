"""``StoryLoadErrorItem`` and ``ConfigurationItem``: the items that fail for a story source or the plugin's configuration (internal)."""

from __future__ import annotations

import pytest

from pyside6_storybook.discovery import LoadError
from pyside6_storybook.testing.storybook_item import StorybookItem
from pyside6_storybook.testing.storybook_session import StorybookFailure


class StoryLoadErrorItem(StorybookItem):
    """Fails with the message and traceback of a story source that could not be loaded, so an import error is a failing test.

    Attributes:
        error: The load error.
    """

    def __init__(self, *, parent: pytest.Collector, error: LoadError) -> None:
        """Create the item; its node id is ``storybook::load-error[<source>]``.

        Args:
            parent: The ``storybook`` collector.
            error: The load error.
        """
        super().__init__(parent=parent, suffix=f"load-error[{error.source}]")
        self.error = error

    def runtest(self) -> None:
        """Fail with the error's message and details."""
        text = self.error.message if not self.error.details else f"{self.error.message}\n\n{self.error.details}"
        raise StorybookFailure(text)

    def reportinfo(self) -> tuple[str, None, str]:
        """Return the failing source."""
        return str(self.path), None, f"load error {self.error.source}"


class ConfigurationItem(StorybookItem):
    """The single item of a run whose theme provider or themes cannot be used, or that found no stories; it fails with the reason.

    Attributes:
        message: Why the plugin cannot collect story items.
    """

    def __init__(self, *, parent: pytest.Collector, message: str) -> None:
        """Create the item; its node id is ``storybook::configuration``.

        Args:
            parent: The ``storybook`` collector.
            message: Why the plugin cannot collect story items.
        """
        super().__init__(parent=parent, suffix="configuration")
        self.message = message

    def runtest(self) -> None:
        """Fail with the reason."""
        raise StorybookFailure(self.message)

    def reportinfo(self) -> tuple[str, None, str]:
        """Return the project root and ``storybook configuration``."""
        return str(self.path), None, "storybook configuration"


__all__ = ["ConfigurationItem", "StoryLoadErrorItem"]
