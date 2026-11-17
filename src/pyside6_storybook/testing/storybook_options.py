"""``StorybookOptions``: the plugin's command-line options and ini keys, read and checked once (internal)."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from pathlib import Path

import pytest

DEFAULT_QT_WARNINGS_IGNORE = ("propagateSizeHints",)
"""Qt warnings that never fail an item: the offscreen platform logs this one when some widgets are shown."""

QT_WARNINGS_CHOICES = ("fail", "ignore")

MAX_CHANNEL = 255

DEFAULT_SNAPSHOT_DIR = "tests/storybook_snapshots"
"""Where the baselines are, relative to pytest's ``rootpath``."""

DEFAULT_SNAPSHOT_FAILURES = "storybook-snapshot-failures"
"""Where the actual and diff images of a failed snapshot are written, relative to pytest's ``rootpath``."""


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
        snapshots: Whether each story and theme also gets a snapshot item (``--storybook-snapshots``; implied by ``update_snapshots``).
        update_snapshots: Whether a snapshot item writes its baseline instead of comparing (``--storybook-update-snapshots``).
        snapshot_dir: The folder of the baselines (``storybook_snapshot_dir``), absolute.
        snapshot_failures: The folder the actual and diff images of a failure are written to (``storybook_snapshot_failures``), absolute.
        snapshot_tolerance: The largest difference of one channel, from 0 to 255, that still counts as equal.
        snapshot_max_diff: The largest share of differing pixels, from 0 to 1, that still passes.
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
    snapshots: bool = field(default=False, kw_only=True)
    update_snapshots: bool = field(default=False, kw_only=True)
    snapshot_dir: Path = field(default=Path(DEFAULT_SNAPSHOT_DIR), kw_only=True)
    snapshot_failures: Path = field(default=Path(DEFAULT_SNAPSHOT_FAILURES), kw_only=True)
    snapshot_tolerance: int = field(default=0, kw_only=True)
    snapshot_max_diff: float = field(default=0.0, kw_only=True)

    @classmethod
    def from_config(cls, config: pytest.Config) -> StorybookOptions:
        """Read and check the options of a pytest configuration.

        Args:
            config: The configuration whose options and ini values to read.

        Returns:
            The options.

        Raises:
            pytest.UsageError: If a value is malformed: an empty or duplicate theme name, an unknown ``--storybook-qt-warnings`` value,
                a regular expression that does not compile, a contrast ratio outside 1 to 21, a snapshot tolerance outside 0 to 255 or a
                snapshot max diff outside 0 to 1.
        """
        targets = tuple(config.getoption("storybook_stories") or ()) or tuple(config.getini("storybook_stories"))
        provider = config.getoption("storybook_theme_provider") or str(config.getini("storybook_theme_provider")).strip() or None
        themes = _themes(config.getoption("storybook_themes"), "--storybook-themes") or _themes(
            str(config.getini("storybook_themes")), "storybook_themes"
        )
        update = bool(config.getoption("storybook_update_snapshots"))
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
            snapshots=update or bool(config.getoption("storybook_snapshots") or config.getini("storybook_snapshots")),
            update_snapshots=update,
            snapshot_dir=_folder(config, "storybook_snapshot_dir", DEFAULT_SNAPSHOT_DIR),
            snapshot_failures=_folder(config, "storybook_snapshot_failures", DEFAULT_SNAPSHOT_FAILURES),
            snapshot_tolerance=_tolerance(config),
            snapshot_max_diff=_max_diff(config),
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


def _folder(config: pytest.Config, key: str, default: str) -> Path:
    text = str(config.getini(key)).strip() or default
    return Path(config.rootpath, text)


def _tolerance(config: pytest.Config) -> int:
    text = str(config.getini("storybook_snapshot_tolerance")).strip() or "0"
    try:
        value = int(text)
    except ValueError:
        value = -1
    if not 0 <= value <= MAX_CHANNEL:
        raise pytest.UsageError(f"storybook_snapshot_tolerance: {text!r} is not a whole number from 0 to {MAX_CHANNEL}")
    return value


def _max_diff(config: pytest.Config) -> float:
    text = str(config.getini("storybook_snapshot_max_diff")).strip() or "0"
    try:
        value = float(text)
    except ValueError:
        value = math.nan
    if not 0.0 <= value <= 1.0:
        raise pytest.UsageError(f"storybook_snapshot_max_diff: {text!r} is not a share of pixels, a number from 0 to 1")
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


__all__ = ["DEFAULT_QT_WARNINGS_IGNORE", "DEFAULT_SNAPSHOT_DIR", "DEFAULT_SNAPSHOT_FAILURES", "QT_WARNINGS_CHOICES", "StorybookOptions"]
