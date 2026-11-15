"""``StoryRegistry``: an ordered collection of stories, unique by id."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator

from pyside6_storybook.controls import Control
from pyside6_storybook.registry.layout import Layout, coerce_layout
from pyside6_storybook.registry.story_context import StoryFunction
from pyside6_storybook.registry.story_definition import Story


class StoryRegistry:
    """An ordered collection of stories, unique by id."""

    def __init__(self) -> None:
        self._stories: dict[str, Story] = {}
        self._default_layout = Layout.PADDED

    @property
    def default_layout(self) -> Layout:
        """The layout of every story that declares none; ``Layout.PADDED`` until set.

        Assigning a ``Layout`` or its string value changes it, before or after stories register; anything else raises ``ValueError``.
        """
        return self._default_layout

    @default_layout.setter
    def default_layout(self, value: Layout | str) -> None:
        self._default_layout = Layout(value)

    def register(self, story: Story) -> Story:
        """Add a story.

        Registering an id again from the same module and qualified name (a module imported twice or reloaded) replaces the
        earlier story and keeps its position. The story remembers this registry, so that ``Story.variant`` can register variants
        here.

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
        story._registry = self
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

    def story(self, id: str, *, controls: Iterable[Control] = (), layout: Layout | str | None = None) -> Callable[[StoryFunction], Story]:
        """Return a decorator that turns a function into a story registered here.

        Args:
            id: The story id, see ``Story``.
            controls: The story's controls.
            layout: The story's layout: a ``Layout``, its string value, or ``None`` for ``default_layout``.

        Returns:
            A decorator returning the registered ``Story``.

        Raises:
            ValueError: If ``layout`` is not valid; raised here, when the decorator is created.
        """
        story_layout = coerce_layout(layout)

        def decorator(function: StoryFunction) -> Story:
            return self.register(Story(id, function, controls=controls, layout=story_layout))

        return decorator

    def __iter__(self) -> Iterator[Story]:
        return iter(list(self._stories.values()))

    def __len__(self) -> int:
        return len(self._stories)

    def __contains__(self, story_id: object) -> bool:
        return story_id in self._stories


__all__ = ["StoryRegistry"]
