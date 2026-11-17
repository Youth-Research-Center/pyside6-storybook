import re

import pytest

from pyside6_storybook import StoryRegistry
from pyside6_storybook.testing.storybook_options import StorybookOptions


def _options(pytester: pytest.Pytester, *args: str, ini: str = "") -> StorybookOptions:
    pytester.makepyprojecttoml(f"[tool.pytest.ini_options]\n{ini}\n")
    return StorybookOptions.from_config(pytester.parseconfig(*args))


def test_the_defaults_turn_the_plugin_off_and_fail_on_qt_warnings(pytester: pytest.Pytester, stories: StoryRegistry) -> None:
    options = _options(pytester)

    assert options.enabled is False
    assert options.targets == ()
    assert options.theme_provider is None
    assert options.themes is None
    assert options.qt_warnings_fail is True
    assert [pattern.pattern for pattern in options.qt_warnings_ignore] == ["propagateSizeHints"]
    assert options.a11y is False
    assert (options.contrast, options.contrast_normal, options.contrast_large, options.contrast_disabled) == (True, 4.5, 3.0, False)


def test_the_a11y_option_and_ini_key_turn_the_accessibility_items_on(pytester: pytest.Pytester, stories: StoryRegistry) -> None:
    assert _options(pytester, "--storybook-a11y").a11y is True
    assert _options(pytester, ini="storybook_a11y = true").a11y is True


def test_the_contrast_options_and_ini_keys(pytester: pytest.Pytester, stories: StoryRegistry) -> None:
    assert _options(pytester, "--storybook-no-contrast").contrast is False
    assert _options(pytester, ini="storybook_contrast = false").contrast is False
    assert _options(pytester, "--storybook-contrast-disabled").contrast_disabled is True
    assert _options(pytester, ini="storybook_contrast_disabled = true").contrast_disabled is True
    options = _options(pytester, ini='storybook_contrast_normal = "7"\nstorybook_contrast_large = "4.5"')
    assert (options.contrast_normal, options.contrast_large) == (7.0, 4.5)


@pytest.mark.parametrize("value", ["abc", "0.5", "22", "nan", ""])
@pytest.mark.parametrize("key", ["storybook_contrast_normal", "storybook_contrast_large"])
def test_a_contrast_threshold_that_is_not_a_ratio_is_a_usage_error(pytester: pytest.Pytester, stories: StoryRegistry, key: str, value: str) -> None:
    with pytest.raises(pytest.UsageError, match=f"{key}: .* is not a contrast ratio"):
        _options(pytester, ini=f'{key} = "{value}"')


def test_every_ini_key_is_read(pytester: pytest.Pytester, stories: StoryRegistry) -> None:
    options = _options(
        pytester,
        ini="""
storybook = true
storybook_stories = ["a", "b.c"]
storybook_theme_provider = "app.theme:provider"
storybook_themes = "Light, Dark"
storybook_qt_warnings = "ignore"
storybook_qt_warnings_ignore = ["one", "two"]
""",
    )

    assert options.enabled is True
    assert options.targets == ("a", "b.c")
    assert options.theme_provider == "app.theme:provider"
    assert options.themes == ("Light", "Dark")
    assert options.qt_warnings_fail is False
    assert [pattern.pattern for pattern in options.qt_warnings_ignore] == ["one", "two"]


def test_the_command_line_wins_over_the_ini_file(pytester: pytest.Pytester, stories: StoryRegistry) -> None:
    options = _options(
        pytester,
        "--storybook-stories",
        "cli_one",
        "--storybook-stories",
        "cli_two",
        "--storybook-theme-provider",
        "cli:provider",
        "--storybook-themes",
        "Dark",
        "--storybook-qt-warnings",
        "fail",
        ini="""
storybook_stories = ["ini"]
storybook_theme_provider = "ini:provider"
storybook_themes = "Light"
storybook_qt_warnings = "ignore"
""",
    )

    assert options.targets == ("cli_one", "cli_two")
    assert options.theme_provider == "cli:provider"
    assert options.themes == ("Dark",)
    assert options.qt_warnings_fail is True


