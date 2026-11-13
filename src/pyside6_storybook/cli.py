"""The ``pyside6-storybook`` command line, which ``python -m pyside6_storybook`` runs too."""

from __future__ import annotations

import argparse
import os
import sys
import textwrap
from collections.abc import Sequence

from PySide6.QtWidgets import QApplication

from pyside6_storybook import __version__
from pyside6_storybook.app import run
from pyside6_storybook.discovery import LoadError, load_stories
from pyside6_storybook.themes import BUILTIN_THEME_NAMES

PROGRAM_NAME = "pyside6-storybook"


def main(argv: Sequence[str] | None = None) -> int:
    """Load the stories named on the command line and open the gallery, or list them with ``--list``.

    The ``QApplication`` is created before any story module is imported, so a module that creates a widget at import time works.
    With ``--list`` no window is opened, and the offscreen platform is used unless ``QT_QPA_PLATFORM`` says otherwise, so listing
    works without a display.

    ``--help``, ``--version`` and usage errors exit through ``SystemExit`` (code 0, 0 and 2), as ``argparse`` does.

    Args:
        argv: The arguments after the program name. Defaults to ``sys.argv[1:]``.

    Returns:
        0 on success; 1 when no stories were found, a target does not exist, or (with ``--list``) any story module failed to load;
        otherwise the gallery's exit code. Story modules that fail to load are reported on standard error, and the gallery still
        opens with the stories that did load and lists the failures under "Load errors".
    """
    arguments = _parser().parse_args(argv)
    targets: list[str] = arguments.targets
    if not targets:
        _print_error(f"no stories to show: pass the folders, files or modules that contain them, for example `{PROGRAM_NAME} path/to/stories`")
        return 1
    _application = _ensure_application(offscreen=arguments.list)  # kept alive until main returns
    result = load_stories(targets)
    _print_load_errors(result.errors)
    if any(error.target_error for error in result.errors):
        return 1
    if len(result.registry) == 0:
        _print_error("no stories found in: " + ", ".join(targets))
        return 1
    if arguments.list:
        for story_id in result.registry.ids():
            print(story_id)
        return 1 if result.errors else 0
    return run(result.registry, theme=arguments.theme, load_errors=result.errors)


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
    parser.add_argument("--list", action="store_true", help="print the ids of the stories found, one per line, and exit without opening a window")
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


__all__ = ["PROGRAM_NAME", "main"]
