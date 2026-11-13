"""``load_stories``: import story modules from folders, files and dotted module names."""

from __future__ import annotations

import importlib
import importlib.util
import os
import traceback
from collections.abc import Callable, Iterable
from functools import partial
from pathlib import Path
from typing import TypeVar

from pyside6_storybook import registry as registry_module
from pyside6_storybook.discovery.constants import NOT_FOUND_MESSAGE
from pyside6_storybook.discovery.file_search import story_files_below, story_modules_in_package
from pyside6_storybook.discovery.load_result import LoadError, LoadResult
from pyside6_storybook.discovery.module_import import ModuleNameTakenError, import_file, prepend_to_sys_path, spec_file

_T = TypeVar("_T")


def load_stories(targets: Iterable[str | os.PathLike[str]], *, cwd: str | os.PathLike[str] | None = None) -> LoadResult:
    """Import the story modules named by ``targets``; their ``@story`` decorators register the stories.

    Each target is, in this order of precedence:

    - an existing folder: every ``*_story.py`` and ``*_stories.py`` file below it is loaded, skipping ``test_*`` files, hidden
      folders, ``__pycache__`` and virtual environments;
    - an existing ``.py`` file: that file is loaded;
    - a dotted module name: the module is imported, and for a package also its submodules named ``*_story`` or ``*_stories``
      in it and in its regular subpackages (again skipping ``test_*`` files).

    A file inside a package (its folder has ``__init__.py``) is imported under its full dotted name, with the folder above the
    topmost package on ``sys.path``, so relative imports work and a file reached by path and by module name is one module. A
    file outside any package is imported under its own name with its folder on ``sys.path``, so siblings can import it and share
    the module; it gets a synthetic name derived from its path only when its own name is taken by another file. A file whose
    module name refers to a different file is reported without being executed. ``cwd`` is put on ``sys.path`` too, as
    ``python -m`` does, so stories can import the application.

    Importing runs the code in those modules, exactly as running a test suite does.

    Args:
        targets: Folders, files and dotted module names. Relative paths are resolved against ``cwd``. Duplicates are ignored.
        cwd: The working directory; defaults to the process's current directory.

    Returns:
        The registry the stories registered in, the modules loaded, and the targets or files that failed. A failure never stops
        the remaining targets from loading.
    """
    working_directory = Path.cwd() if cwd is None else Path(cwd)
    prepend_to_sys_path(working_directory.resolve())
    importlib.invalidate_caches()
    loader = _Loader(working_directory)
    for target in targets:
        loader.load_target(target)
    return LoadResult(registry=registry_module.default_registry, modules=tuple(loader.modules), errors=tuple(loader.errors))


class _Loader:
    """Imports story modules for one ``load_stories`` call and records what happened."""

    def __init__(self, working_directory: Path) -> None:
        self._working_directory = working_directory
        self._seen_targets: set[str] = set()
        self._seen_files: set[Path] = set()
        self.modules: list[str] = []
        self.errors: list[LoadError] = []

    def load_target(self, target: str | os.PathLike[str]) -> None:
        text = os.fspath(target)
        if text in self._seen_targets:
            return
        self._seen_targets.add(text)
        path = Path(text)
        if not path.is_absolute():
            path = self._working_directory / path
        if path.is_dir():
            for file in story_files_below(path):
                self._load_file(file)
        elif path.is_file():
            if path.suffix != ".py":
                self.errors.append(LoadError(text, f"{text} is not a Python file or a folder"))
                return
            self._load_file(path)
        else:
            self._load_dotted_name(text)

    def _load_file(self, path: Path) -> None:
        path = path.resolve()
        if path in self._seen_files:
            return
        self._seen_files.add(path)
        try:
            module_name = self._guarded_import(str(path), str(path), partial(import_file, path))
        except ModuleNameTakenError as error:
            self.errors.append(LoadError(str(path), str(error)))
            return
        if module_name is not None:
            self._record_module(module_name)

    def _load_dotted_name(self, name: str) -> None:
        if not all(part.isidentifier() for part in name.split(".")):
            self.errors.append(LoadError(name, f"{name}: {NOT_FOUND_MESSAGE}"))
            return
        errors_before = len(self.errors)
        try:
            spec = self._guarded_import(name, name, partial(importlib.util.find_spec, name), reraise_missing=True)
            if spec is None:
                if len(self.errors) == errors_before:
                    self.errors.append(LoadError(name, f"{name}: {NOT_FOUND_MESSAGE}"))
                return
            file = spec_file(spec)
            if file is not None and file in self._seen_files:
                return
            module = self._guarded_import(name, name, partial(importlib.import_module, name), reraise_missing=True)
        except ModuleNotFoundError:
            self.errors.append(LoadError(name, f"{name}: {NOT_FOUND_MESSAGE}"))
            return
        if module is None:
            return
        if file is not None:
            self._seen_files.add(file)
        if not hasattr(module, "__path__"):
            self._record_module(name)
            return
        for location in module.__path__:
            for story_file, submodule_name in story_modules_in_package(Path(location), name):
                story_path = story_file.resolve()
                if story_path in self._seen_files:
                    continue
                self._seen_files.add(story_path)
                if self._guarded_import(str(story_path), submodule_name, partial(importlib.import_module, submodule_name)) is not None:
                    self._record_module(submodule_name)

    def _guarded_import(self, source: str, label: str, action: Callable[[], _T], *, reraise_missing: bool = False) -> _T | None:
        """Run an import, turning any exception raised by the imported code into a ``LoadError`` for ``source``.

        ``ModuleNameTakenError`` always propagates, and with ``reraise_missing`` so does a ``ModuleNotFoundError`` saying that
        ``label`` itself does not exist, so callers can report those in their own words. Returns ``None`` after recording a failure.
        """
        try:
            return action()
        except ModuleNameTakenError:
            raise
        except ModuleNotFoundError as error:
            if reraise_missing and _is_missing(label, error):
                raise
            self.errors.append(_failure(source, label, error))
        except Exception as error:  # noqa: BLE001 - story modules are user code: any error becomes a LoadError with its traceback
            self.errors.append(_failure(source, label, error))
        return None

    def _record_module(self, name: str) -> None:
        if name not in self.modules:
            self.modules.append(name)


def _is_missing(name: str, error: ModuleNotFoundError) -> bool:
    """Whether ``error`` says that ``name`` itself (or one of its parent packages) does not exist."""
    return error.name is not None and (name == error.name or name.startswith(error.name + "."))


def _failure(source: str, label: str, error: BaseException) -> LoadError:
    return LoadError(source, f"Importing {label} failed: {error}", "".join(traceback.format_exception(error)))


__all__ = ["load_stories"]
