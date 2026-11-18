"""``StorybookSession``: what the pytest plugin keeps for one pytest run (internal).

It owns the ``QApplication``, the theme provider and its lifecycle, and the registry of the stories, and it renders a story in a theme.
It lives in ``config.stash`` under ``SESSION_KEY``.
"""

from __future__ import annotations

import logging
import os
import sys
import traceback
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, TypeVar

import pytest
from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QPalette
from PySide6.QtWidgets import QApplication, QLayout, QVBoxLayout, QWidget

import pyside6_storybook
from pyside6_storybook import registry as registry_module
from pyside6_storybook.discovery import LoadError, load_stories
from pyside6_storybook.discovery.sources import StorySources, StorySourcesError, put_on_sys_path, resolve_story_sources
from pyside6_storybook.polishing import polish_all_widgets
from pyside6_storybook.registry import Story, StoryContext, StoryRegistry
from pyside6_storybook.registry.rendering import RenderedStory, StoryRenderError, render_story
from pyside6_storybook.testing.exception_capture import ExceptionCapture
from pyside6_storybook.testing.qt_messages import QtMessageCollector
from pyside6_storybook.testing.storybook_options import StorybookOptions
from pyside6_storybook.themes import BuiltinThemeProvider, ThemeProvider
from pyside6_storybook.themes.builtin_theme_provider import palette_color_scheme
from pyside6_storybook.themes.provider_loader import ThemeProviderError, load_theme_provider
from pyside6_storybook.themes.provider_values import read_color_scheme, read_tokens
from pyside6_storybook_pytest import SESSION_KEY

if TYPE_CHECKING:
    from pyside6_storybook.testing.storybook_collector import StorybookCollector

NO_STORIES_CONFIGURED = "no stories configured: set `storybook_stories` or `stories` in `[tool.pyside6-storybook]`"

_logger = logging.getLogger(__name__)
_T = TypeVar("_T")
_application: QApplication | None = None
"""The ``QApplication`` this module created, kept for the life of the process: pytest-qt and later runs in the process reuse it."""


class StorybookFailure(Exception):
    """A failure to report as plain text, without a traceback: a theme provider error or Qt warnings.

    Attributes:
        text: The message to show for the failing item.
    """

    def __init__(self, text: str) -> None:
        """Create the failure.

        Args:
            text: What to show for the failing item.
        """
        super().__init__(text)
        self.text = text


@dataclass(frozen=True, slots=True)
class RenderedHost:
    """A story rendered inside an opaque host widget, shown offscreen.

    Attributes:
        widget: The story's own widget, undecorated.
        root: The outermost widget after the decorators; a child of ``host``.
        host: The shown top-level widget that holds ``root``.
    """

    widget: QWidget
    root: QWidget
    host: QWidget

    def dispose(self) -> None:
        """Hide the host and delete it with everything in it, flushing the deferred delete."""
        self.host.hide()
        self.host.deleteLater()
        QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


class _DiscardingSink:
    """An ``ActionSink`` that drops every action; a rendered story logs nothing."""

    def record(self, name: str, args: tuple[object, ...]) -> None:
        """Ignore one action."""


