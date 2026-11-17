import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPalette
from PySide6.QtWidgets import QApplication, QPushButton, QStyleFactory

from pyside6_storybook.contrast import contrast_ratio
from pyside6_storybook.themes import DARK_THEME, LIGHT_THEME, BuiltinThemeProvider, ThemeDefinition, dark_palette, light_palette
from pyside6_storybook.themes.builtin_theme_provider import underlying_style_name

_ACTIVE = QPalette.ColorGroup.Active
_DISABLED = QPalette.ColorGroup.Disabled
_ROLE = QPalette.ColorRole

_TEXT_ON_BACKGROUND = [
    (_ROLE.WindowText, _ROLE.Window),
    (_ROLE.Text, _ROLE.Base),
    (_ROLE.ButtonText, _ROLE.Button),
    (_ROLE.HighlightedText, _ROLE.Highlight),
]

_FUSION_ROLES = [
    _ROLE.Window, _ROLE.WindowText, _ROLE.Base, _ROLE.AlternateBase, _ROLE.ToolTipBase, _ROLE.ToolTipText, _ROLE.PlaceholderText,
    _ROLE.Text, _ROLE.Button, _ROLE.ButtonText, _ROLE.BrightText, _ROLE.Light, _ROLE.Midlight, _ROLE.Dark, _ROLE.Mid, _ROLE.Shadow,
    _ROLE.Highlight, _ROLE.HighlightedText, _ROLE.Link, _ROLE.LinkVisited, _ROLE.Accent,
]  # fmt: skip


def _hex(palette: QPalette, group: QPalette.ColorGroup, role: QPalette.ColorRole) -> str:
    return palette.color(group, role).name()


def test_theme_names() -> None:
    assert BuiltinThemeProvider().theme_names() == ("Light", "Dark", "System")
    assert BuiltinThemeProvider().current_theme() == "Light"


@pytest.mark.parametrize("make_palette", [light_palette, dark_palette])
@pytest.mark.parametrize(("foreground", "background"), _TEXT_ON_BACKGROUND)
def test_text_meets_aa_contrast_on_its_background(make_palette, foreground: QPalette.ColorRole, background: QPalette.ColorRole) -> None:
    palette = make_palette()
    assert contrast_ratio(_hex(palette, _ACTIVE, foreground), _hex(palette, _ACTIVE, background)) >= 4.5


@pytest.mark.parametrize("make_palette", [light_palette, dark_palette])
def test_alternate_rows_are_distinguishable_from_base(make_palette) -> None:
    palette = make_palette()
    assert contrast_ratio(_hex(palette, _ACTIVE, _ROLE.AlternateBase), _hex(palette, _ACTIVE, _ROLE.Base)) >= 1.15


@pytest.mark.parametrize("make_palette", [light_palette, dark_palette])
def test_placeholder_text_meets_aa_contrast_on_base(make_palette) -> None:
    palette = make_palette()
    assert contrast_ratio(_hex(palette, _ACTIVE, _ROLE.PlaceholderText), _hex(palette, _ACTIVE, _ROLE.Base)) >= 4.5


@pytest.mark.parametrize("make_palette", [light_palette, dark_palette])
@pytest.mark.parametrize("role", [_ROLE.WindowText, _ROLE.Text, _ROLE.ButtonText])
def test_disabled_text_differs_from_active_text(make_palette, role: QPalette.ColorRole) -> None:
    palette = make_palette()
    assert _hex(palette, _DISABLED, role) != _hex(palette, _ACTIVE, role)
    assert contrast_ratio(_hex(palette, _DISABLED, role), _hex(palette, _ACTIVE, role)) > 1.5


@pytest.mark.parametrize("make_palette", [light_palette, dark_palette])
def test_every_fusion_role_is_set_in_every_group(make_palette) -> None:
    palette = make_palette()
    for role in _FUSION_ROLES:
        assert palette.isBrushSet(_ACTIVE, role)
        assert palette.isBrushSet(QPalette.ColorGroup.Inactive, role)
        assert palette.isBrushSet(_DISABLED, role)


