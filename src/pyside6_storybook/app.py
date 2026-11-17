"""Entry point that opens the gallery window."""

from __future__ import annotations

import logging
import sys
from collections.abc import Sequence
from dataclasses import dataclass

from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtGui import QFont, QPalette
from PySide6.QtWidgets import QApplication

from pyside6_storybook.discovery import LoadError
from pyside6_storybook.discovery.reload import ReloadSession
from pyside6_storybook.gui.window import GalleryWindow
from pyside6_storybook.polishing import polish_all_widgets
from pyside6_storybook.registry import StoryRegistry, default_registry
from pyside6_storybook.themes import BuiltinThemeProvider, ThemeProvider
from pyside6_storybook.themes.builtin_theme_provider import underlying_style_name

_WINDOW_SIZE = (1100, 700)
_logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class _ApplicationLook:
    """The application-wide properties a theme provider changes."""

    style_name: str
    palette: QPalette
    style_sheet: str
    font: QFont

    @classmethod
    def of(cls, app: QApplication) -> _ApplicationLook:
        """Read the look of ``app``."""
        return cls(
            style_name=underlying_style_name(app), palette=QPalette(app.palette()), style_sheet=app.styleSheet(), font=QFont(app.font())
        )

    def not_restored(self, current: _ApplicationLook) -> list[str]:
        """Return the names of the properties of ``current`` that differ from these."""
        differing = {
            "style": self.style_name != current.style_name,
            "palette": self.palette != current.palette,
            "style sheet": self.style_sheet != current.style_sheet,
            "font": self.font != current.font,
        }
        return [name for name, differs in differing.items() if differs]


def run(
    registry: StoryRegistry | None = None,
    argv: Sequence[str] | None = None,
    *,
    theme: str | None = None,
    load_errors: Sequence[LoadError] = (),
    reload: ReloadSession | None = None,
    theme_provider: ThemeProvider | None = None,
) -> int:
    """Open the gallery window and run the event loop until it closes.

    Creates the ``QApplication`` (an existing one is reused), activates the theme provider for the duration of the run and
    deactivates it afterwards. A provider that leaves the application's style, palette, style sheet or font changed is reported in
    a logged warning; the properties are not fixed.

    Args:
        registry: The stories to show. Defaults to ``default_registry``.
        argv: Command-line arguments for ``QApplication``. Defaults to ``sys.argv``.
        theme: The theme to start in, one of the provider's ``theme_names()``. Defaults to the provider's current theme. It is applied
            through the window once it is built, so a provider that fails to apply it shows the error in the gallery.
        load_errors: Story sources that failed to load, listed in the gallery under "Load errors".
        reload: What to load again when a story file changes; the command line passes it. Internal. Without it, nothing is reloaded.
        theme_provider: Supplies and applies the themes. Defaults to a new ``BuiltinThemeProvider``.

    Returns:
        The exit code of the event loop.

    Raises:
        ValueError: If ``theme`` is not one of the provider's theme names.
    """
    provider = BuiltinThemeProvider() if theme_provider is None else theme_provider
    if theme is not None:
        names = tuple(provider.theme_names())
        if theme not in names:
            raise ValueError(f"Unknown theme {theme!r}; expected one of {names}")
    existing = QApplication.instance()
    app = existing if isinstance(existing, QApplication) else QApplication(list(sys.argv if argv is None else argv))
    before = _ApplicationLook.of(app)
    try:
        polish_all_widgets()  # the provider may change the application style sheet; see pyside6_storybook.polishing
        modules_before = set(sys.modules)
        provider.activate(app)
        if reload is not None:
            # A provider may import its theme manager here; a reload must not drop it, or the stories would get another copy.
            reload.keep_modules(set(sys.modules) - modules_before)
        window = GalleryWindow(default_registry if registry is None else registry, provider, load_errors=load_errors, reload=reload)
        if theme is not None:
            # Through the window, so a provider that fails to apply a valid theme shows the error in the gallery instead of closing it.
            window.set_theme(theme)
        window.resize(*_WINDOW_SIZE)
        window.show()
        exit_code = app.exec()
        window.close()
        window.deleteLater()
        # Delete the window, and every widget it left for deletion, before the provider restores the application's look: Qt can crash
        # in a later setStyleSheet when they are deleted after a style sheet change (#80).
        QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        # Quitting closes the window, and closing the last window posts another Quit event. The loop has ended, so a later event loop in
        # this process would receive it and stop at once, and every nested loop after it would return immediately.
        QCoreApplication.removePostedEvents(app, QEvent.Type.Quit)
    except Exception:
        _logger.exception("The gallery could not run")
        raise
    finally:
        _deactivate(provider, app, before)
    return exit_code


def _deactivate(provider: ThemeProvider, app: QApplication, before: _ApplicationLook) -> None:
    """Deactivate the provider and log a warning for each application property it did not restore. Never raises."""
    try:
        polish_all_widgets()
        provider.deactivate()
        not_restored = before.not_restored(_ApplicationLook.of(app))
    except Exception:
        _logger.exception("Deactivating the theme provider failed")
        return
    if not_restored:
        _logger.warning("The theme provider %s did not restore the application's %s", type(provider).__name__, ", ".join(not_restored))


__all__ = ["run"]
