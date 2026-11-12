"""``Story``: a registered story function with its id and controls, and ``StoryOrigin``."""

from __future__ import annotations

import inspect
from collections.abc import Iterable
from typing import NamedTuple

from PySide6.QtWidgets import QWidget

from pyside6_storybook.controls import Control
from pyside6_storybook.registry.story_context import StoryContext, StoryFunction


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


__all__ = ["Story", "StoryOrigin"]
