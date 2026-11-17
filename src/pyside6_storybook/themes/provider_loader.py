"""Load a theme provider from a ``module:attribute`` spec, as ``--theme-provider`` and ``theme_provider`` in ``pyproject.toml`` name it."""

from __future__ import annotations

import importlib
import sys
from dataclasses import dataclass
from typing import cast

from pyside6_storybook.themes.provider import ThemeProvider

PROTOCOL_METHODS = ("theme_names", "current_theme", "activate", "set_theme", "on_changed", "deactivate")
"""The methods of ``ThemeProvider``; each must be callable on a loaded provider."""


class ThemeProviderError(Exception):
    """A theme provider spec cannot be loaded; the message names the spec."""


@dataclass(frozen=True, slots=True)
class LoadedProvider:
    """A loaded theme provider.

    Attributes:
        provider: The provider object.
        modules: The ``sys.modules`` names that importing the module and calling the attribute added, which a reload keeps.
    """

    provider: ThemeProvider
    modules: tuple[str, ...]


def load_theme_provider(spec: str) -> LoadedProvider:
    """Import ``module:attribute`` and return the provider it names.

    The attribute may be dotted (``app.theming:Theme.provider``). It is kept as it is when it is an instance, and called with no
    arguments when it is a class or a callable that lacks a protocol method (a factory function). The kept object must have every
    method of ``ThemeProvider`` as a callable attribute. Call this once the ``QApplication`` exists, because a factory may create
    widgets.

    Args:
        spec: ``module:attribute``.

    Returns:
        The provider and the names of the modules the import and the call added to ``sys.modules``.

    Raises:
        ThemeProviderError: If the spec is malformed, the module cannot be imported, the attribute is missing, the factory raises, or
            the result lacks a protocol method. The message names the spec.
    """
    module_name, separator, attribute = spec.partition(":")
    if not separator or not module_name or not attribute or ":" in attribute:
        raise ThemeProviderError(f"theme provider {spec!r}: expected 'module:attribute'")
    before = set(sys.modules)
    try:
        module = importlib.import_module(module_name)
    except Exception as error:
        raise ThemeProviderError(f"theme provider {spec!r}: module '{module_name}' cannot be imported: {_describe(error)}") from error
    target: object = module
    for part in attribute.split("."):
        try:
            target = getattr(target, part)
        except AttributeError as error:
            raise ThemeProviderError(f"theme provider {spec!r}: module '{module_name}' has no attribute '{attribute}'") from error
        except Exception as error:
            raise ThemeProviderError(f"theme provider {spec!r}: reading '{attribute}' failed: {_describe(error)}") from error
    if isinstance(target, type) or (callable(target) and _missing_methods(target)):
        try:
            target = target()
        except Exception as error:
            raise ThemeProviderError(f"theme provider {spec!r}: calling '{attribute}' failed: {_describe(error)}") from error
    missing = _missing_methods(target)
    if missing:
        raise ThemeProviderError(f"theme provider {spec!r}: the result is not a ThemeProvider; missing or not callable: {', '.join(missing)}")
    modules = tuple(sorted(set(sys.modules) - before))
    return LoadedProvider(provider=cast(ThemeProvider, target), modules=modules)


def _missing_methods(candidate: object) -> list[str]:
    return [name for name in PROTOCOL_METHODS if not callable(getattr(candidate, name, None))]


def _describe(error: Exception) -> str:
    return f"{type(error).__name__}: {error}"


__all__ = ["PROTOCOL_METHODS", "LoadedProvider", "ThemeProviderError", "load_theme_provider"]
