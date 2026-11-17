"""The story model, one module per type, plus the process-wide ``default_registry`` and the ``@story`` decorator.

``default_registry`` and ``story`` live here, not in a submodule, because ``story`` looks up ``default_registry`` in this
module's namespace when it is called.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping

from pyside6_storybook.controls import Control
from pyside6_storybook.registry.checks_ignore import NO_CHECKS_IGNORED
from pyside6_storybook.registry.layout import Layout
from pyside6_storybook.registry.size_preset import SizePreset
from pyside6_storybook.registry.story_context import ActionSink, Decorator, StoryContext, StoryFunction
from pyside6_storybook.registry.story_definition import Story, StoryOrigin
from pyside6_storybook.registry.story_registry import StoryRegistry

default_registry = StoryRegistry()
"""The process-wide registry that the module-level ``story`` decorator registers into."""


def story(
    id: str,
    *,
    controls: Iterable[Control] = (),
    layout: Layout | str | None = None,
    decorators: Iterable[Decorator] = (),
    checks_ignore: Mapping[str, str] = NO_CHECKS_IGNORED,
) -> Callable[[StoryFunction], Story]:
    """Turn a function into a story registered in ``default_registry``.

    Args:
        id: A ``/``-separated path such as ``"Inputs/Button"``; the last segment is the story's name.
        controls: The story's controls.
        layout: How the gallery places the widget in the preview: a ``Layout``, its string value, or ``None`` for the registry's
            ``default_layout``.
        decorators: Functions that wrap the story's widget, the first one outermost; see ``Decorator``.
        checks_ignore: Rules of the pytest plugin's checks the story opts out of, each with the reason: ``{"focus": "decorative"}``.
            The rules are ``"name"`` and ``"focus"``.

    Returns:
        A decorator returning the registered ``Story``.

    Raises:
        ValueError: If ``layout`` is not valid, or ``checks_ignore`` names an unknown rule or has an empty reason.
        TypeError: If ``checks_ignore`` is not a mapping.
    """
    return default_registry.story(id, controls=controls, layout=layout, decorators=decorators, checks_ignore=checks_ignore)


__all__ = [
    "ActionSink",
    "Decorator",
    "Layout",
    "SizePreset",
    "Story",
    "StoryContext",
    "StoryFunction",
    "StoryOrigin",
    "StoryRegistry",
    "default_registry",
    "story",
]
