"""``Story``: a registered story function with its id and controls, and ``StoryOrigin``."""

from __future__ import annotations

import inspect
from collections.abc import Iterable, Mapping
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, NamedTuple

from PySide6.QtWidgets import QWidget

from pyside6_storybook.controls import Control
from pyside6_storybook.registry.story_context import StoryContext, StoryFunction

if TYPE_CHECKING:
    from pyside6_storybook.registry.story_registry import StoryRegistry


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
        component: The groups joined with ``/`` (``"Inputs/Button"`` for ``"Inputs/Button/Default"``), or ``None`` without groups.
        controls: The story's controls, in order.
        args: For a variant, the values it overrides, by control name, as a read-only mapping; empty for any other story.
        variant_of: The base story, for a variant; ``None`` otherwise.
        doc: The function's docstring, or an empty string.
        module: Module the function was defined in.
        qualname: Qualified name of the function. For a callable without one (a ``functools.partial`` or a callable object), the
            module and qualified name of its type.
    """

    __slots__ = (
        "_args",
        "_component",
        "_function",
        "_registry",
        "_variant_of",
        "controls",
        "doc",
        "groups",
        "id",
        "module",
        "name",
        "qualname",
    )

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
        self._component = "/".join(self.groups) or None
        self._args: Mapping[str, Any] = MappingProxyType({})
        self._variant_of: Story | None = None
        self._registry: StoryRegistry | None = None
        self.controls = controls
        self.doc = inspect.getdoc(function) or ""
        self.module = getattr(function, "__module__", None) or type(function).__module__
        self.qualname = getattr(function, "__qualname__", None) or type(function).__qualname__
        self._function = function

    @property
    def component(self) -> str | None:
        """The groups joined with ``/`` (``"Inputs/Button"`` for ``"Inputs/Button/Default"``), or ``None`` without groups."""
        return self._component

    @property
    def args(self) -> Mapping[str, Any]:
        """For a variant, the values it overrides, by control name, as a read-only mapping; empty for any other story."""
        return self._args

    @property
    def variant_of(self) -> Story | None:
        """The base story, for a variant; ``None`` otherwise."""
        return self._variant_of

    @property
    def origin(self) -> StoryOrigin:
        """The module and qualified name the story function was defined in."""
        return StoryOrigin(self.module, self.qualname)

    def default_args(self) -> dict[str, object]:
        """Return the value every control starts with, keyed by control name.

        Each value is the variant's value for the control, or the control's default, passed through the control's ``coerce``, so
        it has the type a story receives. Every call returns new objects.
        """
        return {control.name: control.coerce(self.args.get(control.name, control.default)) for control in self.controls}

    def variant(self, name: str, *, args: Mapping[str, object] | None = None) -> Story:
        """Register a variant of this story: the same function and controls, with other starting values.

        The variant's id is the component plus ``name`` (``"Inputs/Button/Disabled"``), and it comes after this story in the
        registry. Calling this twice with the same name replaces the first variant.

        Args:
            name: The variant's name: not blank, without ``/``, and different from this story's name.
            args: Values that replace control defaults, by control name. Each must be accepted by its control's ``coerce``.

        Returns:
            The registered variant.

        Raises:
            TypeError: If this story is itself a variant.
            RuntimeError: If this story was never registered.
            ValueError: If this story's id has no group, ``name`` is invalid, or ``args`` has an unknown key or an invalid value.
        """
        if self.variant_of is not None:
            raise TypeError(f"{self.id!r} is a variant of {self.variant_of.id!r}; call .variant() on the base story instead")
        if self._registry is None:
            raise RuntimeError(f"Story {self.id!r} is not registered, so it cannot have variants; register it first")
        if self.component is None:
            raise ValueError(
                f"Story {self.id!r} has no component, so it cannot have variants; give it an id with a group, for example 'Button/Default'"
            )
        if not name.strip() or "/" in name:
            raise ValueError(f"Invalid variant name {name!r} for story {self.id!r}: expected a non-blank name without '/'")
        if name == self.name:
            raise ValueError(f"Variant name {name!r} is the name of its base story {self.id!r}; choose another name")
        variant_id = f"{self.component}/{name}"
        controls = {control.name: control for control in self.controls}
        checked: dict[str, object] = {}
        for key, value in (args or {}).items():
            control = controls.get(key)
            if control is None:
                raise ValueError(f"Variant {variant_id!r}: {key!r} is not a control of {self.id!r}; expected one of {sorted(controls)}")
            try:
                checked[key] = control.coerce(value)
            except (TypeError, ValueError) as error:
                raise ValueError(f"Variant {variant_id!r}: invalid value for {key!r}: {error}") from error
        variant = Story(variant_id, self._function, controls=self.controls)
        variant._args = MappingProxyType(checked)
        variant._variant_of = self
        return self._registry.register(variant)

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
