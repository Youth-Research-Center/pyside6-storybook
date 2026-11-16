import ast
import tomllib
from collections.abc import Iterator
from importlib import resources
from pathlib import Path

import pytest
import shiboken6
from icon_testing import assert_tinted, strongest_pixel
from PySide6.QtGui import QAction, QColor, QIcon, QPalette
from PySide6.QtWidgets import QApplication, QPushButton, QWidget

import pyside6_storybook
from pyside6_storybook import StoryRegistry
from pyside6_storybook.gui import icons
from pyside6_storybook.gui.icons import ActionIcons, IconRole, build_icon, clear_icon_cache, icon_svg, palette_icon
from pyside6_storybook.gui.window import GalleryWindow
from pyside6_storybook.themes import BuiltinThemes

_FORBIDDEN_IMPORTS = {"urllib", "http", "socket", "ssl"}


@pytest.fixture(autouse=True)
def cold_icon_cache() -> Iterator[None]:
    clear_icon_cache()
    yield
    clear_icon_cache()


def _manifest_icons() -> list[str]:
    text = resources.files("pyside6_storybook.resources").joinpath("icons", "icon_manifest.toml").read_text(encoding="utf-8")
    return list(tomllib.loads(text)["icons"])


def _palette(*, active: str = "#ff0000", disabled: str = "#00ff00", highlighted_text: str = "#0000ff") -> QPalette:
    palette = QPalette()
    palette.setColor(QPalette.ColorGroup.Active, QPalette.ColorRole.WindowText, QColor(active))
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.WindowText, QColor(disabled))
    palette.setColor(QPalette.ColorGroup.Active, QPalette.ColorRole.HighlightedText, QColor(highlighted_text))
    return palette


def test_the_bundle_loads_and_returns_tintable_svg() -> None:
    svg = icon_svg("magnifying-glass")

    assert svg.startswith("<svg")
    assert "currentColor" in svg


def test_an_unknown_icon_raises_key_error_naming_the_manifest() -> None:
    with pytest.raises(KeyError) as error:
        icon_svg("no-such-icon")

    assert "icon_manifest.toml" in str(error.value)
    assert "build_icon_bundle.py" in str(error.value)


def test_the_manifest_lists_the_icon_set_of_the_gallery() -> None:
    assert sorted(_manifest_icons()) == sorted(
        [
            "arrow-counter-clockwise",
            "arrows-clockwise",
            "copy",
            "magnifying-glass",
            "magnifying-glass-minus",
            "magnifying-glass-plus",
            "trash",
            "warning",
        ]
    )


@pytest.mark.parametrize("name", _manifest_icons())
def test_every_manifest_icon_is_in_the_bundle_and_renders(name: str, qapp: QApplication) -> None:
    assert "currentColor" in icon_svg(name)
    assert not build_icon(name, "#000000").pixmap(16, 16).isNull()


def test_the_tint_reaches_the_pixels(qapp: QApplication) -> None:
    assert_tinted(strongest_pixel(build_icon("copy", "#ff0000")), "#ff0000")
    assert_tinted(strongest_pixel(build_icon("copy", "#00ff00")), "#00ff00")


def test_an_invalid_colour_is_rejected(qapp: QApplication) -> None:
    with pytest.raises(ValueError, match="Invalid icon colour"):
        build_icon("copy", "not-a-colour")


def test_the_disabled_and_selected_tints_use_their_own_colours(qapp: QApplication) -> None:
    icon = build_icon("copy", "#ff0000", disabled_color="#00ff00", selected_color="#0000ff")

    assert_tinted(strongest_pixel(icon, mode=QIcon.Mode.Normal), "#ff0000")
    assert_tinted(strongest_pixel(icon, mode=QIcon.Mode.Disabled), "#00ff00")
    assert_tinted(strongest_pixel(icon, mode=QIcon.Mode.Selected), "#0000ff")


def test_the_cache_is_keyed_on_colour_and_device_pixel_ratio(qapp: QApplication, monkeypatch: pytest.MonkeyPatch) -> None:
    build_icon("copy", "#ff0000")
    build_icon("copy", "#ff0000")
    assert icons._render_pixmap.cache_info().misses == 1
    assert icons._render_pixmap.cache_info().hits == 1

    build_icon("copy", "#00ff00")
    assert icons._render_pixmap.cache_info().misses == 2

    monkeypatch.setattr(icons, "_device_pixel_ratio", lambda: 2.0)
    pixmap = build_icon("copy", "#ff0000", size=16).pixmap(16, 16)
    assert icons._render_pixmap.cache_info().misses == 3
    assert icons._render_pixmap("copy", "#ff0000", 16, 2.0).devicePixelRatio() == 2.0
    assert icons._render_pixmap("copy", "#ff0000", 16, 2.0).width() == 32
    assert not pixmap.isNull()


def test_clear_icon_cache_forgets_the_renders(qapp: QApplication) -> None:
    build_icon("copy", "#ff0000")

    clear_icon_cache()

    assert icons._render_pixmap.cache_info().currsize == 0


def test_a_translucent_colour_makes_a_translucent_icon(qapp: QApplication) -> None:
    pixel = strongest_pixel(build_icon("copy", "#80ff0000"))

    assert 120 <= pixel.alpha() <= 136
    assert_tinted(pixel, "#ff0000")


