"""``LoadResult`` and ``LoadError``: what ``load_stories`` returns."""

from __future__ import annotations

from dataclasses import dataclass, field

from pyside6_storybook.registry import StoryRegistry


@dataclass(frozen=True, slots=True)
class LoadError:
    """A story source that could not be loaded.

    Attributes:
        source: The target as given, or the path of the story file, that failed.
        message: A one-line description of the problem.
        details: The formatted traceback when an exception was raised while importing, otherwise an empty string.
        target_error: ``True`` when the target itself is wrong (no file, folder or module has that name, or it is a file that is
            not Python), as opposed to a story module that failed while importing.
    """

    source: str
    message: str
    details: str = ""
    target_error: bool = field(default=False, kw_only=True)


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
