"""The worked example in ``examples/themed_app``, reached only through the command line and ``load_stories``.

The example's package is never imported here at module level: it is put on ``sys.path`` for one test, and its modules are removed
again by the ``stories`` fixture.
"""

import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, cast

import pytest
from PySide6.QtGui import QColor, QFont, QPalette
from PySide6.QtWidgets import QApplication, QPushButton

from pyside6_storybook import StoryRegistry, cli, load_stories
from pyside6_storybook.contrast import contrast_ratio
from pyside6_storybook.gui.window import GalleryWindow
from pyside6_storybook.themes.provider_loader import load_theme_provider

pytestmark = pytest.mark.usefixtures("restore_window_activation")

_EXAMPLE = Path(__file__).resolve().parent.parent / "examples" / "themed_app"
_PROVIDER_SPEC = "themed_app.storybook:provider"
_STORY_IDS = ["Meters/Gauge", "Meters/Empty", "Meters/Full", "Buttons/Pill", "Buttons/Disabled", "Buttons/Pill Row"]
_THEMES = ("Paper", "Ink")
_MINIMUM_CONTRAST = 4.5


def test_list_names_the_stories_the_provider_and_both_themes(
    stories: StoryRegistry, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(_EXAMPLE)

    assert cli.main(["--list"]) == 0

    captured = capsys.readouterr()
    assert captured.out.splitlines() == _STORY_IDS
    assert f"pyside6-storybook: theme provider {_PROVIDER_SPEC} (themes: Paper, Ink)" in captured.err.splitlines()


@pytest.fixture
def example_stories(stories: StoryRegistry, monkeypatch: pytest.MonkeyPatch) -> StoryRegistry:
    """The example's stories, loaded into the isolated default registry with the example folder on ``sys.path``."""
    monkeypatch.syspath_prepend(str(_EXAMPLE))
    result = load_stories([_EXAMPLE / "themed_app" / "stories"], cwd=_EXAMPLE)
    assert result.errors == ()
    return stories


def _pixel(widget: QPushButton, x: int) -> str:
    image = widget.grab().toImage()
    return image.pixelColor(x, image.height() // 2).name()


def test_switching_theme_restyles_both_widgets_and_the_application_is_restored(
    qtbot, qapp: QApplication, restore_application_look: None, example_stories: StoryRegistry
) -> None:
    palette, style_sheet, font = QPalette(qapp.palette()), qapp.styleSheet(), QFont(qapp.font())
    provider = load_theme_provider(_PROVIDER_SPEC).provider
    provider.activate(qapp)
    try:
        window = GalleryWindow(example_stories, provider)
        qtbot.addWidget(window)
        window.resize(1000, 700)
        window.show()
        seen: dict[str, dict[str, str]] = {}
        for theme in _THEMES:
            window.set_theme(theme)
            tokens = {str(key): str(value) for key, value in cast(Any, provider).tokens().items()}  # tokens() is optional, so not on ThemeProvider
            assert {"accent", "surface", "text", "track"} <= set(tokens)
            colors: dict[str, str] = {}
            for story_id in _STORY_IDS:
                assert window.select_story(story_id)
                widget = window.current_preview_widget()
                assert widget is not None
                pill = widget if isinstance(widget, QPushButton) else widget.findChild(QPushButton)
                if pill is not None:
                    if pill.isEnabled():
                        colors["pill"] = _pixel(pill, 10)
                        assert colors["pill"] == tokens["accent"]
                    continue
                image = widget.grab().toImage()
                bar_end = widget.width() - widget.fontMetrics().horizontalAdvance("100%") - 8
                if story_id != "Meters/Empty":
                    colors["fill"] = image.pixelColor(3, image.height() // 2).name()
                    assert colors["fill"] == tokens["accent"]
                if story_id != "Meters/Full":
                    colors["track"] = image.pixelColor(bar_end - 4, image.height() // 2).name()
                    assert colors["track"] == tokens["track"]
            seen[theme] = colors
        assert seen["Paper"]["pill"] != seen["Ink"]["pill"]
        assert seen["Paper"]["fill"] != seen["Ink"]["fill"]
        assert seen["Paper"]["track"] != seen["Ink"]["track"]
    finally:
        provider.deactivate()

    assert qapp.palette() == palette
    assert qapp.styleSheet() == style_sheet
    assert qapp.font() == font


@pytest.mark.parametrize("theme", _THEMES)
def test_each_theme_palette_is_readable(qapp: QApplication, restore_application_look: None, example_stories: StoryRegistry, theme: str) -> None:
    provider = load_theme_provider(_PROVIDER_SPEC).provider
    provider.activate(qapp)
    try:
        provider.set_theme(theme)
        palette = qapp.palette()
        for group in (QPalette.ColorGroup.Active, QPalette.ColorGroup.Inactive):
            for text, background in (
                (QPalette.ColorRole.WindowText, QPalette.ColorRole.Window),
                (QPalette.ColorRole.Text, QPalette.ColorRole.Base),
                (QPalette.ColorRole.ButtonText, QPalette.ColorRole.Button),
                (QPalette.ColorRole.HighlightedText, QPalette.ColorRole.Highlight),
            ):
                ratio = contrast_ratio(palette.color(group, text).name(QColor.NameFormat.HexRgb), palette.color(group, background).name())
                assert ratio >= _MINIMUM_CONTRAST, (theme, group, text, background, ratio)
    finally:
        provider.deactivate()


@pytest.mark.full
def test_the_installed_command_lists_the_example() -> None:
    command = shutil.which("pyside6-storybook")
    assert command is not None
    environment = {**os.environ, "QT_QPA_PLATFORM": "offscreen"}

    completed = subprocess.run([command, "--list"], cwd=_EXAMPLE, env=environment, capture_output=True, text=True, timeout=60, check=False)

    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.splitlines() == _STORY_IDS
    assert _PROVIDER_SPEC in completed.stderr
    assert "Paper, Ink" in completed.stderr
