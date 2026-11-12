import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPalette
from PySide6.QtWidgets import QApplication, QPushButton, QStyleFactory

from pyside6_storybook.contrast import contrast_ratio
from pyside6_storybook.themes import DARK_THEME, LIGHT_THEME, BuiltinThemes, ThemeDefinition, dark_palette, light_palette

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
    assert BuiltinThemes().names == ("Light", "Dark")
    assert BuiltinThemes().current == "Light"


@pytest.mark.parametrize("make_palette", [light_palette, dark_palette])
@pytest.mark.parametrize(("foreground", "background"), _TEXT_ON_BACKGROUND)
def test_text_meets_aa_contrast_on_its_background(make_palette, foreground: QPalette.ColorRole, background: QPalette.ColorRole) -> None:
    palette = make_palette()
    assert contrast_ratio(_hex(palette, _ACTIVE, foreground), _hex(palette, _ACTIVE, background)) >= 4.5


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


def test_activate_applies_the_current_theme_and_fusion(qapp: QApplication, themes: BuiltinThemes) -> None:
    assert qapp.style().objectName().lower() == "fusion"
    assert qapp.palette().color(_ACTIVE, _ROLE.Window) == light_palette().color(_ACTIVE, _ROLE.Window)


def test_set_theme_changes_the_application_palette(qapp: QApplication, themes: BuiltinThemes) -> None:
    light_window = qapp.palette().color(_ACTIVE, _ROLE.Window).name()

    themes.set_theme("Dark")

    assert themes.current == "Dark"
    assert qapp.palette().color(_ACTIVE, _ROLE.Window).name() == _hex(dark_palette(), _ACTIVE, _ROLE.Window)
    assert qapp.palette().color(_ACTIVE, _ROLE.Window).name() != light_window
    assert qapp.palette().color(_DISABLED, _ROLE.ButtonText).name() == _hex(dark_palette(), _DISABLED, _ROLE.ButtonText)

    themes.set_theme("Light")
    assert qapp.palette().color(_ACTIVE, _ROLE.Window).name() == light_window


def test_set_theme_rejects_unknown_names(themes: BuiltinThemes) -> None:
    with pytest.raises(ValueError, match="Unknown theme 'Sepia'"):
        themes.set_theme("Sepia")
    assert themes.current == "Light"


def test_set_theme_before_activate_is_applied_on_activation(qapp: QApplication, restore_application_look: None) -> None:
    builtin_themes = BuiltinThemes()
    builtin_themes.set_theme("Dark")
    original = qapp.palette().color(_ACTIVE, _ROLE.Window).name()
    assert original != _hex(dark_palette(), _ACTIVE, _ROLE.Window)

    builtin_themes.activate(qapp)
    try:
        assert qapp.palette().color(_ACTIVE, _ROLE.Window).name() == _hex(dark_palette(), _ACTIVE, _ROLE.Window)
    finally:
        builtin_themes.deactivate()


def test_activating_twice_raises(qapp: QApplication, themes: BuiltinThemes) -> None:
    with pytest.raises(RuntimeError, match="already active"):
        themes.activate(qapp)


def test_deactivate_restores_style_palette_and_style_sheet(qapp: QApplication, restore_application_look: None) -> None:
    qapp.setPalette(dark_palette())
    qapp.setStyleSheet("QLabel { margin: 0px; }")
    style_name = qapp.style().objectName()
    palette = QPalette(qapp.palette())
    builtin_themes = BuiltinThemes()
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
    builtin_themes = BuiltinThemes()
    builtin_themes.activate(qapp)
    assert qapp.style().objectName().lower() == "fusion"

    builtin_themes.deactivate()

    assert qapp.style().objectName() == original


def test_deactivate_is_idempotent(qapp: QApplication, restore_application_look: None) -> None:
    builtin_themes = BuiltinThemes()
    builtin_themes.deactivate()
    builtin_themes.activate(qapp)
    builtin_themes.deactivate()
    builtin_themes.deactivate()


def test_set_theme_after_deactivate_leaves_the_application_alone(qapp: QApplication, restore_application_look: None) -> None:
    builtin_themes = BuiltinThemes()
    builtin_themes.activate(qapp)
    builtin_themes.deactivate()
    palette = QPalette(qapp.palette())

    builtin_themes.set_theme("Dark")

    assert qapp.palette() == palette


@pytest.mark.parametrize("theme", ["Light", "Dark"])
def test_a_disabled_button_looks_different_from_an_enabled_one(qtbot, themes: BuiltinThemes, theme: str) -> None:
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
    builtin_themes = BuiltinThemes()

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


def _themes_with_hints(monkeypatch: pytest.MonkeyPatch, hints: _FakeStyleHints) -> BuiltinThemes:
    builtin_themes = BuiltinThemes()
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
    assert theme.name in BuiltinThemes().names
