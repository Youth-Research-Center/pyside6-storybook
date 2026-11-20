"""The ``pyside6-storybook`` command line, which ``python -m pyside6_storybook`` runs too."""

from __future__ import annotations

import argparse
import os
import platform
import sys
import textwrap
from collections.abc import Sequence
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any

import PySide6
from PySide6.QtCore import qVersion
from PySide6.QtWidgets import QApplication

from pyside6_storybook import __version__
from pyside6_storybook.app import run
from pyside6_storybook.discovery import LoadError, load_stories
from pyside6_storybook.discovery.constants import EXAMPLES_MODULE
from pyside6_storybook.discovery.reload import ReloadSession
from pyside6_storybook.discovery.sources import StorySourcesError, put_on_sys_path, resolve_story_sources
from pyside6_storybook.themes import BUILTIN_THEME_NAMES
from pyside6_storybook.themes.provider import ThemeProvider
from pyside6_storybook.themes.provider_loader import ThemeProviderError, load_theme_provider

PROGRAM_NAME = "pyside6-storybook"
_QT_FOR_PYTHON_DISTRIBUTIONS = ("PySide6", "PySide6-Essentials", "PySide6-Addons", "shiboken6")


def main(argv: Sequence[str] | None = None) -> int:
    """Load the stories named on the command line and open the gallery, or list them with ``--list``.

    Without targets the default sources are used: ``[tool.pyside6-storybook]`` in ``pyproject.toml``, then the
    ``pyside6_storybook.stories`` entry points, then the built-in examples (see ``discovery.sources``). ``--examples`` adds the
    built-in example stories to the targets. With ``--list``, standard error says where the stories came from. The gallery loads the
    targets again when a story file or a module of the project changes, unless ``--no-reload`` is given; ``--list`` never reloads.

    The ``QApplication`` is created before any story module is imported, so a module that creates a widget at import time works.
    With ``--list`` no window is opened, and the offscreen platform is used unless ``QT_QPA_PLATFORM`` says otherwise, so listing
    works without a display.

    The theme provider comes from ``--theme-provider module:attribute``, else ``theme_provider`` in ``pyproject.toml``, else the
    built-in themes; ``--theme`` and ``theme`` choose the starting theme the same way. The provider is loaded after the
    ``QApplication`` exists and before the stories, so a theme module the stories import is first imported by the provider and a
    reload keeps it. A provider that cannot be loaded, or an unknown theme, is an error: the built-in themes are never used instead.
    With ``--list`` standard error also names the provider and its themes; the provider is not activated.

    ``--help``, ``--version``, ``--debug-info`` and usage errors exit through ``SystemExit`` (code 0, 0, 0 and 2), as ``argparse`` does.
    ``--debug-info`` prints the versions a bug report needs and loads nothing.

    Args:
        argv: The arguments after the program name. Defaults to ``sys.argv[1:]``.

    Returns:
        0 on success; 1 when the configuration is wrong, the theme provider cannot be loaded, the theme is unknown, no stories were
        found, a target does not exist, or (with ``--list``) any story module failed to load;
        otherwise the gallery's exit code. Story modules that fail to load are reported on standard error, and the gallery still
        opens with the stories that did load and lists the failures under "Load errors".
    """
    arguments = _parser().parse_args(argv)
    cwd = Path.cwd().resolve()
    try:
        sources = resolve_story_sources(arguments.targets, examples=arguments.examples, cwd=cwd)
    except StorySourcesError as error:
        _print_error(str(error))
        return 1
    targets = sources.targets
    _application = _ensure_application(offscreen=arguments.list)  # kept alive until main returns
    put_on_sys_path(sources.pythonpath, cwd=cwd)
    provider_spec = arguments.theme_provider or sources.theme_provider
    provider: ThemeProvider | None = None
    kept_modules: tuple[str, ...] = ()
    theme_names: Sequence[str] = BUILTIN_THEME_NAMES
    if provider_spec is not None:
        try:
            loaded = load_theme_provider(provider_spec)
            provider, kept_modules = loaded.provider, loaded.modules
            try:
                theme_names = tuple(provider.theme_names())
            except Exception as error:
                raise ThemeProviderError(f"theme provider {provider_spec!r}: theme_names() failed: {type(error).__name__}: {error}") from error
        except ThemeProviderError as error:
            _print_error(str(error))
            return 1
    theme = arguments.theme or sources.theme
    if theme is not None and theme not in theme_names:
        origin = "--theme" if arguments.theme else "theme in pyproject.toml"
        _print_error(f"unknown theme {theme!r} ({origin}); the available themes are: {', '.join(theme_names)}")
        return 1
    result = load_stories(targets, cwd=cwd)
    _print_load_errors(result.errors)
    if any(error.target_error for error in result.errors):
        return 1
    if len(result.registry) == 0:
        _print_error("no stories found in: " + ", ".join(targets))
        return 1
    if arguments.list:
        print(f"{PROGRAM_NAME}: stories from {sources.origin}", file=sys.stderr)
        print(f"{PROGRAM_NAME}: theme provider {provider_spec or 'built-in'} (themes: {', '.join(theme_names)})", file=sys.stderr)
        for story_id in result.registry.ids():
            print(story_id)
        return 1 if result.errors else 0
    session = (
        None
        if arguments.no_reload
        else ReloadSession(targets, cwd=cwd, pythonpath=sources.pythonpath, initial=result, keep=kept_modules)
    )
    return run(result.registry, theme=theme, load_errors=result.errors, reload=session, theme_provider=provider)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=PROGRAM_NAME,
        description="Browse PySide6 widget stories in a gallery window, edit their arguments live and switch themes.",
    )
    parser.add_argument(
        "targets",
        nargs="*",
        metavar="TARGET",
        help="a folder (every *_story.py and *_stories.py file below it is loaded), a .py file, or a dotted module or package name",
    )
    parser.add_argument("--examples", action="store_true", help="also load the built-in example stories, built from stock Qt widgets")
    parser.add_argument("--list", action="store_true", help="print the ids of the stories found, one per line, and exit without opening a window")
    parser.add_argument("--no-reload", action="store_true", help="do not load the stories again when a story file or a module they import changes")
    parser.add_argument(
        "--theme-provider",
        metavar="MODULE:ATTRIBUTE",
        help="a theme provider that applies the application's own themes: an instance, a class or a factory function "
        "(default: the theme_provider key of pyproject.toml, else the built-in themes)",
    )
    parser.add_argument(
        "--theme",
        metavar="NAME",
        help=f"the theme to start in, one of the provider's themes (built-in: {', '.join(BUILTIN_THEME_NAMES)}; "
        f"default: the theme key of pyproject.toml, else the provider's current theme)",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument(
        "--debug-info",
        action=_DebugInfoAction,
        help="print the versions of pyside6-storybook, PySide6, Qt, Python and the platform for a bug report, and exit",
    )
    return parser


def _installed_version(name: str) -> str | None:
    try:
        return version(name)
    except PackageNotFoundError:
        return None


def _debug_info() -> str:
    distributions = [f"{name} {found}" for name in _QT_FOR_PYTHON_DISTRIBUTIONS if (found := _installed_version(name)) is not None]
    lines = {
        "pyside6-storybook": __version__,
        "PySide6": PySide6.__version__,
        "Qt": qVersion(),
        "Qt for Python distributions": ", ".join(distributions) or "none found",
        "Python": f"{platform.python_version()} ({platform.python_implementation()})",
        "Platform": platform.platform(),
        "pytest": _installed_version("pytest") or "not installed",
        "pytest-qt": _installed_version("pytest-qt") or "not installed",
        "QT_QPA_PLATFORM": os.environ.get("QT_QPA_PLATFORM") or "not set",  # Qt treats an empty value as unset
    }
    return "\n".join(f"{key}: {value}" for key, value in lines.items())


class _DebugInfoAction(argparse.Action):
    """Prints ``_debug_info()`` and exits while the arguments are parsed, as ``--version`` does."""

    def __init__(
        self,
        option_strings: Sequence[str],
        dest: str = argparse.SUPPRESS,
        default: str = argparse.SUPPRESS,
        help: str | None = None,  # argparse passes the help text by this keyword
    ) -> None:
        super().__init__(option_strings=option_strings, dest=dest, default=default, nargs=0, help=help)

    def __call__(
        self,
        parser: argparse.ArgumentParser,
        namespace: argparse.Namespace,
        values: str | Sequence[Any] | None,
        option_string: str | None = None,
    ) -> None:
        print(_debug_info())
        parser.exit()


def _ensure_application(*, offscreen: bool) -> QApplication:
    existing = QApplication.instance()
    if isinstance(existing, QApplication):
        return existing
    qt_arguments = [sys.argv[0] if sys.argv and sys.argv[0] else PROGRAM_NAME]
    if offscreen and "QT_QPA_PLATFORM" not in os.environ:
        qt_arguments += ["-platform", "offscreen"]
    return QApplication(qt_arguments)


def _print_load_errors(errors: Sequence[LoadError]) -> None:
    for error in errors:
        _print_error(error.message)
        if error.details:
            print(textwrap.indent(error.details.rstrip("\n"), "    "), file=sys.stderr)


def _print_error(message: str) -> None:
    print(f"error: {message}", file=sys.stderr)


__all__ = ["EXAMPLES_MODULE", "PROGRAM_NAME", "main"]
