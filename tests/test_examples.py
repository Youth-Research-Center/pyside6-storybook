import ast
import dataclasses
import typing
from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication, QLabel, QVBoxLayout, QWidget

import pyside6_storybook.examples
from pyside6_storybook import (
    BoolControl,
    ChoiceControl,
    ColorControl,
    Control,
    EnumControl,
    FileControl,
    FloatControl,
    IntControl,
    StoryContext,
    StoryRegistry,
    TextControl,
    load_stories,
)
from pyside6_storybook.checks import check_accessible_names, check_keyboard_focus, check_text_contrast
from pyside6_storybook.cli import EXAMPLES_MODULE
from pyside6_storybook.gui import ErrorPanel, GalleryWindow
from pyside6_storybook.gui.sidebar import StorySidebar
from pyside6_storybook.registry.rendering import render_story
from pyside6_storybook.themes import BUILTIN_THEME_NAMES, BuiltinThemeProvider

EXPECTED_IDS = [
    "Buttons/Push Button/Default",
    "Buttons/Push Button/Disabled",
    "Buttons/Push Button/Checkable",
    "Buttons/Check Box",
    "Display/Label",
    "Display/Progress Bar",
    "Display/Palette",
    "Display/Color Swatch",
    "Display/Alignment",
    "Display/Table",
    "Display/Token Badge",
    "Forms/Sign-in Form",
    "Inputs/Line Edit/Default",
    "Inputs/Line Edit/Password",
    "Inputs/Line Edit/Read-only",
    "Inputs/Spin Box",
    "Inputs/Double Spin Box",
    "Inputs/Combo Box",
    "Inputs/Slider",
    "Inputs/File Path",
]
_EXAMPLES_FOLDER = Path(pyside6_storybook.examples.__file__).parent


@pytest.fixture
def examples(stories: StoryRegistry) -> StoryRegistry:
    result = load_stories([EXAMPLES_MODULE])
    assert result.errors == ()
    return result.registry


def test_the_examples_are_the_expected_stories(examples: StoryRegistry) -> None:
    assert examples.ids() == EXPECTED_IDS


def test_the_examples_use_every_control_type(examples: StoryRegistry) -> None:
    used = {type(control) for story in examples for control in story.controls}
    assert used == {TextControl, BoolControl, ChoiceControl, IntControl, FloatControl, ColorControl, EnumControl, FileControl}


def test_the_examples_use_every_control_option(examples: StoryRegistry) -> None:
    options = {field.name: field.default for control_type in typing.get_args(Control) for field in dataclasses.fields(control_type) if field.kw_only}
    assert {"label", "description", "multiline", "step", "decimals", "slider", "alpha", "filter"} <= set(options)
    used = {
        name
        for story in examples
        for control in story.controls
        for name, default in options.items()
        if hasattr(control, name) and getattr(control, name) != default
    }
    assert used == set(options)


def test_one_example_has_no_controls_and_shows_the_theme(qtbot, examples: StoryRegistry) -> None:
    palette_story = examples.get("Display/Palette")
    assert palette_story.controls == ()
    for theme in BUILTIN_THEME_NAMES:
        widget = palette_story(StoryContext(args={}, theme=theme))
        qtbot.addWidget(widget)
        assert f"Theme: {theme}" in [label.text() for label in widget.findChildren(QLabel)]


def test_the_file_path_example_shows_a_path_with_markup_verbatim(qtbot, examples: StoryRegistry) -> None:
    file_story = examples.get("Inputs/File Path")
    widget = file_story(StoryContext(args={"path": Path("<b>notes.txt")}))
    qtbot.addWidget(widget)
    assert isinstance(widget, QLabel)
    assert widget.text() == "<b>notes.txt"
    assert widget.textFormat() == Qt.TextFormat.PlainText


@pytest.mark.parametrize("story_id", EXPECTED_IDS)
def test_every_example_passes_the_accessibility_checks(qtbot, examples: StoryRegistry, themes: BuiltinThemeProvider, story_id: str) -> None:
    example = examples.get(story_id)
    widget = render_story(example, StoryContext(args=example.default_args()), registry=examples).root
    qtbot.addWidget(widget)
    widget.show()
    qtbot.waitUntil(widget.isVisible, timeout=5000)

    assert [str(issue) for issue in check_accessible_names(widget)] == []
    assert [str(issue) for issue in check_keyboard_focus(widget)] == []


