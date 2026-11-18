"""Where the stories come from when the command line is run: its targets, or the project's default sources.

The order is: targets on the command line (and ``--examples``), then ``[tool.pyside6-storybook]`` in the working directory's
``pyproject.toml``, then the ``pyside6_storybook.stories`` entry points of installed packages, then the built-in examples. The
examples are used only when nothing is configured, never because configured stories failed to load.

``pythonpath``, ``theme_provider`` and ``theme`` of the same table apply whichever of these supplies the stories.
"""

from __future__ import annotations

import sys
import tomllib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from importlib.metadata import entry_points
from pathlib import Path

import pyside6_storybook.examples
from pyside6_storybook.discovery.constants import CONFIG_FILE_NAME, CONFIG_TABLE, ENTRY_POINT_GROUP
from pyside6_storybook.discovery.module_import import prepend_to_sys_path

EXAMPLES_FOLDER = Path(pyside6_storybook.examples.__file__).resolve().parent
"""The folder of the installed example stories. Loaded by path, not by module name, so a local folder or module of the same name
cannot shadow it (an existing path wins over a module name in story discovery)."""

_KNOWN_KEYS = ("stories", "pythonpath", "theme_provider", "theme")


class StorySourcesError(Exception):
    """The ``[tool.pyside6-storybook]`` configuration cannot be used; the message names the file and the key."""


@dataclass(frozen=True, slots=True)
class StorySources:
    """The targets to load and where they came from.

    Attributes:
        targets: Folders, files and dotted module names for ``load_stories``, resolved against the working directory.
        origin: Where the targets came from, for messages ("the command line", "[tool.pyside6-storybook] in ...").
        pythonpath: Folders to put on ``sys.path`` before loading, from the configuration. Absolute paths.
        theme_provider: The ``module:attribute`` of the configured theme provider, or ``None``.
        theme: The configured starting theme, or ``None``.
        fallback: ``True`` when the targets are the built-in examples because nothing was configured, so no caller has to parse ``origin``.
    """

    targets: tuple[str, ...]
    origin: str
    pythonpath: tuple[Path, ...] = field(default=(), kw_only=True)
    theme_provider: str | None = field(default=None, kw_only=True)
    theme: str | None = field(default=None, kw_only=True)
    fallback: bool = field(default=False, kw_only=True)


def resolve_story_sources(command_line_targets: Sequence[str], *, examples: bool, cwd: Path) -> StorySources:
    """Decide which targets to load.

    Args:
        command_line_targets: The targets given on the command line.
        examples: Whether ``--examples`` was given; it adds the built-in examples to the command-line targets.
        cwd: The working directory, where ``pyproject.toml`` is looked for.

    Returns:
        The targets, their origin, the configured ``pythonpath``, ``theme_provider`` and ``theme``, and whether the built-in examples
            were used because nothing was configured (``fallback``).

    Raises:
        StorySourcesError: If ``pyproject.toml`` is not valid TOML or its ``[tool.pyside6-storybook]`` table is wrong. The file is
            read also when the command line names targets, because ``pythonpath``, ``theme_provider`` and ``theme`` apply to
            whatever stories are opened; only ``stories`` is ignored then.
    """
    config_path = cwd / CONFIG_FILE_NAME
    table = _read_config_table(config_path)
    pythonpath = _pythonpath(table, config_path) if table is not None else ()
    theme_provider = _non_empty_string(table, "theme_provider", config_path) if table is not None else None
    theme = _non_empty_string(table, "theme", config_path) if table is not None else None
    if command_line_targets or examples:
        targets = tuple(command_line_targets) + ((str(EXAMPLES_FOLDER),) if examples else ())
        return StorySources(targets, "the command line", pythonpath=pythonpath, theme_provider=theme_provider, theme=theme)
    stories = _stories(table, config_path) if table is not None else None
    if stories is not None:
        origin = f"[tool.{CONFIG_TABLE}] in {config_path}"
        return StorySources(stories, origin, pythonpath=pythonpath, theme_provider=theme_provider, theme=theme)
    advertised = list(entry_points(group=ENTRY_POINT_GROUP))
    if advertised:
        names = ", ".join(entry_point.name for entry_point in advertised)
        targets = tuple(entry_point.module for entry_point in advertised)
        origin = f"the {ENTRY_POINT_GROUP} entry points: {names}"
        return StorySources(targets, origin, pythonpath=pythonpath, theme_provider=theme_provider, theme=theme)
    return StorySources(
        (str(EXAMPLES_FOLDER),),
        "the built-in examples (nothing is configured)",
        pythonpath=pythonpath,
        theme_provider=theme_provider,
        theme=theme,
        fallback=True,
    )