def test_light_and_dark_palettes_differ() -> None:
    assert _hex(light_palette(), _ACTIVE, _ROLE.Window) != _hex(dark_palette(), _ACTIVE, _ROLE.Window)
    assert contrast_ratio(_hex(light_palette(), _ACTIVE, _ROLE.Window), _hex(dark_palette(), _ACTIVE, _ROLE.Window)) > 5


def test_activate_applies_the_current_theme_and_fusion(qapp: QApplication, themes: BuiltinThemeProvider) -> None:
    assert qapp.style().objectName().lower() == "fusion"
    assert qapp.palette().color(_ACTIVE, _ROLE.Window) == light_palette().color(_ACTIVE, _ROLE.Window)


def test_set_theme_changes_the_application_palette(qapp: QApplication, themes: BuiltinThemeProvider) -> None:
    light_window = qapp.palette().color(_ACTIVE, _ROLE.Window).name()

    themes.set_theme("Dark")

    assert themes.current_theme() == "Dark"
    assert qapp.palette().color(_ACTIVE, _ROLE.Window).name() == _hex(dark_palette(), _ACTIVE, _ROLE.Window)
    assert qapp.palette().color(_ACTIVE, _ROLE.Window).name() != light_window
    assert qapp.palette().color(_DISABLED, _ROLE.ButtonText).name() == _hex(dark_palette(), _DISABLED, _ROLE.ButtonText)

    themes.set_theme("Light")
    assert qapp.palette().color(_ACTIVE, _ROLE.Window).name() == light_window


def test_set_theme_rejects_unknown_names(themes: BuiltinThemeProvider) -> None:
    with pytest.raises(ValueError, match="Unknown theme 'Sepia'"):
        themes.set_theme("Sepia")
    assert themes.current_theme() == "Light"


def test_set_theme_before_activate_is_applied_on_activation(qapp: QApplication, restore_application_look: None) -> None:
    builtin_themes = BuiltinThemeProvider()
    builtin_themes.set_theme("Dark")
    original = qapp.palette().color(_ACTIVE, _ROLE.Window).name()
    assert original != _hex(dark_palette(), _ACTIVE, _ROLE.Window)

    builtin_themes.activate(qapp)
    try:
        assert qapp.palette().color(_ACTIVE, _ROLE.Window).name() == _hex(dark_palette(), _ACTIVE, _ROLE.Window)
    finally:
        builtin_themes.deactivate()


def test_activating_twice_raises(qapp: QApplication, themes: BuiltinThemeProvider) -> None:
    with pytest.raises(RuntimeError, match="already active"):
        themes.activate(qapp)


def test_deactivate_restores_style_palette_and_style_sheet(qapp: QApplication, restore_application_look: None) -> None:
    qapp.setPalette(dark_palette())
    qapp.setStyleSheet("QLabel { margin: 0px; }")
    style_name = qapp.style().objectName()
    palette = QPalette(qapp.palette())
    builtin_themes = BuiltinThemeProvider()
    builtin_themes.activate(qapp)
    builtin_themes.set_theme("Light")
    assert qapp.palette() != palette

    builtin_themes.deactivate()

    assert qapp.palette() == palette
    assert qapp.style().objectName() == style_name
    assert qapp.styleSheet() == "QLabel { margin: 0px; }"


def test_deactivate_restores_a_non_fusion_style(qapp: QApplication, restore_application_look: None) -> None:
    available_styles = QStyleFactory.keys()
    if "Windows" not in available_styles:
        pytest.skip("the Windows style is not available on this platform")
    qapp.setStyle("Windows")
    original = qapp.style().objectName()
    assert original.lower() != "fusion"
    builtin_themes = BuiltinThemeProvider()
    builtin_themes.activate(qapp)
    assert qapp.style().objectName().lower() == "fusion"

    builtin_themes.deactivate()

    assert qapp.style().objectName() == original