def test_palette_icon_reads_the_active_disabled_and_highlighted_text_colours(qapp: QApplication) -> None:
    icon = palette_icon("copy", palette=_palette())

    assert_tinted(strongest_pixel(icon, mode=QIcon.Mode.Normal), "#ff0000")
    assert_tinted(strongest_pixel(icon, mode=QIcon.Mode.Disabled), "#00ff00")
    assert_tinted(strongest_pixel(icon, mode=QIcon.Mode.Selected), "#0000ff")


@pytest.mark.parametrize(
    ("role", "palette_role"),
    [
        (IconRole.TEXT, QPalette.ColorRole.WindowText),
        (IconRole.MUTED, QPalette.ColorRole.PlaceholderText),
        (IconRole.ACCENT, QPalette.ColorRole.Highlight),
        (IconRole.ON_ACCENT, QPalette.ColorRole.HighlightedText),
    ],
)
def test_each_role_tints_from_its_palette_role(role: IconRole, palette_role: QPalette.ColorRole, qapp: QApplication) -> None:
    palette = _palette()
    palette.setColor(QPalette.ColorGroup.Active, palette_role, QColor("#123456"))

    assert role.value == palette_role
    assert_tinted(strongest_pixel(palette_icon("copy", role=role, palette=palette)), "#123456")


def test_palette_icon_defaults_to_the_application_palette(qapp: QApplication) -> None:
    expected = qapp.palette().color(QPalette.ColorGroup.Active, QPalette.ColorRole.WindowText)

    assert_tinted(strongest_pixel(palette_icon("copy")), expected.name())


def test_retint_renders_bound_icons_again_from_the_new_palette(qtbot) -> None:
    parent = QWidget()
    qtbot.addWidget(parent)
    button = QPushButton(parent)
    action = QAction(parent)
    registry = ActionIcons()
    registry.bind(button, "copy")
    registry.bind(action, "trash", role=IconRole.ACCENT)

    registry.retint(_palette(active="#ff0000"))
    assert_tinted(strongest_pixel(button.icon()), "#ff0000")

    registry.retint(_palette(active="#00ff00"))
    assert_tinted(strongest_pixel(button.icon()), "#00ff00")
    assert not action.icon().isNull()


def test_bind_sets_the_icon_immediately_with_the_given_role(qtbot) -> None:
    parent = QWidget()
    qtbot.addWidget(parent)
    button = QPushButton(parent)
    expected = QApplication.palette().color(QPalette.ColorGroup.Active, QPalette.ColorRole.Highlight)

    ActionIcons(size=24).bind(button, "copy", role=IconRole.ACCENT)

    assert_tinted(strongest_pixel(button.icon(), 24), expected.name())


def test_retint_drops_a_deleted_target_and_keeps_the_others(qtbot) -> None:
    parent = QWidget()
    qtbot.addWidget(parent)
    doomed = QPushButton(parent)
    kept = QPushButton(parent)
    registry = ActionIcons()
    registry.bind(doomed, "copy")
    registry.bind(kept, "trash")
    shiboken6.delete(doomed)

    registry.retint(_palette(active="#ff0000"))

    assert_tinted(strongest_pixel(kept.icon()), "#ff0000")
    assert [binding.target for binding in registry._bound] == [kept]


def test_the_window_retints_on_a_theme_switch(qtbot, registry: StoryRegistry, themes: BuiltinThemes, monkeypatch: pytest.MonkeyPatch) -> None:
    window = GalleryWindow(registry, themes)
    qtbot.addWidget(window)
    button = QPushButton(window)
    window._icons.bind(button, "copy")
    calls: list[QPalette | None] = []
    original = window._icons.retint
    monkeypatch.setattr(window._icons, "retint", lambda palette=None: (calls.append(palette), original(palette)))

    # Qt delivers an application palette change to a widget as a PaletteChange event from the event loop, not inside setPalette().
    window.set_theme("Dark")
    qtbot.waitUntil(lambda: len(calls) >= 1, timeout=5000)
    dark_text = QApplication.palette().color(QPalette.ColorGroup.Active, QPalette.ColorRole.WindowText)
    assert_tinted(strongest_pixel(button.icon()), dark_text.name())
    after_dark = len(calls)
    window.set_theme("Light")
    qtbot.waitUntil(lambda: len(calls) > after_dark, timeout=5000)

    light_text = QApplication.palette().color(QPalette.ColorGroup.Active, QPalette.ColorRole.WindowText)
    assert light_text.name() != dark_text.name()
    assert_tinted(strongest_pixel(button.icon()), light_text.name())


def test_the_window_retints_on_its_own_palette_change(qtbot, registry: StoryRegistry, themes: BuiltinThemes, monkeypatch: pytest.MonkeyPatch) -> None:
    window = GalleryWindow(registry, themes)
    qtbot.addWidget(window)
    calls: list[QPalette | None] = []
    monkeypatch.setattr(window._icons, "retint", lambda palette=None: calls.append(palette))

    window.setPalette(_palette())

    assert calls


def _imported_roots(path: Path) -> set[str]:
    roots: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None and node.level == 0:
            roots.add(node.module.split(".")[0])
    return roots


def test_no_module_of_the_package_can_make_a_network_request() -> None:
    package_dir = Path(pyside6_storybook.__file__).parent
    offenders = {
        str(path.relative_to(package_dir)): sorted(_imported_roots(path) & _FORBIDDEN_IMPORTS)
        for path in package_dir.rglob("*.py")
        if _imported_roots(path) & _FORBIDDEN_IMPORTS
    }

    assert offenders == {}
