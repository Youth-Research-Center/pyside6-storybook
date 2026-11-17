"""``ThemeProvider``: the protocol an application implements to let the gallery use its own theme manager."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Protocol, runtime_checkable

from PySide6.QtWidgets import QApplication


@runtime_checkable
class ThemeProvider(Protocol):
    """Applies themes to the application and tells the gallery when the theme changed.

    The gallery calls every method on the main thread, and a provider calls its callbacks on it too. The lifecycle:

    1. ``theme_names`` and ``current_theme`` work before ``activate``. ``theme_names`` is not empty and does not change while the
       provider is active.
    2. ``activate`` is called once, before the window is built. It records whatever the provider will change (style, palette,
       style sheet, font, colour scheme) and applies the current theme.
    3. ``set_theme`` applies a theme and raises ``ValueError`` for a name that ``theme_names`` does not list.
    4. ``on_changed`` registers a callback that the provider calls with no arguments after every theme change, whether the gallery
       asked for it or the provider made it itself. Several callbacks may be registered and are called in order.
    5. ``deactivate`` undoes everything ``activate`` and ``set_theme`` changed, the font included, and clears the callbacks.
    6. A provider that sets an application-wide style sheet also sets a matching ``QPalette``: the gallery chrome is drawn from
       palette roles, and a style sheet alone leaves ``QApplication.palette()`` unchanged.
    7. ``tokens() -> Mapping[str, object]`` is optional and not part of this protocol, so a provider without it still satisfies
       it. When present, the gallery reads it after ``activate`` and after every change notification and gives the result to each
       story as ``StoryContext.tokens``; a provider without it gives stories an empty mapping.
    """

    def theme_names(self) -> Sequence[str]:
        """Return the names of the available themes, in the order the theme switch lists them."""
        ...

    def current_theme(self) -> str:
        """Return the name of the current theme."""
        ...

    def activate(self, app: QApplication) -> None:
        """Record what the provider will change on ``app`` and apply the current theme."""
        ...

    def set_theme(self, name: str) -> None:
        """Apply a theme and notify the callbacks.

        Raises:
            ValueError: If ``name`` is not one of ``theme_names``.
        """
        ...

    def on_changed(self, callback: Callable[[], None]) -> None:
        """Register a callback that is called with no arguments after every theme change."""
        ...

    def deactivate(self) -> None:
        """Restore everything ``activate`` and ``set_theme`` changed and clear the registered callbacks."""
        ...


__all__ = ["ThemeProvider"]