def test_deactivate_is_idempotent(qapp: QApplication, restore_application_look: None) -> None:
    builtin_themes = BuiltinThemeProvider()
    builtin_themes.deactivate()
    builtin_themes.activate(qapp)
    builtin_themes.deactivate()
    builtin_themes.deactivate()


def test_set_theme_after_deactivate_leaves_the_application_alone(qapp: QApplication, restore_application_look: None) -> None:
    builtin_themes = BuiltinThemeProvider()
    builtin_themes.activate(qapp)
    builtin_themes.deactivate()
    palette = QPalette(qapp.palette())

    builtin_themes.set_theme("Dark")

    assert qapp.palette() == palette


@pytest.mark.parametrize("theme", ["Light", "Dark"])
def test_a_disabled_button_looks_different_from_an_enabled_one(qtbot, themes: BuiltinThemeProvider, theme: str) -> None:
    themes.set_theme(theme)
    enabled, disabled = QPushButton("Button"), QPushButton("Button")
    qtbot.addWidget(enabled)
    qtbot.addWidget(disabled)
    disabled.setEnabled(False)
    for button in (enabled, disabled):
        button.resize(button.sizeHint())

    enabled_image: QImage = enabled.grab().toImage()
    disabled_image: QImage = disabled.grab().toImage()

    assert enabled_image.size() == disabled_image.size()
    assert enabled_image != disabled_image


def test_deactivate_restores_a_non_fusion_style_under_an_application_style_sheet(qapp: QApplication, restore_application_look: None) -> None:
    available_styles = QStyleFactory.keys()
    if "Windows" not in available_styles:
        pytest.skip("the Windows style is not available on this platform")
    style_sheet = "QLabel { margin: 1px; }"
    qapp.setStyle("Windows")
    qapp.setStyleSheet(style_sheet)
    builtin_themes = BuiltinThemeProvider()

    builtin_themes.activate(qapp)
    builtin_themes.deactivate()

    assert qapp.styleSheet() == style_sheet
    qapp.setStyleSheet("")
    assert qapp.style().name() == "windows"


class _FakeStyleHints:
    """Mimics QStyleHints on a platform that has a system colour scheme and honours overrides."""

    def __init__(self, system: Qt.ColorScheme, *, override: Qt.ColorScheme | None = None) -> None:
        self.system = system
        self.override = override

    def colorScheme(self) -> Qt.ColorScheme:
        return self.override if self.override is not None else self.system

    def setColorScheme(self, scheme: Qt.ColorScheme) -> None:
        self.override = None if scheme == Qt.ColorScheme.Unknown else scheme

    def unsetColorScheme(self) -> None:
        self.override = None


def _themes_with_hints(monkeypatch: pytest.MonkeyPatch, hints: _FakeStyleHints) -> BuiltinThemeProvider:
    builtin_themes = BuiltinThemeProvider()
    monkeypatch.setattr(builtin_themes, "_style_hints", lambda app: hints)
    return builtin_themes


