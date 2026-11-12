"""``load_stories``: import story modules from folders, files and dotted module names."""

from __future__ import annotations

import hashlib
import importlib
import importlib.util
import os
import sys
import traceback
from collections.abc import Callable, Iterable, Iterator
from functools import partial
from pathlib import Path
from types import ModuleType
from typing import TypeVar

from pyside6_storybook import registry as registry_module
from pyside6_storybook.discovery.load_result import LoadError, LoadResult

_STORY_SUFFIXES = ("_story", "_stories")
_SYNTHETIC_PREFIX = "_pyside6_storybook_"
_NOT_FOUND = "no such file, folder or module"
_T = TypeVar("_T")


def load_stories(targets: Iterable[str | os.PathLike[str]], *, cwd: str | os.PathLike[str] | None = None) -> LoadResult:
    """Import the story modules named by ``targets``; their ``@story`` decorators register the stories.

    Each target is, in this order of precedence:

    - an existing folder: every ``*_story.py`` and ``*_stories.py`` file below it is loaded, skipping hidden folders,
      ``__pycache__`` and virtual environments;
    - an existing ``.py`` file: that file is loaded;
    - a dotted module name: the module is imported, and for a package also its submodules named ``*_story`` or ``*_stories``
      in it and in its regular subpackages.

    A file inside a package (its folder has ``__init__.py``) is imported under its full dotted name, with the folder above the
    topmost package on ``sys.path``, so relative imports work and a file reached by path and by module name is one module. A
    file outside any package gets a synthetic module name derived from its path, and its folder is put on ``sys.path`` so it can
    import its siblings. ``cwd`` is put on ``sys.path`` too, as ``python -m`` does, so stories can import the application.

    Importing runs the code in those modules, exactly as running a test suite does.

    Args:
        targets: Folders, files and dotted module names. Relative paths are resolved against ``cwd``. Duplicates are ignored.
        cwd: The working directory; defaults to the process's current directory.

    Returns:
        The registry the stories registered in, the modules loaded, and the targets or files that failed. A failure never stops
        the remaining targets from loading.
    """
    working_directory = Path.cwd() if cwd is None else Path(cwd)
    _prepend_to_sys_path(working_directory.resolve())
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
            for file in _story_files_below(path):
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
            module_name = self._guarded_import(str(path), str(path), partial(_import_file, path))
        except _ModuleNameTakenError as error:
            self.errors.append(LoadError(str(path), str(error)))
            return
        if module_name is not None:
            self._record_module(module_name)

    def _load_dotted_name(self, name: str) -> None:
        if not all(part.isidentifier() for part in name.split(".")):
            self.errors.append(LoadError(name, f"{name}: {_NOT_FOUND}"))
            return
        errors_before = len(self.errors)
        try:
            spec = self._guarded_import(name, name, partial(importlib.util.find_spec, name), reraise_missing=True)
            if spec is None:
                if len(self.errors) == errors_before:
                    self.errors.append(LoadError(name, f"{name}: {_NOT_FOUND}"))
                return
            file = Path(spec.origin).resolve() if spec.has_location and spec.origin else None
            if file is not None and file in self._seen_files:
                return
            module = self._guarded_import(name, name, partial(importlib.import_module, name), reraise_missing=True)
        except ModuleNotFoundError:
            self.errors.append(LoadError(name, f"{name}: {_NOT_FOUND}"))
            return
        if module is None:
            return
        if file is not None:
            self._seen_files.add(file)
        if not hasattr(module, "__path__"):
            self._record_module(name)
            return
        for location in module.__path__:
            for story_file, submodule_name in _story_modules_in_package(Path(location), name):
                story_path = story_file.resolve()
                if story_path in self._seen_files:
                    continue
                self._seen_files.add(story_path)
                if self._guarded_import(str(story_path), submodule_name, partial(importlib.import_module, submodule_name)) is not None:
                    self._record_module(submodule_name)

    def _guarded_import(self, source: str, label: str, action: Callable[[], _T], *, reraise_missing: bool = False) -> _T | None:
        """Run an import, turning any exception raised by the imported code into a ``LoadError`` for ``source``.

        ``_ModuleNameTakenError`` always propagates, and with ``reraise_missing`` so does a ``ModuleNotFoundError`` saying that
        ``label`` itself does not exist, so callers can report those in their own words. Returns ``None`` after recording a failure.
        """
        try:
            return action()
        except _ModuleNameTakenError:
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


