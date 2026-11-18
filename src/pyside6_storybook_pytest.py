"""The pytest plugin of pyside6-storybook: renders every story in every theme as a test, and provides the ``render_story`` fixture.

This module is registered through the ``pytest11`` entry point, so pytest imports it on every run. It imports only ``pytest`` and the
standard library at module level: the implementation (``pyside6_storybook.testing``, which imports Qt) is imported inside the hooks,
and only when the plugin is enabled with ``--storybook`` or ``storybook = true``, or when a test uses ``render_story``.
"""

from __future__ import annotations

from collections.abc import Callable, Generator, Iterator
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from PySide6.QtWidgets import QWidget

    from pyside6_storybook.testing.storybook_session import StorybookSession


SESSION_KEY = pytest.StashKey["StorybookSession"]()
"""Where the plugin's ``StorybookSession`` is kept in ``config.stash``. Defined here so the hooks can look it up without importing Qt."""


def _session(config: pytest.Config) -> StorybookSession | None:
    return config.stash.get(SESSION_KEY, None)


def pytest_addoption(parser: pytest.Parser) -> None:
    """Register the options and ini keys; every setting has both, and the command line wins."""
    group = parser.getgroup("storybook", "pyside6-storybook")
    group.addoption("--storybook", action="store_true", default=False, help="render every story in every theme as a test")
    group.addoption(
        "--storybook-stories",
        action="append",
        default=[],
        metavar="TARGET",
        help="a folder, a .py file or a dotted module name to load stories from; repeatable (default: [tool.pyside6-storybook])",
    )
    group.addoption(
        "--storybook-theme-provider",
        metavar="MODULE:ATTRIBUTE",
        help="the theme provider (default: theme_provider in [tool.pyside6-storybook], else the built-in themes)",
    )
    group.addoption("--storybook-themes", metavar="NAMES", help="comma-separated themes to render each story in (default: every theme)")
    group.addoption(
        "--storybook-qt-warnings",
        choices=("fail", "ignore"),
        help="whether a Qt warning logged while a story renders fails its item (default: fail)",
    )
    group.addoption(
        "--storybook-a11y",
        action="store_true",
        default=False,
        help="also check every story for controls without an accessible name or Tab focus (items <id>[a11y-name] and <id>[a11y-focus])",
    )
    parser.addini("storybook", "turn the pyside6-storybook plugin on", type="bool", default=False)
    parser.addini("storybook_stories", "story targets, one per line", type="linelist", default=[])
    parser.addini("storybook_theme_provider", "the theme provider, as module:attribute", default="")
    parser.addini("storybook_themes", "comma-separated themes to render each story in", default="")
    parser.addini("storybook_qt_warnings", "fail or ignore: whether a Qt warning during a render fails the item", default="")
    parser.addini("storybook_a11y", "also check accessible names and keyboard focus of every story", type="bool", default=False)
    parser.addini(
        "storybook_qt_warnings_ignore",
        "regular expressions of Qt warnings that never fail an item, one per line",
        type="linelist",
        default=["propagateSizeHints"],
    )


def pytest_configure(config: pytest.Config) -> None:
    """Register the ``storybook`` marker and, when the plugin is on, check the options and the story sources.

    Raises:
        pytest.UsageError: If an option or the ``[tool.pyside6-storybook]`` table is malformed, or no stories are configured.
    """
    config.addinivalue_line("markers", "storybook: a story rendered in a theme by the pyside6-storybook pytest plugin")
    if config.getoption("storybook") or config.getini("storybook"):
        from pyside6_storybook.testing.storybook_session import StorybookSession

        config.stash[SESSION_KEY] = StorybookSession.from_config(config)


@pytest.hookimpl(wrapper=True, tryfirst=True)
def pytest_make_collect_report(collector: pytest.Collector) -> Generator[None, pytest.CollectReport, pytest.CollectReport]:
    """Add the storybook collector to the pytest session's report, so pytest collects its items like any others.

    The items therefore exist before any ``pytest_collection_modifyitems`` hook runs, are counted in "collected N items" and by
    ``--collect-only``, and take part in ``-k``, ``--deselect`` and ``--lf``.
    """
    report = yield
    if isinstance(collector, pytest.Session) and report.outcome == "passed":
        state = _session(collector.config)
        if state is not None and state.options.enabled:
            from pyside6_storybook.testing.storybook_collector import StorybookCollector

            if not any(isinstance(node, StorybookCollector) for node in report.result):
                report.result.append(StorybookCollector.attach(collector))
    return report


@pytest.hookimpl(wrapper=True)
def pytest_runtest_teardown(item: pytest.Item, nextitem: pytest.Item | None) -> Iterator[None]:
    """Deactivate the theme provider when the next test is not a storybook item, so no other test sees its look."""
    yield
    state = _session(item.config)
    if state is not None and state.active:
        from pyside6_storybook.testing.storybook_item import StorybookItem

        if not isinstance(nextitem, StorybookItem):
            state.release_provider()


def pytest_sessionfinish(session: pytest.Session) -> None:
    """Deactivate the provider, put the default registry back and reinstall the previous Qt message handler."""
    state = _session(session.config)
    if state is not None:
        state.finish()


@pytest.fixture
def render_story(request: pytest.FixtureRequest) -> Iterator[Callable[..., QWidget]]:
    """Render a story by id and return its widget, shown: ``render_story("Inputs/Button/Default", args={...}, theme="Dark")``.

    ``args`` overrides some default arguments (an unknown name raises ``KeyError``), and ``theme`` activates the theme provider for the
    test. What was rendered is deleted at teardown. Needs pytest-qt (``pyside6-storybook[pytest]``).
    """
    from pyside6_storybook.testing.fixtures import story_renderer

    with story_renderer(request) as render:
        yield render
