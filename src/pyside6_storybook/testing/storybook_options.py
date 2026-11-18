"""``StorybookOptions``: the plugin's command-line options and ini keys, read and checked once (internal)."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field

import pytest

DEFAULT_QT_WARNINGS_IGNORE = ("propagateSizeHints",)
"""Qt warnings that never fail an item: the offscreen platform logs this one when some widgets are shown."""

QT_WARNINGS_CHOICES = ("fail", "ignore")


@dataclass(frozen=True, slots=True)
class StorybookOptions:
    """What the command line and the ini file say about the plugin; the command line wins.

    Attributes:
        enabled: Whether the plugin collects story items (``--storybook`` or ``storybook = true``).
        targets: Story targets from ``--storybook-stories`` or ``storybook_stories``; empty to use ``[tool.pyside6-storybook]``.
        theme_provider: The ``module:attribute`` of the theme provider, or ``None`` for the project's ``theme_provider`` or the built-in
            themes.
        themes: The themes to render each story in, or ``None`` for every theme the provider lists.
        qt_warnings_fail: Whether a Qt warning logged during a render fails the item.
        qt_warnings_ignore: Patterns (searched in the message) of the warnings that never fail.
        a11y: Whether each story also gets the accessible-name and keyboard-focus items (``--storybook-a11y``).
        contrast: Whether ``a11y`` also adds a text-contrast item per story and theme; off with ``--storybook-no-contrast``.
        contrast_normal: The contrast ratio normal text needs (``storybook_contrast_normal``).
        contrast_large: The contrast ratio large text needs (``storybook_contrast_large``).
        contrast_disabled: Whether the contrast check includes disabled widgets (``--storybook-contrast-disabled``).
    """

    enabled: bool
    targets: tuple[str, ...]
    theme_provider: str | None
    themes: tuple[str, ...] | None
    qt_warnings_fail: bool
    qt_warnings_ignore: tuple[re.Pattern[str], ...]
    a11y: bool = field(default=False, kw_only=True)
    contrast: bool = field(default=True, kw_only=True)
    contrast_normal: float = field(default=4.5, kw_only=True)
    contrast_large: float = field(default=3.0, kw_only=True)
    contrast_disabled: bool = field(default=False, kw_only=True)

    @classmethod
    def from_config(cls, config: pytest.Config) -> StorybookOptions:
        """Read and check the options of a pytest configuration.

        Args:
            config: The configuration whose options and ini values to read.

        Returns:
            The options.

        Raises:
            pytest.UsageError: If a value is malformed: an empty or duplicate theme name, an unknown ``--storybook-qt-warnings`` value,
                or a regular expression that does not compile.
        """
        targets = tuple(config.getoption("storybook_stories") or ()) or tuple(config.getini("storybook_stories"))
        provider = config.getoption("storybook_theme_provider") or str(config.getini("storybook_theme_provider")).strip() or None
        themes = _themes(config.getoption("storybook_themes"), "--storybook-themes") or _themes(
            str(config.getini("storybook_themes")), "storybook_themes"
        )
        warnings = config.getoption("storybook_qt_warnings") or str(config.getini("storybook_qt_warnings")).strip() or "fail"
        if warnings not in QT_WARNINGS_CHOICES:
            raise pytest.UsageError(f"storybook_qt_warnings: {warnings!r} is not one of {', '.join(QT_WARNINGS_CHOICES)}")
        return cls(
            enabled=bool(config.getoption("storybook") or config.getini("storybook")),
            targets=targets,
            theme_provider=provider,
            themes=themes,
            qt_warnings_fail=warnings == "fail",
            qt_warnings_ignore=_patterns(config.getini("storybook_qt_warnings_ignore")),
            a11y=bool(config.getoption("storybook_a11y") or config.getini("storybook_a11y")),
            contrast=not config.getoption("storybook_no_contrast") and bool(config.getini("storybook_contrast")),
            contrast_normal=_ratio(config, "storybook_contrast_normal"),
            contrast_large=_ratio(config, "storybook_contrast_large"),
            contrast_disabled=bool(config.getoption("storybook_contrast_disabled") or config.getini("storybook_contrast_disabled")),
        )


def _ratio(config: pytest.Config, key: str) -> float:
    text = str(config.getini(key)).strip()
    try:
        value = float(text)
    except ValueError:
        value = math.nan
    if not 1.0 <= value <= 21.0:
        raise pytest.UsageError(f"{key}: {text!r} is not a contrast ratio, a number from 1 to 21")
    return value


def _themes(value: str | None, source: str) -> tuple[str, ...] | None:
    if value is None or not value.strip():
        return None
    names = tuple(name.strip() for name in value.split(","))
    if not all(names):
        raise pytest.UsageError(f"{source}: {value!r} has an empty theme name; expected comma-separated names such as Light,Dark")
    duplicates = sorted({name for name in names if names.count(name) > 1})
    if duplicates:
        raise pytest.UsageError(f"{source}: {', '.join(duplicates)} listed more than once")
    return names


def _patterns(values: list[str]) -> tuple[re.Pattern[str], ...]:
    patterns = []
    for value in values:
        try:
            patterns.append(re.compile(value))
        except re.error as error:
            raise pytest.UsageError(f"storybook_qt_warnings_ignore: {value!r} is not a valid regular expression: {error}") from error
    return tuple(patterns)


__all__ = ["DEFAULT_QT_WARNINGS_IGNORE", "QT_WARNINGS_CHOICES", "StorybookOptions"]
