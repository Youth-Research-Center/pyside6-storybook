"""The ``pyside6-storybook`` command line, which ``python -m pyside6_storybook`` runs too."""

from __future__ import annotations

import argparse
import os
import sys
import textwrap
from collections.abc import Sequence
from pathlib import Path

from PySide6.QtWidgets import QApplication

from pyside6_storybook import __version__
from pyside6_storybook.app import run
from pyside6_storybook.discovery import LoadError, load_stories
from pyside6_storybook.discovery.constants import EXAMPLES_MODULE
from pyside6_storybook.discovery.reload import ReloadSession
from pyside6_storybook.discovery.sources import StorySourcesError, put_on_sys_path, resolve_story_sources
from pyside6_storybook.themes import BUILTIN_THEME_NAMES

PROGRAM_NAME = "pyside6-storybook"


def main(argv: Sequence[str] | None = None) -> int:
    """Load the stories named on the command line and open the gallery, or list them with ``--list``.

    Without targets the default sources are used: ``[tool.pyside6-storybook]`` in ``pyproject.toml``, then the
    ``pyside6_storybook.stories`` entry points, then the built-in examples (see ``discovery.sources``). ``--examples`` adds the
    built-in example stories to the targets. With ``--list``, standard error says where the stories came from. The gallery loads the
    targets again when a story file or a module of the project changes, unless ``--no-reload`` is given; ``--list`` never reloads.

    The ``QApplication`` is created before any story module is imported, so a module that creates a widget at import time works.
    With ``--list`` no window is opened, and the offscreen platform is used unless ``QT_QPA_PLATFORM`` says otherwise, so listing
    works without a display.

    ``--help``, ``--version`` and usage errors exit through ``SystemExit`` (code 0, 0 and 2), as ``argparse`` does.

    Args:
        argv: The arguments after the program name. Defaults to ``sys.argv[1:]``.

    Returns:
        0 on success; 1 when the configuration is wrong, no stories were found, a target does not exist, or (with ``--list``) any
        story module failed to load;
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
    result = load_stories(targets, cwd=cwd)
    _print_load_errors(result.errors)
    if any(error.target_error for error in result.errors):
        return 1
    if len(result.registry) == 0:
        _print_error("no stories found in: " + ", ".join(targets))
        return 1
    if arguments.list:
        print(f"{PROGRAM_NAME}: stories from {sources.origin}", file=sys.stderr)
        for story_id in result.registry.ids():
            print(story_id)
        return 1 if result.errors else 0
    session = None if arguments.no_reload else ReloadSession(targets, cwd=cwd, pythonpath=sources.pythonpath, initial=result)
    return run(result.registry, theme=arguments.theme, load_errors=result.errors, reload=session)


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
    parser.add_argument("--theme", choices=BUILTIN_THEME_NAMES, help=f"the theme to start in (default: {BUILTIN_THEME_NAMES[0]})")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser


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