def put_on_sys_path(folders: Sequence[Path], *, cwd: Path) -> None:
    """Put the working directory and then the configured ``pythonpath`` folders at the front of ``sys.path``.

    The folders end up first, in the configured order, ahead of the working directory, so a module in ``src`` is not shadowed by
    one of the same name at the project root. A folder already on ``sys.path`` is moved, not duplicated.

    Args:
        folders: The configured folders, in order.
        cwd: The working directory, which ``load_stories`` also puts on ``sys.path``.
    """
    prepend_to_sys_path(cwd)
    for folder in reversed(folders):
        entry = str(folder)
        sys.path[:] = [existing for existing in sys.path if existing != entry]
        sys.path.insert(0, entry)


def _read_config_table(path: Path) -> Mapping[str, object] | None:
    if not path.is_file():
        return None
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        raise StorySourcesError(f"{path} cannot be read: {error}") from error
    try:
        document = tomllib.loads(text)
    except tomllib.TOMLDecodeError as error:
        raise StorySourcesError(f"{path} is not valid TOML: {error}") from error
    tool = document.get("tool", {})
    if not isinstance(tool, dict):
        raise StorySourcesError(f"[tool] in {path} must be a table")
    table = tool.get(CONFIG_TABLE)
    if table is None:
        return None
    if not isinstance(table, dict):
        raise StorySourcesError(f"[tool.{CONFIG_TABLE}] in {path} must be a table")
    unknown = sorted(set(table) - set(_KNOWN_KEYS))
    if unknown:
        listed = ", ".join(repr(key) for key in unknown)
        raise StorySourcesError(f"[tool.{CONFIG_TABLE}] in {path}: unknown key {listed}; the known keys are {', '.join(_KNOWN_KEYS)}")
    return table


def _string_list(table: Mapping[str, object], key: str, path: Path) -> tuple[str, ...] | None:
    value = table.get(key)
    if value is None:
        return None
    if not isinstance(value, list) or not all(isinstance(item, str) and item for item in value):
        raise StorySourcesError(f"[tool.{CONFIG_TABLE}] in {path}: '{key}' must be a list of strings")
    return tuple(value)


def _non_empty_string(table: Mapping[str, object], key: str, path: Path) -> str | None:
    value = table.get(key)
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise StorySourcesError(f"[tool.{CONFIG_TABLE}] in {path}: '{key}' must be a non-empty string")
    return value


def _stories(table: Mapping[str, object], path: Path) -> tuple[str, ...] | None:
    stories = _string_list(table, "stories", path)
    if stories == ():
        raise StorySourcesError(f"[tool.{CONFIG_TABLE}] in {path}: 'stories' is empty")
    return stories


def _pythonpath(table: Mapping[str, object], path: Path) -> tuple[Path, ...]:
    entries = _string_list(table, "pythonpath", path) or ()
    folders = []
    for entry in entries:
        folder = (path.parent / entry).resolve()
        if not folder.is_dir():
            raise StorySourcesError(f"[tool.{CONFIG_TABLE}] in {path}: 'pythonpath' folder '{entry}' does not exist")
        folders.append(folder)
    return tuple(folders)


__all__ = ["EXAMPLES_FOLDER", "StorySources", "StorySourcesError", "put_on_sys_path", "resolve_story_sources"]
