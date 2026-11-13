import ast
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication, QLabel, QListWidget, QWidget

import pyside6_storybook.examples
from pyside6_storybook import BoolControl, ChoiceControl, FloatControl, IntControl, StoryContext, StoryRegistry, TextControl, load_stories
from pyside6_storybook.cli import EXAMPLES_MODULE
from pyside6_storybook.gui import ErrorPanel, GalleryWindow
from pyside6_storybook.themes import BUILTIN_THEME_NAMES, BuiltinThemes

EXPECTED_IDS = [
    "Buttons/Push Button",
    "Buttons/Check Box",
    "Display/Label",
    "Display/Progress Bar",
    "Display/Palette",
    "Forms/Sign-in Form",
    "Inputs/Line Edit",
    "Inputs/Spin Box",
    "Inputs/Double Spin Box",
    "Inputs/Combo Box",
    "Inputs/Slider",
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
    assert used == {TextControl, BoolControl, ChoiceControl, IntControl, FloatControl}


def test_one_example_has_no_controls_and_shows_the_theme(qtbot, examples: StoryRegistry) -> None:
    palette_story = examples.get("Display/Palette")
    assert palette_story.controls == ()
    for theme in BUILTIN_THEME_NAMES:
        widget = palette_story(StoryContext(args={}, theme=theme))
        qtbot.addWidget(widget)
        assert f"Theme: {theme}" in [label.text() for label in widget.findChildren(QLabel)]


def test_every_example_has_a_docstring(examples: StoryRegistry) -> None:
    assert [story.id for story in examples if not story.doc] == []


@pytest.mark.parametrize("theme", BUILTIN_THEME_NAMES)
@pytest.mark.parametrize("story_id", EXPECTED_IDS)
def test_every_example_renders_with_its_defaults_in_every_theme(qtbot, examples: StoryRegistry, themes: BuiltinThemes, story_id: str, theme: str) -> None:
    themes.set_theme(theme)
    example = examples.get(story_id)

    widget = example(StoryContext(args=example.default_args(), theme=theme))

    assert isinstance(widget, QWidget)
    qtbot.addWidget(widget)
    widget.show()


def test_the_gallery_renders_every_example_without_an_error(qtbot, examples: StoryRegistry, themes: BuiltinThemes, qapp: QApplication) -> None:
    window = GalleryWindow(examples, themes)
    qtbot.addWidget(window)
    window.show()
    sidebar = window.findChild(QListWidget, "storySidebar")
    assert sidebar is not None

    with qtbot.capture_exceptions() as exceptions:
        for theme in BUILTIN_THEME_NAMES:
            window.set_theme(theme)
            for row in range(sidebar.count()):
                sidebar.setCurrentRow(row)
                assert window.current_preview_widget() is not None, sidebar.item(row).text()
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