def test_deactivate_restores_a_colour_scheme_the_application_had_forced(
    qapp: QApplication, restore_application_look: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    hints = _FakeStyleHints(Qt.ColorScheme.Light, override=Qt.ColorScheme.Dark)
    builtin_themes = _themes_with_hints(monkeypatch, hints)

    builtin_themes.activate(qapp)
    assert hints.colorScheme() == Qt.ColorScheme.Light
    builtin_themes.deactivate()

    assert hints.colorScheme() == Qt.ColorScheme.Dark


def test_deactivate_lets_an_application_that_followed_the_system_keep_following_it(
    qapp: QApplication, restore_application_look: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    hints = _FakeStyleHints(Qt.ColorScheme.Light)
    builtin_themes = _themes_with_hints(monkeypatch, hints)

    builtin_themes.activate(qapp)
    builtin_themes.set_theme("Dark")
    assert hints.colorScheme() == Qt.ColorScheme.Dark
    builtin_themes.deactivate()

    assert hints.override is None
    assert hints.colorScheme() == Qt.ColorScheme.Light


def test_theme_definition_stores_read_only_copies_of_its_colours() -> None:
    colors = {_ROLE.Window: "#101010"}
    theme = ThemeDefinition(name="Test", color_scheme=Qt.ColorScheme.Dark, colors=colors, disabled_colors={_ROLE.Text: "#202020"})
    colors[_ROLE.Window] = "#ffffff"

    assert theme.colors[_ROLE.Window] == "#101010"
    with pytest.raises(TypeError):
        theme.colors[_ROLE.Window] = "#ffffff"  # ty: ignore[invalid-assignment]
    palette = theme.palette()
    assert _hex(palette, _ACTIVE, _ROLE.Window) == "#101010"
    assert _hex(palette, _DISABLED, _ROLE.Text) == "#202020"


@pytest.mark.parametrize(("theme", "make_palette"), [(LIGHT_THEME, light_palette), (DARK_THEME, dark_palette)])
def test_built_in_theme_definitions_build_the_published_palettes(theme: ThemeDefinition, make_palette) -> None:
    assert theme.palette() == make_palette()
    assert theme.name in BuiltinThemeProvider().theme_names()


def _look(app: QApplication) -> tuple[str, QPalette, str]:
    return underlying_style_name(app), QPalette(app.palette()), app.styleSheet()


def _use_windows_style(app: QApplication) -> None:
    available_styles = QStyleFactory.keys()
    if "Windows" not in available_styles:
        pytest.skip("the Windows style is not available on this platform")
    app.setStyle("Windows")


def test_system_restores_the_style_palette_and_style_sheet_found_at_activation(qapp: QApplication, restore_application_look: None) -> None:
    _use_windows_style(qapp)
    original_palette = QPalette(qapp.palette())
    original_palette.setColor(_ROLE.Window, "#336699")
    qapp.setPalette(original_palette)
    qapp.setStyleSheet("QLabel { margin: 1px; }")
    original = _look(qapp)
    builtin_themes = BuiltinThemeProvider()
    builtin_themes.activate(qapp)
    try:
        assert underlying_style_name(qapp) == "fusion"
        qapp.setStyleSheet("QLabel { margin: 2px; }")

        builtin_themes.set_theme("System")

        assert _look(qapp) == original
        assert builtin_themes.current_theme() == "System"
    finally:
        builtin_themes.deactivate()


def test_dark_after_system_applies_fusion_and_the_dark_palette_again(qapp: QApplication, restore_application_look: None) -> None:
    _use_windows_style(qapp)
    builtin_themes = BuiltinThemeProvider()
    builtin_themes.activate(qapp)
    try:
        builtin_themes.set_theme("System")
        assert qapp.style().name() == "windows"

        builtin_themes.set_theme("Dark")

        assert qapp.style().name() == "fusion"
        assert qapp.palette() == dark_palette()
    finally:
        builtin_themes.deactivate()


def test_switching_through_the_themes_leaves_no_residue_in_system(qapp: QApplication, restore_application_look: None) -> None:
    _use_windows_style(qapp)
    qapp.setStyleSheet("QLabel { margin: 1px; }")
    builtin_themes = BuiltinThemeProvider()
    builtin_themes.activate(qapp)
    try:
        builtin_themes.set_theme("System")
        first = _look(qapp)

        for name in ("Light", "System", "Dark", "System"):
            builtin_themes.set_theme(name)

        assert _look(qapp) == first
    finally:
        builtin_themes.deactivate()


def test_color_scheme_is_light_and_dark_for_those_themes_and_qts_for_system(
    qapp: QApplication, restore_application_look: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    hints = _FakeStyleHints(Qt.ColorScheme.Dark)
    builtin_themes = _themes_with_hints(monkeypatch, hints)
    builtin_themes.activate(qapp)
    try:
        assert builtin_themes.color_scheme() == Qt.ColorScheme.Light
        builtin_themes.set_theme("Dark")
        assert builtin_themes.color_scheme() == Qt.ColorScheme.Dark
        builtin_themes.set_theme("System")
        assert builtin_themes.color_scheme() == Qt.ColorScheme.Dark
        hints.system = Qt.ColorScheme.Light
        assert builtin_themes.color_scheme() == Qt.ColorScheme.Light
    finally:
        builtin_themes.deactivate()


def test_system_color_scheme_is_guessed_from_the_palette_when_qt_does_not_know(
    qapp: QApplication, restore_application_look: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    builtin_themes = _themes_with_hints(monkeypatch, _FakeStyleHints(Qt.ColorScheme.Unknown))
    palette = QPalette(qapp.palette())
    builtin_themes.activate(qapp)
    try:
        builtin_themes.set_theme("System")
        dark = QPalette(palette)
        dark.setColor(_ROLE.Window, "#101010")
        qapp.setPalette(dark)
        assert builtin_themes.color_scheme() == Qt.ColorScheme.Dark
        light = QPalette(palette)
        light.setColor(_ROLE.Window, "#f0f0f0")
        qapp.setPalette(light)
        assert builtin_themes.color_scheme() == Qt.ColorScheme.Light
    finally:
        builtin_themes.deactivate()


def test_the_colour_scheme_signal_is_followed_only_while_system_is_active(qapp: QApplication, restore_application_look: None) -> None:
    builtin_themes = BuiltinThemeProvider()
    calls: list[int] = []
    builtin_themes.on_changed(lambda: calls.append(1))
    builtin_themes.activate(qapp)
    try:
        builtin_themes.set_theme("System")
        assert calls == [1]
        qapp.styleHints().colorSchemeChanged.emit(Qt.ColorScheme.Dark)
        assert calls == [1]  # not yet: the callbacks run after the event loop
        QApplication.processEvents()
        assert calls == [1, 1]

        builtin_themes.set_theme("Dark")
        assert calls == [1, 1, 1]
        qapp.styleHints().colorSchemeChanged.emit(Qt.ColorScheme.Light)
        QApplication.processEvents()
        assert calls == [1, 1, 1]

        builtin_themes.set_theme("System")
        builtin_themes.deactivate()
        calls.clear()
        qapp.styleHints().colorSchemeChanged.emit(Qt.ColorScheme.Light)
        QApplication.processEvents()
        assert calls == []
    finally:
        builtin_themes.deactivate()


def test_a_colour_scheme_change_while_light_is_active_is_followed_in_system_and_after_deactivate(
    qapp: QApplication, restore_application_look: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    hints = _FakeStyleHints(Qt.ColorScheme.Light)
    builtin_themes = _themes_with_hints(monkeypatch, hints)
    builtin_themes.activate(qapp)
    hints.system = Qt.ColorScheme.Dark

    builtin_themes.set_theme("System")

    assert hints.override is None
    assert hints.colorScheme() == Qt.ColorScheme.Dark
    builtin_themes.set_theme("Light")
    assert hints.colorScheme() == Qt.ColorScheme.Light
    builtin_themes.deactivate()
    assert hints.override is None
    assert hints.colorScheme() == Qt.ColorScheme.Dark


def test_a_colour_scheme_the_application_forced_is_forced_again_by_system_and_deactivate(
    qapp: QApplication, restore_application_look: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    hints = _FakeStyleHints(Qt.ColorScheme.Light, override=Qt.ColorScheme.Dark)
    builtin_themes = _themes_with_hints(monkeypatch, hints)

    builtin_themes.activate(qapp)
    assert hints.colorScheme() == Qt.ColorScheme.Light  # the Light theme's own scheme
    builtin_themes.set_theme("System")
    assert hints.colorScheme() == Qt.ColorScheme.Dark
    builtin_themes.set_theme("Light")
    builtin_themes.deactivate()

    assert hints.override == Qt.ColorScheme.Dark
