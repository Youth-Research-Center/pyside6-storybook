import logging
from collections.abc import Mapping

import pytest
from fake_providers import RaisingProvider, StyleSheetProvider
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication, QLabel, QWidget

from pyside6_storybook import BuiltinThemeProvider, StoryContext, StoryRegistry, TextControl, ThemeProvider
from pyside6_storybook.cli import EXAMPLES_MODULE
from pyside6_storybook.discovery import load_stories
from pyside6_storybook.gui.error_panel import ErrorPanel
from pyside6_storybook.gui.window import GalleryWindow

_TOKEN_NAMES = {
    "window",
    "window_text",
    "base",
    "alternate_base",
    "text",
    "button",
    "button_text",
    "highlight",
    "highlighted_text",
    "accent",
    "border",
    "placeholder_text",
}


class _NoTokensProvider:
    """A provider that implements only the protocol's six methods."""

    def __init__(self, inner: StyleSheetProvider) -> None:
        self._inner = inner
        self.theme_names = inner.theme_names
        self.current_theme = inner.current_theme
        self.activate = inner.activate
        self.set_theme = inner.set_theme
        self.on_changed = inner.on_changed
        self.deactivate = inner.deactivate


@pytest.fixture
def recording() -> tuple[StoryRegistry, list[Mapping[str, object]]]:
    seen: list[Mapping[str, object]] = []
    stories = StoryRegistry()

    @stories.story("Display/Label", controls=[TextControl("text", "Hi")])
    def label(ctx: StoryContext) -> QLabel:
        seen.append(ctx.tokens)
        return QLabel(str(ctx.args["text"]))

    return stories, seen


def _window(qtbot, registry: StoryRegistry, provider: ThemeProvider) -> GalleryWindow:
    window = GalleryWindow(registry, provider)
    qtbot.addWidget(window)
    return window


def test_the_tokens_default_to_empty_and_are_a_read_only_copy_that_stays_out_of_repr() -> None:
    assert StoryContext(args={}).tokens == {}
    source = {"accent": "#112233"}
    context = StoryContext(args={}, theme="Dark", tokens=source)
    source["accent"] = "#000000"

    assert context.tokens == {"accent": "#112233"}
    with pytest.raises(TypeError):
        context.tokens["accent"] = "#ffffff"  # ty: ignore[invalid-assignment]
    assert "tokens" not in repr(context)
    assert StoryContext(args={"a": 1}, theme="Dark").theme == "Dark"


def test_the_builtin_tokens_are_the_application_palettes_active_colours(themes: BuiltinThemeProvider, qapp: QApplication) -> None:
    tokens = themes.tokens()

    assert set(tokens) == _TOKEN_NAMES
    palette = qapp.palette()
    active = QPalette.ColorGroup.Active
    assert tokens["window"] == palette.color(active, QPalette.ColorRole.Window).name()
    assert tokens["accent"] == palette.color(active, QPalette.ColorRole.Accent).name()
    assert tokens["border"] == palette.color(active, QPalette.ColorRole.Mid).name()
    assert all(isinstance(value, str) and len(value) == 7 and value.startswith("#") for value in tokens.values())


def test_tokens_reach_the_story_and_change_with_the_theme(qtbot, recording, themes: BuiltinThemeProvider) -> None:
    registry, seen = recording
    window = _window(qtbot, registry, themes)
    light_window = seen[-1]["window"]
    assert light_window == themes.tokens()["window"]

    themes.set_theme("Dark")

    assert seen[-1]["window"] == themes.tokens()["window"]
    assert seen[-1]["window"] != light_window
    assert len(seen) == 2
    assert isinstance(window.current_preview_widget(), QLabel)


def test_a_provider_without_tokens_yields_an_empty_mapping(qtbot, recording, qapp: QApplication, restore_application_look: None) -> None:
    registry, seen = recording
    provider = _NoTokensProvider(StyleSheetProvider())
    assert isinstance(provider, ThemeProvider)
    provider.activate(qapp)
    try:
        window = _window(qtbot, registry, provider)
        provider.set_theme("Ink")

        assert [dict(tokens) for tokens in seen] == [{}, {}]
        assert isinstance(window.current_preview_widget(), QLabel)
    finally:
        provider.deactivate()


def test_a_provider_with_tokens_gives_them_to_the_story(qtbot, recording, qapp: QApplication, restore_application_look: None) -> None:
    registry, seen = recording
    provider = StyleSheetProvider()
    provider.activate(qapp)
    try:
        window = _window(qtbot, registry, provider)
        provider.set_theme("Ink")

        assert [dict(tokens) for tokens in seen] == [{"background": "#fdf6e3"}, {"background": "#101418"}]
        assert isinstance(window.current_preview_widget(), QLabel)
    finally:
        provider.deactivate()


