"""The implementation of the ``render_story`` fixture (internal)."""

from __future__ import annotations

from collections.abc import Callable, Generator, Mapping
from contextlib import contextmanager

import pytest
from PySide6.QtWidgets import QWidget

from pyside6_storybook.registry import Story
from pyside6_storybook.testing.storybook_session import RenderedHost, StorybookSession

RenderStory = Callable[..., QWidget]
"""``render_story(story_id, *, args=None, theme=None)``: render a story and return its widget, shown."""

NEEDS_PYTEST_QT = "render_story needs pytest-qt: install pyside6-storybook[pytest]"


@contextmanager
def story_renderer(request: pytest.FixtureRequest) -> Generator[RenderStory]:
    """Provide the ``render_story`` function for one test, and delete what it rendered afterwards.

    Args:
        request: The fixture request of the test.

    Yields:
        The function that renders a story by id.

    Raises:
        pytest.UsageError: If pytest-qt, whose ``qapp`` fixture creates the ``QApplication``, is not installed or is disabled, or the
            sources are not usable (see ``StorybookSession.from_config``).
    """
    try:
        request.getfixturevalue("qapp")
    except pytest.FixtureLookupError as error:
        raise pytest.UsageError(NEEDS_PYTEST_QT) from error
    session = StorybookSession.for_config(request.config)
    session.prepare()
    rendered: list[RenderedHost] = []
    themed = False

    def render_story(story_id: str, *, args: Mapping[str, object] | None = None, theme: str | None = None) -> QWidget:
        nonlocal themed
        story = session.get_story(story_id)
        values = _coerced(story, args or {})
        if theme is not None:
            themed = True
            session.set_theme(theme)
        host = session.render(story, args=values)
        rendered.append(host)
        return host.widget

    try:
        yield render_story
    finally:
        for host in reversed(rendered):
            host.dispose()
        if themed:
            session.release_provider()


def _coerced(story: Story, args: Mapping[str, object]) -> dict[str, object]:
    controls = {control.name: control for control in story.controls}
    unknown = [name for name in args if name not in controls]
    if unknown:
        names = ", ".join(map(repr, unknown))
        raise KeyError(f"story {story.id!r} has no control named {names}; its controls are: {', '.join(controls) or 'none'}")
    return {name: controls[name].coerce(value) for name, value in args.items()}


__all__ = ["NEEDS_PYTEST_QT", "RenderStory", "story_renderer"]
