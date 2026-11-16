"""``ReloadSession``: load the same targets again into a fresh registry, keeping the old state when the new load is not usable.

A reload drops the modules the project owns from ``sys.modules`` (the story modules of the last accepted load, their parent packages,
and every other module that lives under the working directory or a ``pythonpath`` folder), points both bindings of the default
registry at a new ``StoryRegistry`` and runs ``load_stories`` again, so every module executes again in import order and an edited
widget class is picked up like an edited story. The result is accepted when it has a story and no source failed that did not already
fail; otherwise the modules and the registry bindings are put back.
"""

from __future__ import annotations

import importlib
import importlib.util
import logging
import os
import sys
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType

import pyside6_storybook
from pyside6_storybook import registry as registry_module
from pyside6_storybook.discovery.file_search import folders_below, story_files_below, story_modules_in_package
from pyside6_storybook.discovery.load_result import LoadError, LoadResult
from pyside6_storybook.discovery.loader import load_stories
from pyside6_storybook.discovery.module_import import module_file, spec_file
from pyside6_storybook.registry import StoryRegistry

_LIBRARY_PACKAGE = "pyside6_storybook"
_LIBRARY_ROOT = Path(pyside6_storybook.__file__).resolve().parent
_EXCLUDED_FOLDERS = frozenset({"site-packages", "dist-packages", ".venv", "venv", "node_modules"})


@dataclass(frozen=True, slots=True)
class ReloadResult:
    """The outcome of ``ReloadSession.reload``.

    Attributes:
        load: What ``load_stories`` returned for the reload. When the reload was rejected its registry is not the one in use.
        accepted: Whether the new registry replaces the old one.
        new_errors: The errors of ``load`` whose source was not failing in the last accepted load.
    """

    load: LoadResult
    accepted: bool
    new_errors: tuple[LoadError, ...]