class StorybookSession:
    """The state of the plugin in one pytest run.

    ``prepare`` creates the ``QApplication``, loads the theme provider and then the stories into a fresh registry; ``finish`` puts the
    default registry back and deactivates the provider.

    Attributes:
        options: The options of the run.
        sources: Where the stories come from.
        registry: The registry the stories were loaded into; ``None`` until ``prepare`` loaded them.
        provider: The theme provider; the built-in one until ``prepare`` loaded the project's.
        themes: The themes each story is rendered in; empty until ``prepare`` ran.
        load_errors: The story sources that failed to load.
        configuration_error: Why the provider or the themes cannot be used, or ``None``. No stories are loaded then.
    """

    def __init__(self, options: StorybookOptions, sources: StorySources, *, rootpath: Path) -> None:
        """Create a session; nothing is imported or created until ``prepare``.

        Args:
            options: The checked options.
            sources: The resolved story sources.
            rootpath: The project root, where ``pyproject.toml`` is and the targets are resolved.
        """
        self.options = options
        self.sources = sources
        self.registry: StoryRegistry | None = None
        self.provider: ThemeProvider = BuiltinThemeProvider()
        self.themes: tuple[str, ...] = ()
        self.load_errors: tuple[LoadError, ...] = ()
        self.configuration_error: str | None = None
        self._rootpath = rootpath
        self._prepared = False
        self._active = False
        self._app: QApplication | None = None
        self._bindings: tuple[StoryRegistry, StoryRegistry] | None = None
        self._collector: QtMessageCollector | None = None

    @classmethod
    def from_config(cls, config: pytest.Config) -> StorybookSession:
        """Read the options and the story sources of a pytest configuration.

        Args:
            config: The pytest configuration. Its ``rootpath`` is searched for ``pyproject.toml``.

        Returns:
            A session that has not loaded anything.

        Raises:
            pytest.UsageError: If an option is malformed, ``pyproject.toml`` is wrong, or no stories are configured and only the
                built-in examples would be tested.
        """
        options = StorybookOptions.from_config(config)
        try:
            sources = resolve_story_sources(options.targets, examples=False, cwd=config.rootpath)
        except StorySourcesError as error:
            raise pytest.UsageError(str(error)) from error
        if sources.fallback:
            raise pytest.UsageError(NO_STORIES_CONFIGURED)
        return cls(options, sources, rootpath=config.rootpath)

    @classmethod
    def for_config(cls, config: pytest.Config) -> StorybookSession:
        """Return the session of ``config``, creating and keeping one when the plugin is not enabled (for ``render_story``)."""
        session = config.stash.get(SESSION_KEY, None)
        if session is None:
            session = cls.from_config(config)
            config.stash[SESSION_KEY] = session
        return session

    @property
    def active(self) -> bool:
        """Whether the theme provider is activated."""
        return self._active

    def prepare(self) -> None:
        """Create the ``QApplication``, then load the theme provider and the stories; does nothing after the first call.

        ``QT_QPA_PLATFORM`` defaults to ``offscreen``. A provider that cannot be loaded, or a theme that it does not list, is not
        raised: it is kept in ``configuration_error`` and no stories are loaded.
        """
        if self._prepared:
            return
        self._prepared = True
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        self._app = _ensure_application()
        put_on_sys_path(self.sources.pythonpath, cwd=self._rootpath)
        spec = self.options.theme_provider or self.sources.theme_provider
        try:
            if spec is not None:
                self.provider = load_theme_provider(spec).provider
            try:
                names = tuple(self.provider.theme_names())
            except Exception as error:
                raise ThemeProviderError(f"theme provider {spec!r}: theme_names() failed: {type(error).__name__}: {error}") from error
        except ThemeProviderError as error:
            self.configuration_error = str(error)
            return
        unknown = [name for name in self.options.themes or () if name not in names]
        if unknown:
            listed = ", ".join(map(repr, unknown))
            self.configuration_error = f"unknown theme {listed} (storybook_themes); the available themes are: {', '.join(names)}"
            return
        self.themes = self.options.themes or names
        previous = registry_module.default_registry
        self._bindings = (previous, pyside6_storybook.default_registry)
        fresh = StoryRegistry()
        registry_module.default_registry = fresh
        pyside6_storybook.default_registry = fresh
        imported_before = set(sys.modules)
        result = load_stories(self.sources.targets, cwd=self._rootpath)
        self.registry = result.registry
        self.load_errors = result.errors + _imported_too_early(result.modules, imported_before, previous, fresh)

    def collect_items(self, collector: StorybookCollector) -> list[pytest.Item]:
        """Prepare the session and build the items under ``collector``: stories in registry order, then themes, then load errors.

        Args:
            collector: The parent of the items.

        Returns:
            One item per story and theme, one per load error, or a single configuration item.
        """
        from pyside6_storybook.testing.load_error_item import ConfigurationItem, StoryLoadErrorItem
        from pyside6_storybook.testing.story_item import StoryItem

        self.prepare()
        if self.configuration_error is not None:
            return [ConfigurationItem.from_parent(collector, message=self.configuration_error)]
        registry = self.registry
        assert registry is not None
        items: list[pytest.Item] = [StoryItem.from_parent(collector, story=story, theme=theme) for story in registry for theme in self.themes]
        items.extend(StoryLoadErrorItem.from_parent(collector, error=error) for error in self.load_errors)
        if not items:
            targets = ", ".join(self.sources.targets)
            items.append(ConfigurationItem.from_parent(collector, message=f"no stories found in: {targets}"))
        return items

    def get_story(self, story_id: str) -> Story:
        """Return a loaded story.

        Args:
            story_id: The story's id.

        Returns:
            The story.

        Raises:
            KeyError: If no story has the id; the message lists the closest ids.
        """
        import difflib

        self.prepare()
        if self.configuration_error is not None:
            raise pytest.UsageError(self.configuration_error)
        assert self.registry is not None
        if story_id in self.registry:
            return self.registry.get(story_id)
        close = difflib.get_close_matches(story_id, self.registry.ids(), n=5, cutoff=0.5)
        hint = f"; did you mean: {', '.join(close)}" if close else f"; the stories are: {', '.join(self.registry.ids()) or 'none'}"
        raise KeyError(f"unknown story {story_id!r}{hint}")

    def activate_provider(self) -> None:
        """Activate the theme provider if it is not active.

        Raises:
            StorybookFailure: If the provider fails.
        """
        if self._active:
            return
        app = self._app or _ensure_application()
        polish_all_widgets()
        self._provider_call("activate", self.provider.activate, app)
        self._active = True

    def release_provider(self) -> None:
        """Deactivate the theme provider if it is active, which puts the application's look back. Never raises."""
        if not self._active:
            return
        self._active = False
        try:
            polish_all_widgets()
            self.provider.deactivate()
        except Exception:
            _logger.exception("Deactivating the theme provider failed")

    def set_theme(self, theme: str) -> None:
        """Activate the provider and switch it to ``theme``, polishing every widget first.

        Raises:
            StorybookFailure: If the provider fails.
        """
        self.activate_provider()
        polish_all_widgets()
        if self._provider_call("current_theme", self.provider.current_theme) != theme:
            self._provider_call("set_theme", self.provider.set_theme, theme)

    def render(self, story: Story, *, args: Mapping[str, object] | None = None) -> RenderedHost:
        """Render a story in the current theme, inside an opaque host widget that is shown offscreen.

        The context carries the story's default arguments (``args`` override some), a sink that discards actions, and, while the
        provider is active, its tokens and colour scheme.

        Args:
            story: The story to render.
            args: Values that replace some default arguments; they are already coerced.

        Returns:
            The rendered widgets. The caller disposes them.

        Raises:
            StoryRenderError: If the story or a decorator fails.
            StorybookFailure: If the theme provider fails.
        """
        existing = set(QApplication.topLevelWidgets())
        try:
            return self._render(story, args)
        except BaseException:
            # A story that raises leaves the widgets it built before the error without a parent, and render_story cannot know them.
            for widget in set(QApplication.topLevelWidgets()) - existing:
                widget.hide()
                widget.deleteLater()
            QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
            raise

    def _render(self, story: Story, args: Mapping[str, object] | None) -> RenderedHost:
        values = story.default_args()
        if args:
            values.update(args)
        tokens: Mapping[str, object] = {}
        scheme: Qt.ColorScheme | None = None
        if self._active:
            tokens = self._provider_call("tokens", read_tokens, self.provider)
            scheme = self._provider_call("color_scheme", read_color_scheme, self.provider)
        context = StoryContext(
            args=values,
            theme=self._provider_call("current_theme", self.provider.current_theme),
            actions=_DiscardingSink(),
            tokens=tokens,
            color_scheme=scheme if scheme is not None else palette_color_scheme(QApplication.palette()),
        )
        assert self.registry is not None
        rendered = render_story(story, context, registry=self.registry)
        return self._show(rendered)

    def check_story(self, story: Story, theme: str) -> None:
        """Render a story in a theme and dispose of it; what a story item runs.

        Qt warnings logged meanwhile fail the item unless an ignore pattern matches them or ``storybook_qt_warnings`` is ``ignore``. An
        exception that PySide6 hands to ``sys.excepthook`` meanwhile (one raised in a ``paintEvent`` or a slot) fails it too, with or
        without pytest-qt.

        Raises:
            StoryRenderError: If the story or a decorator fails.
            StorybookFailure: If the theme provider fails, Qt logged a warning or an exception reached ``sys.excepthook``.
        """
        collector = QtMessageCollector()
        self._collector = collector
        try:
            with collector, ExceptionCapture() as exceptions:
                self.set_theme(theme)
                self.render(story).dispose()
        finally:
            self._collector = None
        unexcused = collector.unexcused(self.options.qt_warnings_ignore) if self.options.qt_warnings_fail else []
        parts: list[str] = []
        if exceptions.errors:
            parts.append(f"{len(exceptions.errors)} exception(s) raised in Qt while rendering {story.id} in {theme}:")
            parts.extend(exceptions.errors)
        if unexcused:
            listed = "\n".join(f"  {message}" for message in unexcused)
            parts.append(f"Qt logged {len(unexcused)} warning(s) while rendering {story.id} in {theme}:\n{listed}")
        if parts:
            raise StorybookFailure("\n".join(parts))

    def finish(self) -> None:
        """End the session: deactivate the provider, put both bindings of the default registry back and reinstall the Qt message handler."""
        self.release_provider()
        if self._collector is not None:
            self._collector.uninstall()
            self._collector = None
        if self._bindings is not None:
            registry_module.default_registry, pyside6_storybook.default_registry = self._bindings
            self._bindings = None

    def _show(self, rendered: RenderedStory) -> RenderedHost:
        """Put the story's root in an opaque host, show it, drop the focus a shown window gives its first input and settle the events."""
        host = QWidget()
        host.setAutoFillBackground(True)
        host.setBackgroundRole(QPalette.ColorRole.Window)
        layout = QVBoxLayout(host)
        layout.setContentsMargins(0, 0, 0, 0)
        # A top-level layout that constrains its window makes Qt ask the platform to propagate the size hints, which the offscreen
        # platform logs a warning for, for every story; the host does not need constraints.
        layout.setSizeConstraint(QLayout.SizeConstraint.SetNoConstraint)
        layout.addWidget(rendered.root)
        result = RenderedHost(widget=rendered.widget, root=rendered.root, host=host)
        try:
            host.show()
            QApplication.processEvents()
            focus = QApplication.focusWidget()
            if focus is not None and (focus is host or host.isAncestorOf(focus)):
                focus.clearFocus()
            QApplication.processEvents()
        except BaseException:
            result.dispose()
            raise
        return result

    def _provider_call(self, name: str, function: Callable[..., _T], *args: object) -> _T:
        try:
            return function(*args)
        except Exception as error:
            text = "".join(traceback.format_exception(error))
            summary = f"theme provider {type(self.provider).__name__}: {name}() failed: {type(error).__name__}: {error}"
            raise StorybookFailure(f"{summary}\n\n{text}") from error


def _imported_too_early(
    modules: tuple[str, ...], imported_before: set[str], previous: StoryRegistry, fresh: StoryRegistry
) -> tuple[LoadError, ...]:
    """Return a load error for each story module that was imported before collection and whose stories are therefore missing.

    Python does not execute a module again, so its stories went to the registry that was the default when it was imported.
    """
    errors: list[LoadError] = []
    for name in modules:
        if name not in imported_before:
            continue
        missing = [story.id for story in previous if story.origin.module == name and story.id not in fresh]
        if missing:
            message = (
                f"{name} was imported before the plugin collected the stories (by a test module or a conftest.py), so its stories "
                f"{', '.join(missing)} are not tested; import it inside the tests that use it, not at module level"
            )
            errors.append(LoadError(name, message))
    return tuple(errors)


def _ensure_application() -> QApplication:
    global _application
    existing = QApplication.instance()
    if isinstance(existing, QApplication):
        return existing
    _application = QApplication([sys.argv[0] if sys.argv and sys.argv[0] else "pyside6-storybook"])
    return _application


__all__ = ["NO_STORIES_CONFIGURED", "RenderedHost", "StoryRenderError", "StorybookFailure", "StorybookSession"]
