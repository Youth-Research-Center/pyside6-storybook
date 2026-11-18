"""``StorybookItem``: the base of every item the plugin collects (internal)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from pyside6_storybook.registry.rendering import StoryRenderError
from pyside6_storybook.testing.storybook_session import StorybookFailure

if TYPE_CHECKING:
    from _pytest._code.code import TerminalRepr


class StorybookItem(pytest.Item):
    """A test item under the ``storybook`` collector.

    It carries the ``storybook`` marker and reports a failure caused by a story, a decorator or the theme provider as the text of
    the error, not as a traceback through the plugin.
    """

    def __init__(self, *, parent: pytest.Collector, suffix: str) -> None:
        """Create the item.

        Args:
            parent: The ``storybook`` collector.
            suffix: The item's name, such as ``Inputs/Button/Default[Dark]``; its node id is ``storybook::`` and the suffix.
        """
        super().__init__(name=suffix, parent=parent, nodeid=f"{parent.nodeid}::{suffix}")
        self.add_marker("storybook")

    def repr_failure(self, excinfo: pytest.ExceptionInfo[BaseException], style: object = None) -> str | TerminalRepr:
        """Show a ``StoryRenderError`` or ``StorybookFailure`` as its text; any other error as pytest does."""
        error = excinfo.value
        if isinstance(error, StoryRenderError):
            return f"{error.title}\n\n{error.details}"
        if isinstance(error, StorybookFailure):
            return error.text
        return super().repr_failure(excinfo)


__all__ = ["StorybookItem"]