class ReloadSession:
    """What a reload needs to know: the targets, the folders the project lives in and the last accepted load."""

    def __init__(
        self,
        targets: Sequence[str],
        *,
        cwd: str | os.PathLike[str],
        pythonpath: Sequence[str | os.PathLike[str]] = (),
        initial: LoadResult,
    ) -> None:
        """Create a session.

        Args:
            targets: The targets given to ``load_stories``.
            cwd: The working directory the targets are resolved against.
            pythonpath: The configured ``pythonpath`` folders; modules below them are reloaded too.
            initial: The first load, which is the baseline for the modules to drop, the errors that may keep failing and the files to watch.
        """
        self._logger = logging.getLogger(self.__class__.__name__)
        self._targets = tuple(targets)
        self._cwd = Path(cwd).resolve()
        self._roots = (self._cwd, *(Path(folder).resolve() for folder in pythonpath))
        self._last = initial

    @property
    def targets(self) -> tuple[str, ...]:
        """The targets that are loaded again on every reload."""
        return self._targets

    @property
    def last_accepted(self) -> LoadResult:
        """The last accepted load: the initial one until a reload is accepted."""
        return self._last

    def reload(self) -> ReloadResult:
        """Load the targets again into a new registry and decide whether to keep it.

        Runs on the calling thread, because the story modules may create widgets. If ``load_stories`` raises something it does not
        catch (``SystemExit`` from a story module), the modules and registry bindings are restored and the exception propagates.

        Returns:
            The new load and whether it was accepted. It is accepted when it found at least one story and every source in its errors was
            already failing in the last accepted load; then ``last_accepted`` is the new load. Otherwise the previous modules and
            registry are back in place.
        """
        before = set(sys.modules)
        dropped = self._managed_names(self._last.modules)
        snapshot = {name: sys.modules[name] for name in dropped}
        bindings = (registry_module.default_registry, pyside6_storybook.default_registry)
        files = [module_file(module) for module in snapshot.values()]
        for name in dropped:
            del sys.modules[name]
        fresh = StoryRegistry()
        _bind_registry(fresh)
        for file in files:
            self._delete_bytecode(file)
        importlib.invalidate_caches()
        try:
            load = load_stories(self._targets, cwd=self._cwd)
        except BaseException:
            self._restore(snapshot, bindings, before, ())
            raise
        failing = {error.source for error in self._last.errors}
        new_errors = tuple(error for error in load.errors if error.source not in failing)
        if len(load.registry) > 0 and not new_errors:
            self._last = load
            return ReloadResult(load, accepted=True, new_errors=())
        self._restore(snapshot, bindings, before, load.modules)
        return ReloadResult(load, accepted=False, new_errors=new_errors)

    def watched_files(self) -> frozenset[Path]:
        """Return the files a change to which should reload: the project's modules and every story source, whether or not it imported.

        The modules are those a reload would drop. The story sources are the file targets, the story files below the folder targets and
        the story modules of the package targets, found on disk, so a story file that fails to import is still watched.
        """
        files = {file for module in self._managed_modules(self._last.modules).values() if (file := module_file(module)) is not None}
        files |= self._source_files()
        return frozenset(file for file in files if file.is_file())

    def folder_targets(self) -> tuple[Path, ...]:
        """Return the targets that are existing folders, resolved against the working directory."""
        folders = []
        for target in self._targets:
            path = self._resolve(target)
            if path.is_dir():
                folders.append(path.resolve())
        return tuple(folders)

    def watched_folders(self) -> frozenset[Path]:
        """Return every folder below each folder target, and the targets themselves; a folder watch is not recursive."""
        return frozenset(folder.resolve() for target in self.folder_targets() for folder in folders_below(target))

    def story_file_set(self) -> frozenset[Path]:
        """Return the story files below the folder targets, to tell a new or removed story file from an editor's swap file."""
        return frozenset(file.resolve() for target in self.folder_targets() for file in story_files_below(target))

    def _resolve(self, target: str) -> Path:
        path = Path(target)
        return path if path.is_absolute() else self._cwd / path

    def _source_files(self) -> set[Path]:
        files: set[Path] = set()
        for target in self._targets:
            path = self._resolve(target)
            if path.is_dir():
                files.update(file.resolve() for file in story_files_below(path))
            elif path.is_file():
                files.add(path.resolve())
            else:
                files |= self._package_files(target)
        return files

    def _package_files(self, name: str) -> set[Path]:
        if not all(part.isidentifier() for part in name.split(".")):
            return set()
        try:
            spec = importlib.util.find_spec(name)
        except Exception:
            self._logger.debug("Could not find the module spec of %s", name, exc_info=True)
            return set()
        if spec is None:
            return set()
        files = set()
        origin = spec_file(spec)
        if origin is not None:
            files.add(origin)
        for location in spec.submodule_search_locations or ():
            folder = Path(location)
            if folder.is_dir():
                files.update(file.resolve() for file, _module in story_modules_in_package(folder, name))
        return files

    def _managed_names(self, modules: Iterable[str]) -> set[str]:
        return set(self._managed_modules(modules))

    def _managed_modules(self, modules: Iterable[str]) -> dict[str, ModuleType]:
        """Return the imported modules a reload owns: the named ones with their parent packages, and the project's own modules."""
        names: set[str] = set()
        for name in modules:
            parts = name.split(".")
            for length in range(1, len(parts) + 1):
                if length == len(parts) or parts[0] != _LIBRARY_PACKAGE:
                    names.add(".".join(parts[:length]))
        found = {name: sys.modules[name] for name in names if name in sys.modules}
        for name, module in list(sys.modules.items()):
            if name not in found and name != "__main__" and self._is_project_module(module):
                found[name] = module
        return found

    def _is_project_module(self, module: ModuleType) -> bool:
        if getattr(module, "__file__", None) is None:
            return False
        file = module_file(module)
        if file is None or file.is_relative_to(_LIBRARY_ROOT):
            return False
        for root in self._roots:
            if file.is_relative_to(root):
                parts = file.relative_to(root).parts
                if not any(part in _EXCLUDED_FOLDERS or part.startswith(".") for part in parts):
                    return True
        return False

    def _delete_bytecode(self, file: Path | None) -> None:
        """Delete the cached bytecode of a source file, because a timestamp-based ``.pyc`` can outlive a same-size edit in the same second."""
        if file is None or file.suffix != ".py":
            return
        try:
            os.remove(importlib.util.cache_from_source(str(file)))
        except (FileNotFoundError, NotImplementedError):
            pass
        except OSError:
            self._logger.warning("Could not delete the bytecode cache of %s", file, exc_info=True)

    def _restore(
        self, snapshot: dict[str, ModuleType], bindings: tuple[StoryRegistry, StoryRegistry], before: set[str], loaded: Iterable[str]
    ) -> None:
        """Put the dropped modules and both registry bindings back, and forget what the rejected attempt imported."""
        for name in self._managed_names(loaded):
            if name not in before:
                sys.modules.pop(name, None)
        sys.modules.update(snapshot)
        registry_module.default_registry, pyside6_storybook.default_registry = bindings


def _bind_registry(registry: StoryRegistry) -> None:
    registry_module.default_registry = registry
    pyside6_storybook.default_registry = registry


__all__ = ["ReloadResult", "ReloadSession"]
