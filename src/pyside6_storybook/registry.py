"""The story model: ``Story``, ``StoryContext``, ``StoryRegistry`` and the ``@story`` decorator."""

from __future__ import annotations

import inspect
from collections.abc import Callable, Iterable, Iterator, Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import NamedTuple

from PySide6.QtWidgets import QWidget

from pyside6_storybook.controls import Control


@dataclass(frozen=True, kw_only=True)
class StoryContext:
    """Everything a story function receives.

    Attributes:
        args: The current control values by control name. Stored as a read-only copy.
        theme: Name of the active theme.
    """

    args: Mapping[str, object]
    theme: str = "Light"

    def __post_init__(self) -> None:
        object.__setattr__(self, "args", MappingProxyType(dict(self.args)))


StoryFunction = Callable[[StoryContext], QWidget]
"""A story function: builds one widget in one state from a ``StoryContext``."""


class StoryOrigin(NamedTuple):
    """Where a story function was defined."""

    module: str
    qualname: str

    def __str__(self) -> str:
        return f"{self.module}.{self.qualname}"


class Story:
    """A registered story: a function that builds one widget, plus its id and controls.

    ``Story`` objects are what ``@story`` returns. They are callable, so ``my_story(ctx)`` still builds the widget.

    Attributes:
        id: The unique ``/``-separated path, for example ``"Inputs/Button"``.
        name: The last segment of ``id``.
        groups: The segments of ``id`` before the name.
        controls: The story's controls, in order.
        doc: The function's docstring, or an empty string.
        module: Module the function was defined in.
        qualname: Qualified name of the function.
    """

    __slots__ = ("_function", "controls", "doc", "groups", "id", "module", "name", "qualname")

    def __init__(self, id: str, function: StoryFunction, *, controls: Iterable[Control] = ()) -> None:
        """Create a story.

        Args:
            id: A non-empty ``/``-separated path without empty segments.
            function: The function that builds the widget.
            controls: The story's controls.

        Raises:
            ValueError: If ``id`` is empty or has an empty segment, or two controls share a name.
            TypeError: If an item of ``controls`` is not a control.
        """
        segments = id.split("/")
        if any(not segment.strip() for segment in segments):
            raise ValueError(f"Invalid story id {id!r}: expected a non-empty '/'-separated path without empty segments")
        controls = tuple(controls)
        names: set[str] = set()
        for control in controls:
            if not isinstance(control, Control):
                raise TypeError(f"Story {id!r}: {control!r} is not a control")
            if control.name in names:
                raise ValueError(f"Story {id!r} has more than one control named {control.name!r}")
            names.add(control.name)
        self.id = id
        self.name = segments[-1]
        self.groups = tuple(segments[:-1])
        self.controls = controls
        self.doc = inspect.getdoc(function) or ""
        self.module = function.__module__
        self.qualname = function.__qualname__
        self._function = function

    @property
    def origin(self) -> StoryOrigin:
        """The module and qualified name the story function was defined in."""
        return StoryOrigin(self.module, self.qualname)

    def default_args(self) -> dict[str, object]:
        """Return the default value of every control, keyed by control name."""
        return {control.name: control.default for control in self.controls}

    def __call__(self, ctx: StoryContext) -> QWidget:
        """Build the story's widget.

        Args:
            ctx: The context to pass to the story function.

        Returns:
            Whatever the story function returns.
        """
        return self._function(ctx)

    def __repr__(self) -> str:
        return f"Story(id={self.id!r}, origin={self.origin})"


class StoryRegistry:
    """An ordered collection of stories, unique by id."""

    def __init__(self) -> None:
        self._stories: dict[str, Story] = {}

    def register(self, story: Story) -> Story:
        """Add a story.

        Registering an id again from the same module and qualified name (a module imported twice or reloaded) replaces the
        earlier story and keeps its position.

        Args:
            story: The story to add.

        Returns:
            ``story``.

        Raises:
            ValueError: If the id is already registered by a different function.
        """
        existing = self._stories.get(story.id)
        if existing is not None and existing.origin != story.origin:
            raise ValueError(f"Story id {story.id!r} is already registered by {existing.origin}; cannot register it again from {story.origin}")
        self._stories[story.id] = story
        return story

    def get(self, story_id: str) -> Story:
        """Return the story with the given id.

        Args:
            story_id: The id to look up.

        Returns:
            The story.

        Raises:
            KeyError: If no story has that id.
        """
        return self._stories[story_id]

    def ids(self) -> list[str]:
        """Return every story id in registration order."""
        return list(self._stories)

    def story(self, id: str, *, controls: Iterable[Control] = ()) -> Callable[[StoryFunction], Story]:
        """Return a decorator that turns a function into a story registered here.

        Args:
            id: The story id, see ``Story``.
            controls: The story's controls.

        Returns:
            A decorator returning the registered ``Story``.
        """

        def decorator(function: StoryFunction) -> Story:
            return self.register(Story(id, function, controls=controls))

        return decorator

    def __iter__(self) -> Iterator[Story]:
        return iter(list(self._stories.values()))

    def __len__(self) -> int:
        return len(self._stories)

    def __contains__(self, story_id: object) -> bool:
        return story_id in self._stories


default_registry = StoryRegistry()
"""The process-wide registry that the module-level ``story`` decorator registers into."""


def story(id: str, *, controls: Iterable[Control] = ()) -> Callable[[StoryFunction], Story]:
    """Turn a function into a story registered in ``default_registry``.

    Args:
        id: A ``/``-separated path such as ``"Inputs/Button"``; the last segment is the story's name.
        controls: The story's controls.

    Returns:
        A decorator returning the registered ``Story``.
    """
    return default_registry.story(id, controls=controls)


__all__ = [
    "Story",
    "StoryContext",
    "StoryFunction",
    "StoryRegistry",
    "default_registry",
    "story",
]