class _ModuleNameTakenError(Exception):
    """A story file's module name is already used by a different file."""


def _import_file(path: Path) -> str:
    """Import a story file under its canonical module name and return that name."""
    canonical = _canonical_module_name(path)
    if canonical is None:
        return _import_file_outside_package(path)
    name, sys_path_entry = canonical
    existing = sys.modules.get(name)
    if existing is not None and _module_file(existing) not in (None, path):
        raise _ModuleNameTakenError(f"Cannot import {path} as {name}: that module name already refers to {_module_file(existing)}")
    _prepend_to_sys_path(sys_path_entry)
    module = importlib.import_module(name)
    if _module_file(module) not in (None, path):
        raise _ModuleNameTakenError(f"Cannot import {path} as {name}: that module name refers to {_module_file(module)}")
    return name


def _canonical_module_name(path: Path) -> tuple[str, Path] | None:
    """Return the dotted name of a file inside a package and the folder to put on ``sys.path``, or ``None`` outside a package."""
    parts = [] if path.name == "__init__.py" else [path.stem]
    folder = path.parent
    while (folder / "__init__.py").is_file():
        parts.insert(0, folder.name)
        folder = folder.parent
    if folder == path.parent or not all(part.isidentifier() for part in parts):
        return None
    return ".".join(parts), folder


def _import_file_outside_package(path: Path) -> str:
    digest = hashlib.sha1(str(path).encode("utf-8"), usedforsecurity=False).hexdigest()[:10]
    stem = "".join(character if character.isalnum() or character == "_" else "_" for character in path.stem)
    name = f"{_SYNTHETIC_PREFIX}{stem}_{digest}"
    if name in sys.modules:
        return name
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot create an import spec for {path}")
    _prepend_to_sys_path(path.parent)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    except BaseException:
        del sys.modules[name]
        raise
    return name


def _story_files_below(folder: Path) -> Iterator[Path]:
    """Yield every story file below ``folder`` in a stable order, skipping hidden folders, caches and virtual environments."""
    for directory, subdirectories, files in os.walk(folder):
        here = Path(directory)
        subdirectories[:] = sorted(
            name
            for name in subdirectories
            if not name.startswith(".") and name != "__pycache__" and not (here / name / "pyvenv.cfg").exists()
        )
        for name in sorted(files):
            if _is_story_file_name(name):
                yield here / name


def _story_modules_in_package(folder: Path, package: str) -> Iterator[tuple[Path, str]]:
    """Yield the story files of a package folder and its regular subpackages, with their dotted module names."""
    for entry in sorted(folder.iterdir()):
        if entry.is_dir():
            if entry.name.isidentifier() and (entry / "__init__.py").is_file():
                yield from _story_modules_in_package(entry, f"{package}.{entry.name}")
        elif _is_story_file_name(entry.name) and entry.stem.isidentifier():
            yield entry, f"{package}.{entry.stem}"


def _is_story_file_name(name: str) -> bool:
    return name.endswith(".py") and name[:-3].endswith(_STORY_SUFFIXES)


def _module_file(module: ModuleType) -> Path | None:
    file = getattr(module, "__file__", None)
    return Path(file).resolve() if file else None


def _prepend_to_sys_path(folder: Path) -> None:
    entry = str(folder)
    if entry not in sys.path:
        sys.path.insert(0, entry)


__all__ = ["load_stories"]
