"""``render_story``: build a story's widget and wrap it in its decorators, or raise a ``StoryRenderError`` that says what failed."""

from __future__ import annotations

import traceback
from dataclasses import dataclass
from pathlib import Path
from types import TracebackType
from typing import TYPE_CHECKING

import shiboken6
from PySide6.QtWidgets import QApplication, QWidget

from pyside6_storybook.registry.story_context import StoryContext

if TYPE_CHECKING:
    from pyside6_storybook.registry.story_definition import Story
    from pyside6_storybook.registry.story_registry import StoryRegistry

_PACKAGE_FOLDER = Path(__file__).resolve().parents[1]
"""The ``pyside6_storybook`` package folder: frames from files below it are library code, trimmed from story tracebacks."""
_NON_WIDGET_DETAILS = "A story function must return the widget it builds."
_DECORATOR_NON_WIDGET_DETAILS = "A decorator must return a QWidget: the widget it received, or a wrapper that contains it."
_DECORATOR_DROPPED_DETAILS = "A decorator must return the widget it received, or a wrapper that contains it as a descendant."
_DECORATOR_UNWRAPPED_DETAILS = (
    "A decorator must keep the widget it received, which holds the decorations applied before it: return it, or a wrapper that "
    "contains it as a descendant."
)


@dataclass(frozen=True, slots=True)
class RenderedStory:
    """A story's widget and what to show for it.

    Attributes:
        widget: What the story function returned, undecorated.
        root: The outermost widget after every decorator, to place in the preview. It is ``widget`` itself without decorators or when
            every decorator returned it.
    """

    widget: QWidget
    root: QWidget


class StoryRenderError(Exception):
    """A story or one of its decorators failed.

    Attributes:
        title: One line for the error panel, naming the story and what failed.
        details: Longer text for the error panel: the traceback starting at the failing user code.
    """

    def __init__(self, title: str, details: str) -> None:
        """Create the error.

        Args:
            title: One line for the error panel.
            details: The traceback or an explanation.
        """
        super().__init__(title)
        self.title = title
        self.details = details


def render_story(story: Story, ctx: StoryContext, *, registry: StoryRegistry) -> RenderedStory:
    """Build ``story``'s widget and wrap it in the story's decorators and then the registry's.

    The first decorator of each list is the outermost. The story's own decorators wrap the widget, and the registry's wrap that.

    Args:
        story: The story to render.
        ctx: The context passed to the story function and to every decorator.
        registry: The registry whose ``decorators`` wrap the story's own.

    Returns:
        The undecorated widget and the outermost widget.

    Raises:
        StoryRenderError: If the story or a decorator raises, the story does not return a ``QWidget``, or a decorator does not
            return a ``QWidget`` that is or contains both the story's widget and the widget the decorator received. The original
            error, if any, is the ``__cause__``. The story's widget and every widget built during the render have been hidden and
            scheduled for deletion; other widgets that existed before the render are left alone.
    """
    existing = _widget_addresses(QApplication.allWidgets())
    try:
        widget = story(ctx)
    except Exception as error:  # stories are user code: any error becomes a StoryRenderError for the error panel
        raise StoryRenderError(f"{story.id} raised {type(error).__name__}: {error}", _story_traceback(error)) from error
    if not isinstance(widget, QWidget):
        raise StoryRenderError(f"{story.id} returned {widget!r}, expected a QWidget", _NON_WIDGET_DETAILS)
    current = widget
    # Applying the last decorator first makes the first one the outermost.
    for decorator in (*reversed(story.decorators), *reversed(registry.decorators)):
        try:
            result = decorator(current, ctx)
        except Exception as error:  # decorators are user code too
            _discard(widget, current, existing=existing)
            title = f"{story.id}: decorator {decorator!r} raised {type(error).__name__}: {error}"
            raise StoryRenderError(title, _story_traceback(error)) from error
        if not isinstance(result, QWidget):
            _discard(widget, current, existing=existing)
            title = f"{story.id}: decorator {decorator!r} returned {result!r}, expected a QWidget"
            raise StoryRenderError(title, _DECORATOR_NON_WIDGET_DETAILS)
        if result is not widget and not result.isAncestorOf(widget):
            _discard(widget, current, result, existing=existing)
            title = f"{story.id}: decorator {decorator!r} returned a widget that does not contain the story's widget"
            raise StoryRenderError(title, _DECORATOR_DROPPED_DETAILS)
        if result is not current and not result.isAncestorOf(current):
            _discard(widget, current, result, existing=existing)
            title = f"{story.id}: decorator {decorator!r} returned a widget that does not contain the widget it received"
            raise StoryRenderError(title, _DECORATOR_UNWRAPPED_DETAILS)
        current = result
    return RenderedStory(widget=widget, root=current)


def _discard(story_widget: QWidget, *others: QWidget, existing: frozenset[int]) -> None:
    """Hide and delete the widgets of a failed render, together with the wrappers a decorator put them in.

    The story's widget is always deleted: the gallery owns what a story returns, as it does after a successful render. Any other
    widget is deleted only if it was created during the render. A deleted widget takes its topmost ancestor that was also created
    during the render with it, so a wrapper a decorator built is deleted too, but a widget that existed before the render (an
    application window a decorator reparented into, or the parent the story gave its widget) is never touched.
    """
    for widget in (story_widget, *others):
        if not shiboken6.isValid(widget) or (widget is not story_widget and _widget_address(widget) in existing):
            continue
        top = widget
        while True:
            parent = top.parentWidget()
            if parent is None or _widget_address(parent) in existing:
                break
            top = parent
        top.hide()
        top.deleteLater()


def _widget_address(widget: QWidget) -> int:
    """Identify a widget by its C++ object, which outlives any one Python wrapper."""
    return shiboken6.getCppPointer(widget)[0]


def _widget_addresses(widgets: list[QWidget]) -> frozenset[int]:
    return frozenset(_widget_address(widget) for widget in widgets)


def _story_traceback(error: BaseException) -> str:
    """Format ``error``'s traceback starting at the user's own code, without the library frames that called it."""
    frames: TracebackType | None = error.__traceback__
    while frames is not None and frames.tb_next is not None and _is_library_file(frames.tb_frame.f_code.co_filename):
        frames = frames.tb_next
    return "".join(traceback.format_exception(type(error), error, frames))


def _is_library_file(filename: str) -> bool:
    return Path(filename).resolve().is_relative_to(_PACKAGE_FOLDER)


__all__ = ["RenderedStory", "StoryRenderError", "render_story"]