def test_a_raising_tokens_method_shows_the_error_panel_and_yields_no_tokens(
    qtbot, recording, qapp: QApplication, restore_application_look: None, caplog: pytest.LogCaptureFixture
) -> None:
    registry, seen = recording
    provider = RaisingProvider()
    provider.activate(qapp)
    try:
        with caplog.at_level(logging.ERROR, logger="GalleryWindow"):
            window = _window(qtbot, registry, provider)
        panel = window.findChild(ErrorPanel)
        assert panel is not None
        assert any("Theme provider failed: RuntimeError: boom" in label.text() for label in panel.findChildren(QLabel))
        assert [dict(tokens) for tokens in seen] == [{}]
        assert any(record.exc_info for record in caplog.records)
    finally:
        provider.deactivate()


def test_a_tokens_failure_after_a_theme_change_shows_the_error_panel(qtbot, recording, qapp: QApplication, restore_application_look: None) -> None:
    registry, _seen = recording
    provider = StyleSheetProvider()
    provider.activate(qapp)
    try:
        window = _window(qtbot, registry, provider)
        assert window.findChild(ErrorPanel) is None

        def failing() -> Mapping[str, object]:
            raise RuntimeError("tokens failed")

        provider.tokens = failing
        provider.simulate_external_change()

        panel = window.findChild(ErrorPanel)
        assert panel is not None
        assert any("RuntimeError: tokens failed" in label.text() for label in panel.findChildren(QLabel))
    finally:
        provider.deactivate()


def test_tokens_that_are_not_a_mapping_show_the_error_panel_instead_of_rendering(
    qtbot, recording, qapp: QApplication, restore_application_look: None
) -> None:
    registry, seen = recording
    provider = StyleSheetProvider()
    provider.activate(qapp)
    try:
        window = _window(qtbot, registry, provider)
        seen.clear()

        def not_a_mapping() -> object:
            return ["#ffffff"]

        provider.tokens = not_a_mapping  # ty: ignore[invalid-assignment]
        with qtbot.capture_exceptions() as exceptions:
            provider.simulate_external_change()
            panel = window.findChild(ErrorPanel)
            assert panel is not None
            assert "Theme provider failed: TypeError: tokens() returned list, expected a mapping" in [
                label.text() for label in panel.findChildren(QLabel)
            ]

        assert exceptions == []
        assert seen == []  # the bad tokens never reach a story
    finally:
        provider.deactivate()


def test_a_story_that_reads_only_the_args_renders_unchanged(qtbot, registry: StoryRegistry, themes: BuiltinThemeProvider) -> None:
    window = _window(qtbot, registry, themes)

    assert window.select_story("Display/Label")
    preview = window.current_preview_widget()
    assert isinstance(preview, QLabel)
    assert preview.text() == "Light 10"


def _fill(badge: QWidget) -> QColor:
    """Return the colour of the badge's fill, sampled left of the text where only the fill and the outline are drawn."""
    image = badge.grab().toImage()
    height = image.height()
    return QColor(image.pixelColor(height // 2 + 3, height // 2))


def test_the_token_badge_pixels_follow_the_theme(qtbot, stories: StoryRegistry, themes: BuiltinThemeProvider) -> None:
    result = load_stories([EXAMPLES_MODULE])
    assert result.errors == ()
    window = _window(qtbot, result.registry, themes)
    assert window.select_story("Display/Token Badge")

    fills = {}
    for theme in ("Light", "Dark"):
        themes.set_theme(theme)
        badge = window.current_preview_widget()
        assert badge is not None
        assert badge.accessibleName() == "Token badge"
        fills[theme] = _fill(badge)
        assert fills[theme].name() == themes.tokens()["accent"]

    assert fills["Light"].name() != fills["Dark"].name()


def test_the_token_badge_falls_back_to_the_palette_without_tokens(qtbot, stories: StoryRegistry, themes: BuiltinThemeProvider) -> None:
    result = load_stories([EXAMPLES_MODULE])
    assert result.errors == ()
    widget = result.registry.get("Display/Token Badge")(StoryContext(args={"text": "Badge"}))
    qtbot.addWidget(widget)
    widget.resize(widget.sizeHint())

    assert widget.accessibleName() == "Token badge"
    assert _fill(widget).name() == themes.tokens()["accent"]
