"""``LoadResult`` and ``LoadError``: what ``load_stories`` returns."""

from __future__ import annotations

from dataclasses import dataclass

from pyside6_storybook.registry import StoryRegistry


@dataclass(frozen=True, slots=True)
class LoadError:
    """A story source that could not be loaded.

    Attributes:
        source: The target as given, or the path of the story file, that failed.
        message: A one-line description of the problem.
        details: The formatted traceback when an exception was raised while importing, otherwise an empty string.
    """

    source: str
    message: str
    details: str = ""


@dataclass(frozen=True, slots=True)
class LoadResult:
    """The outcome of ``load_stories``.

    Attributes:
        registry: The registry the loaded stories registered themselves in (the default registry).
        modules: Names of the story modules that were imported or were already imported, in load order, without duplicates.
        errors: The sources that failed, in load order.
    """

    registry: StoryRegistry
    modules: tuple[str, ...]
    errors: tuple[LoadError, ...]


__all__ = ["LoadError", "LoadResult"]