@pytest.mark.parametrize("value", [",Dark", "Light,,Dark", "Light, "])
def test_an_empty_theme_name_is_a_usage_error(pytester: pytest.Pytester, stories: StoryRegistry, value: str) -> None:
    with pytest.raises(pytest.UsageError, match=r"--storybook-themes: .* has an empty theme name"):
        _options(pytester, "--storybook-themes", value)


def test_a_theme_listed_twice_is_a_usage_error(pytester: pytest.Pytester, stories: StoryRegistry) -> None:
    with pytest.raises(pytest.UsageError, match="storybook_themes: Dark listed more than once"):
        _options(pytester, ini='storybook_themes = "Dark,Light,Dark"')


def test_an_unknown_qt_warnings_value_in_the_ini_file_is_a_usage_error(pytester: pytest.Pytester, stories: StoryRegistry) -> None:
    with pytest.raises(pytest.UsageError, match=re.escape("storybook_qt_warnings: 'warn' is not one of fail, ignore")):
        _options(pytester, ini='storybook_qt_warnings = "warn"')


def test_an_ignore_pattern_that_is_not_a_regular_expression_is_a_usage_error(pytester: pytest.Pytester, stories: StoryRegistry) -> None:
    with pytest.raises(pytest.UsageError, match=r"storybook_qt_warnings_ignore: '\(' is not a valid regular expression"):
        _options(pytester, ini='storybook_qt_warnings_ignore = ["("]')


def test_the_snapshot_defaults(pytester: pytest.Pytester, stories: StoryRegistry) -> None:
    options = _options(pytester)

    assert (options.snapshots, options.update_snapshots, options.snapshot_tolerance, options.snapshot_max_diff) == (False, False, 0, 0.0)
    assert options.snapshot_dir == pytester.path / "tests" / "storybook_snapshots"
    assert options.snapshot_failures == pytester.path / "storybook-snapshot-failures"


def test_the_snapshot_options_and_ini_keys(pytester: pytest.Pytester, stories: StoryRegistry) -> None:
    assert _options(pytester, "--storybook-snapshots").snapshots is True
    assert _options(pytester, ini="storybook_snapshots = true").snapshots is True
    updating = _options(pytester, "--storybook-update-snapshots")
    assert (updating.snapshots, updating.update_snapshots) == (True, True)
    options = _options(
        pytester,
        ini="""
storybook_snapshot_dir = "baselines"
storybook_snapshot_failures = "out/failures"
storybook_snapshot_tolerance = "12"
storybook_snapshot_max_diff = "0.25"
""",
    )
    assert options.snapshot_dir == pytester.path / "baselines"
    assert options.snapshot_failures == pytester.path / "out" / "failures"
    assert (options.snapshot_tolerance, options.snapshot_max_diff) == (12, 0.25)


@pytest.mark.parametrize("value", ["-1", "256", "1.5", "abc"])
def test_a_snapshot_tolerance_outside_0_to_255_is_a_usage_error(pytester: pytest.Pytester, stories: StoryRegistry, value: str) -> None:
    with pytest.raises(pytest.UsageError, match="storybook_snapshot_tolerance: .* is not a whole number from 0 to 255"):
        _options(pytester, ini=f'storybook_snapshot_tolerance = "{value}"')


@pytest.mark.parametrize("value", ["-0.1", "1.1", "abc", "nan"])
def test_a_snapshot_max_diff_outside_0_to_1_is_a_usage_error(pytester: pytest.Pytester, stories: StoryRegistry, value: str) -> None:
    with pytest.raises(pytest.UsageError, match="storybook_snapshot_max_diff: .* is not a share of pixels, a number from 0 to 1"):
        _options(pytester, ini=f'storybook_snapshot_max_diff = "{value}"')
