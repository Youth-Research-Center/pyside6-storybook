"""Entry point that opens the gallery window."""

from __future__ import annotations

import sys
from collections.abc import Sequence

from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtWidgets import QApplication

from pyside6_storybook.discovery import LoadError
from pyside6_storybook.discovery.reload import ReloadSession
from pyside6_storybook.gui.window import GalleryWindow
from pyside6_storybook.registry import StoryRegistry, default_registry
from pyside6_storybook.themes import BuiltinThemes

_WINDOW_SIZE = (1100, 700)


def run(
    registry: StoryRegistry | None = None,
    argv: Sequence[str] | None = None,
    *,
    theme: str | None = None,
    load_errors: Sequence[LoadError] = (),
    reload: ReloadSession | None = None,
) -> int:
    """Open the gallery window and run the event loop until it closes.

    Creates the ``QApplication`` (an existing one is reused), activates the built-in themes for the duration of the run and
    restores the application's style and palette afterwards.

    Args:
        registry: The stories to show. Defaults to ``default_registry``.
        argv: Command-line arguments for ``QApplication``. Defaults to ``sys.argv``.
        theme: The built-in theme to start in. Defaults to the first one.
        load_errors: Story sources that failed to load, listed in the gallery under "Load errors".
        reload: What to load again when a story file changes; the command line passes it. Internal. Without it, nothing is reloaded.

    Returns:
        The exit code of the event loop.

    Raises:
        ValueError: If ``theme`` is not a built-in theme.
    """
    existing = QApplication.instance()
    app = existing if isinstance(existing, QApplication) else QApplication(list(sys.argv if argv is None else argv))
    themes = BuiltinThemes()
    if theme is not None:
        themes.set_theme(theme)
    themes.activate(app)
    try:
        window = GalleryWindow(default_registry if registry is None else registry, themes, load_errors=load_errors, reload=reload)
        window.resize(*_WINDOW_SIZE)
        window.show()
        exit_code = app.exec()
        window.close()
        window.deleteLater()
        # Quitting closes the window, and closing the last window posts another Quit event. The loop has ended, so a later event loop in
        # this process would receive it and stop at once, and every nested loop after it would return immediately.
        QCoreApplication.removePostedEvents(app, QEvent.Type.Quit)
    finally:
        themes.deactivate()
    return exit_code


__all__ = ["run"]
