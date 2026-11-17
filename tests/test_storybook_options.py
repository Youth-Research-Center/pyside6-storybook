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