def _shown_in_theme(
    qtbot, examples: StoryRegistry, themes: BuiltinThemeProvider, story_id: str, theme: str, **args: object
) -> tuple[QWidget, QWidget]:
    """Render an example in a theme inside an opaque shown host; return the host (keep it alive) and the example's root."""
    themes.set_theme(theme)
    example = examples.get(story_id)
    context = StoryContext(args={**example.default_args(), **args}, theme=theme)
    widget = render_story(example, context, registry=examples).root
    # An opaque host like the pytest plugin's, so that a translucent story is drawn over the window colour and not over nothing.
    host = QWidget()
    host.setAutoFillBackground(True)
    host.setBackgroundRole(QPalette.ColorRole.Window)
    layout = QVBoxLayout(host)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.addWidget(widget)
    qtbot.addWidget(host)
    host.show()
    qtbot.waitUntil(widget.isVisible, timeout=5000)
    focus = QApplication.focusWidget()
    if focus is not None:
        focus.clearFocus()
    qtbot.wait(10)
    return host, widget


# System is Qt's own palette, which is white on #308cc6 (3.69:1) in the Palette story offscreen, so only Light and Dark are checked.
@pytest.mark.parametrize("theme", ["Light", "Dark"])
@pytest.mark.parametrize("story_id", EXPECTED_IDS)
def test_every_example_passes_the_contrast_check(qtbot, examples: StoryRegistry, themes: BuiltinThemeProvider, story_id: str, theme: str) -> None:
    _host, widget = _shown_in_theme(qtbot, examples, themes, story_id, theme)

    assert [str(issue) for issue in check_text_contrast(widget)] == []


@pytest.mark.parametrize("theme", ["Light", "Dark"])
@pytest.mark.parametrize("alpha", [0, 64, 255])
@pytest.mark.parametrize("rgb", ["#3a7bd5", "#000000", "#ffffff", "#808080", "#ff0000", "#00c000", "#ffe000"])
def test_the_color_swatch_text_reaches_four_and_a_half_to_one_for_opaque_and_translucent_colors(
    qtbot, examples: StoryRegistry, themes: BuiltinThemeProvider, rgb: str, alpha: int, theme: str
) -> None:
    color = QColor(rgb)
    color.setAlpha(alpha)
    _host, widget = _shown_in_theme(qtbot, examples, themes, "Display/Color Swatch", theme, color=color)

    issues = check_text_contrast(widget, normal=4.5)

    assert [str(issue) for issue in issues] == [], f"{rgb} at alpha {alpha} in {theme}"


def test_every_example_has_a_docstring(examples: StoryRegistry) -> None:
    assert [story.id for story in examples if not story.doc] == []


@pytest.mark.full
@pytest.mark.parametrize("theme", BUILTIN_THEME_NAMES)
@pytest.mark.parametrize("story_id", EXPECTED_IDS)
def test_every_example_renders_with_its_defaults_in_every_theme(
    qtbot, examples: StoryRegistry, themes: BuiltinThemeProvider, story_id: str, theme: str
) -> None:
    themes.set_theme(theme)
    example = examples.get(story_id)

    widget = example(StoryContext(args=example.default_args(), theme=theme))

    assert isinstance(widget, QWidget)
    qtbot.addWidget(widget)
    widget.show()


@pytest.mark.full
def test_the_gallery_renders_every_example_without_an_error(qtbot, examples: StoryRegistry, themes: BuiltinThemeProvider, qapp: QApplication) -> None:
    window = GalleryWindow(examples, themes)
    qtbot.addWidget(window)
    window.show()
    sidebar = window.findChild(StorySidebar)
    assert sidebar is not None

    with qtbot.capture_exceptions() as exceptions:
        for theme in BUILTIN_THEME_NAMES:
            window.set_theme(theme)
            for story_id in sidebar.visible_story_ids():
                assert window.select_story(story_id)
                assert window.current_preview_widget() is not None, story_id
                assert not [panel for panel in window.findChildren(ErrorPanel) if panel.isVisibleTo(window)]

    assert exceptions == []


def test_example_modules_are_story_files_that_import_only_pyside6_and_the_library() -> None:
    modules = sorted(path.name for path in _EXAMPLES_FOLDER.glob("*.py") if path.name != "__init__.py")
    assert modules == ["buttons_stories.py", "display_stories.py", "forms_stories.py", "inputs_stories.py"]
    for name in modules:
        tree = ast.parse((_EXAMPLES_FOLDER / name).read_text(encoding="utf-8"))
        imported = {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
        imported |= {alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names}
        assert {module.split(".")[0] for module in imported if module} <= {"__future__", "PySide6", "pyside6_storybook"}, name


def test_the_sign_in_example_uses_a_decorator(qtbot, examples: StoryRegistry) -> None:
    form = examples.get("Forms/Sign-in Form")

    assert [repr(decorator) for decorator in form.decorators] == ["padding(24)"]
    rendered = render_story(form, StoryContext(args=form.default_args()), registry=examples)
    qtbot.addWidget(rendered.root)
    assert rendered.root is not rendered.widget
    assert rendered.root.isAncestorOf(rendered.widget)
