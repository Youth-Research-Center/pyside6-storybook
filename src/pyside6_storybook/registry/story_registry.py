"""``StoryRegistry``: an ordered collection of stories, unique by id."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator

from pyside6_storybook.controls import Control
from pyside6_storybook.registry.story_context import StoryFunction
from pyside6_storybook.registry.story_definition import Story


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


__all__ = ["StoryRegistry"]
