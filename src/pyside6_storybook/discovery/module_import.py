"""Importing one story file under the module name that keeps it a single module.

A file inside a package is imported under its full dotted name, with the folder above the topmost package on ``sys.path``.
A file outside any package is imported under its own name, with its folder on ``sys.path``, so a sibling story that imports it
shares the module; only when that name is taken by another file does it get a synthetic name derived from its path. Before a
file is executed, the name it would be imported under is checked to resolve to that very file, so a clash never runs the wrong
file.
"""

from __future__ import annotations

import hashlib
import importlib
import importlib.util
import os
import sys
from importlib.machinery import ModuleSpec
from pathlib import Path
from types import ModuleType

from pyside6_storybook.discovery.constants import SYNTHETIC_MODULE_PREFIX


class ModuleNameTakenError(Exception):
    """A story file's module name already refers to a different file."""


def import_file(path: Path) -> str:
    """Import a story file once and return the name of its module.

    Args:
        path: The resolved path of the file.

    Returns:
        The module name the file is imported under, or was already imported under.

    Raises:
        ModuleNameTakenError: If the file's dotted name refers to a different file; nothing is executed in that case.
    """
    already_loaded = loaded_module_name(path)
    if already_loaded is not None:
        return already_loaded
    canonical = canonical_module_name(path)
    if canonical is None:
        return _import_file_outside_package(path)
    name, sys_path_entry = canonical
    existing = sys.modules.get(name)
    if existing is not None:
        raise ModuleNameTakenError(f"Cannot import {path} as {name}: that module name already refers to {module_file(existing)}")
    prepend_to_sys_path(sys_path_entry)
    resolved = spec_file(importlib.util.find_spec(name))
    if resolved != path:
        raise ModuleNameTakenError(f"Cannot import {path} as {name}: {_resolution_description(name, resolved)}")
    importlib.import_module(name)
    return name


def canonical_module_name(path: Path) -> tuple[str, Path] | None:
    """Return the dotted name of a file inside a package and the folder to put on ``sys.path``, or ``None`` outside a package."""
    parts = [] if path.name == "__init__.py" else [path.stem]
    folder = path.parent
    while (folder / "__init__.py").is_file():
        parts.insert(0, folder.name)
        folder = folder.parent
    if folder == path.parent or not all(part.isidentifier() for part in parts):
        return None
    return ".".join(parts), folder


def loaded_module_name(path: Path) -> str | None:
    """Return the name of an already imported module whose file is ``path``, if there is one."""
    for name, module in list(sys.modules.items()):
        file = getattr(module, "__file__", None)
        if file and os.path.basename(file) == path.name and Path(file).resolve() == path:
            return name
    return None


def module_file(module: ModuleType) -> Path | None:
    """Return the resolved path of a module's file, or ``None`` for a module without one."""
    file = getattr(module, "__file__", None)
    return Path(file).resolve() if file else None


def spec_file(spec: ModuleSpec | None) -> Path | None:
    """Return the resolved path a module spec would load from, or ``None`` if it has no file."""
    if spec is None or not spec.has_location or not spec.origin:
        return None
    return Path(spec.origin).resolve()


def prepend_to_sys_path(folder: Path) -> None:
    """Put ``folder`` at the front of ``sys.path`` unless it is already on it."""
    entry = str(folder)
    if entry not in sys.path:
        sys.path.insert(0, entry)


def _import_file_outside_package(path: Path) -> str:
    prepend_to_sys_path(path.parent)
    name = path.stem
    if name.isidentifier() and name not in sys.modules and spec_file(importlib.util.find_spec(name)) == path:
        importlib.import_module(name)
        return name
    return _import_under_synthetic_name(path)


def _import_under_synthetic_name(path: Path) -> str:
    digest = hashlib.sha1(str(path).encode("utf-8"), usedforsecurity=False).hexdigest()[:10]
    stem = "".join(character if character.isalnum() or character == "_" else "_" for character in path.stem)
    name = f"{SYNTHETIC_MODULE_PREFIX}{stem}_{digest}"
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot create an import spec for {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    except BaseException:
        del sys.modules[name]
        raise
    return name


def _resolution_description(name: str, resolved: Path | None) -> str:
    if resolved is not None:
        return f"that module name refers to {resolved}"
    package = sys.modules.get(name.rpartition(".")[0])
    location = getattr(package, "__path__", None) if package is not None else None
    return f"its package is already imported from {list(location) if location else 'elsewhere'}"


__all__ = [
    "ModuleNameTakenError",
    "canonical_module_name",
    "import_file",
    "loaded_module_name",
    "module_file",
    "prepend_to_sys_path",
    "spec_file",
]
