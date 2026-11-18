"""Read a theme provider's optional ``tokens()`` and ``color_scheme()``, checking what they return (internal).

The gallery window and the pytest plugin read these two values the same way. The helpers raise when the provider's method raises or
returns the wrong type; each caller decides what that means (the window shows the error and falls back, a story item fails).
"""

from __future__ import annotations

from collections.abc import Mapping

from PySide6.QtCore import Qt

from pyside6_storybook.themes.provider import ThemeProvider


def read_tokens(provider: ThemeProvider) -> Mapping[str, object]:
    """Return the provider's design tokens.

    Args:
        provider: The theme provider.

    Returns:
        The mapping ``tokens()`` returned, or an empty mapping for a provider without a ``tokens`` method.

    Raises:
        TypeError: If ``tokens()`` does not return a mapping.
        Exception: Whatever ``tokens()`` raises.
    """
    read = getattr(provider, "tokens", None)
    if read is None:
        return {}
    result = read()
    if not isinstance(result, Mapping):
        raise TypeError(f"tokens() returned {type(result).__name__}, expected a mapping")
    return result


def read_color_scheme(provider: ThemeProvider) -> Qt.ColorScheme | None:
    """Return the provider's colour scheme.

    Args:
        provider: The theme provider.

    Returns:
        The ``Qt.ColorScheme`` ``color_scheme()`` returned, or ``None`` for a provider without a ``color_scheme`` method.

    Raises:
        TypeError: If ``color_scheme()`` does not return a ``Qt.ColorScheme``.
        Exception: Whatever ``color_scheme()`` raises.
    """
    read = getattr(provider, "color_scheme", None)
    if read is None:
        return None
    value = read()
    if not isinstance(value, Qt.ColorScheme):
        raise TypeError(f"color_scheme() returned {type(value).__name__}, expected a Qt.ColorScheme")
    return value


__all__ = ["read_color_scheme", "read_tokens"]
