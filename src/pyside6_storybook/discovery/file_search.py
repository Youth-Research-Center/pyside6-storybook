"""Finding story files: below a folder, and in a package and its regular subpackages."""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

from pyside6_storybook.discovery.constants import CACHE_FOLDER_NAME, STORY_FILE_SUFFIXES, TEST_FILE_PREFIX, VIRTUAL_ENVIRONMENT_MARKER


def is_story_file_name(name: str) -> bool:
    """Whether a file name is one discovery loads: ``*_story.py`` or ``*_stories.py``, but not a ``test_*`` pytest module."""
    return name.endswith(".py") and name[:-3].endswith(STORY_FILE_SUFFIXES) and not name.startswith(TEST_FILE_PREFIX)


def story_files_below(folder: Path) -> Iterator[Path]:
    """Yield every story file below ``folder`` in a stable order, skipping hidden folders, caches and virtual environments."""
    for directory, subdirectories, files in os.walk(folder):
        here = Path(directory)
        subdirectories[:] = sorted(name for name in subdirectories if _is_searched_folder(here / name))
        for name in sorted(files):
            if is_story_file_name(name):
                yield here / name


def story_modules_in_package(folder: Path, package: str) -> Iterator[tuple[Path, str]]:
    """Yield the story files of a package folder and its regular subpackages, with their dotted module names.

    Args:
        folder: One of the package's ``__path__`` entries.
        package: The package's dotted name.
    """
    for entry in sorted(folder.iterdir()):
        if entry.is_dir():
            if entry.name.isidentifier() and (entry / "__init__.py").is_file():
                yield from story_modules_in_package(entry, f"{package}.{entry.name}")
        elif is_story_file_name(entry.name) and entry.stem.isidentifier():
            yield entry, f"{package}.{entry.stem}"


def _is_searched_folder(folder: Path) -> bool:
    return not folder.name.startswith(".") and folder.name != CACHE_FOLDER_NAME and not (folder / VIRTUAL_ENVIRONMENT_MARKER).exists()


__all__ = ["is_story_file_name", "story_files_below", "story_modules_in_package"]
