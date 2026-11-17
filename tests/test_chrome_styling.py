import ast
import re
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from conftest import show_active
from fake_providers import AggressiveProvider
from PySide6.QtCore import QEvent
from PySide6.QtGui import QFont, QImage
from PySide6.QtWidgets import QApplication, QLabel, QPushButton, QTreeView, QWidget

from pyside6_storybook import BuiltinThemeProvider, StoryContext, StoryRegistry, TextControl
from pyside6_storybook.contrast import contrast_ratio
from pyside6_storybook.gui.chrome import CHROME_PROPERTY, mark_chrome
from pyside6_storybook.gui.controls_panel import ControlsPanel
from pyside6_storybook.gui.sidebar import _SelectionDelegate
from pyside6_storybook.gui.window import GalleryWindow
from pyside6_storybook.polishing import polish_all_widgets

pytestmark = pytest.mark.usefixtures("restore_window_activation")

_ROOT = Path(__file__).resolve().parent.parent
_THEMES = ("Midnight", "Daylight")
_SELECTION_FORMS = ("highlight", "item", "both")
_MINIMUM_CONTRAST = 4.5


@pytest.fixture(autouse=True)
def _delete_closed_windows() -> Iterator[None]:
    """Delete the windows qtbot closed before the next test changes the application style sheet (#80, as in ``test_theme_provider.py``)."""
    yield
    QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


@pytest.fixture
def aggressive(qapp: QApplication, restore_application_look: None) -> Iterator[Callable[[str], AggressiveProvider]]:
    """Return a function that activates an ``AggressiveProvider`` with a selection form; every provider is deactivated afterwards."""
    providers: list[AggressiveProvider] = []

    def activate(selection: str) -> AggressiveProvider:
        provider = AggressiveProvider(selection=selection)
        provider.activate(qapp)
        providers.append(provider)
        return provider

    try:
        yield activate
    finally:
        for provider in reversed(providers):
            provider.deactivate()


def _stories() -> StoryRegistry:
    stories = StoryRegistry()

    @stories.story("Inputs/Button", controls=[TextControl("text", "Click me")])
    def button(ctx: StoryContext) -> QWidget:
        return QPushButton(str(ctx.args["text"]))

    @stories.story("Broken/Story")
    def broken(ctx: StoryContext) -> QWidget:
        raise ZeroDivisionError

    return stories


def _window(qtbot, provider: BuiltinThemeProvider | AggressiveProvider, theme: str | None = None) -> GalleryWindow:
    window = GalleryWindow(_stories(), provider)
    qtbot.addWidget(window)
    if theme is not None:
        window.set_theme(theme)
    return window


def _application() -> QApplication:
    app = QApplication.instance()
    assert isinstance(app, QApplication)
    return app


def _set_style_sheet(style_sheet: str) -> None:
    """Apply an application style sheet the way the library does: polish every widget first (``pyside6_storybook.polishing``)."""
    polish_all_widgets()
    _application().setStyleSheet(style_sheet)


def _best_contrast(image: QImage, background: str, *, inset: int = 3) -> float:
    """Return the highest contrast any pixel of the image, inside an inset border, has against the background."""
    colours = {
        image.pixelColor(x, y).name()
        for y in range(inset, max(image.height() - inset, inset + 1))
        for x in range(inset, max(image.width() - inset, inset + 1))
    }
    return max(contrast_ratio(colour, background) for colour in colours)


def _label_contrast(label: QLabel) -> float:
    image = label.grab().toImage()
    return _best_contrast(image, image.pixelColor(1, 1).name(), inset=1)


def _selected_row_contrast(window: GalleryWindow) -> float:
    tree = window.findChild(QTreeView, "sbkStoryTree")
    assert tree is not None
    index = tree.currentIndex()
    assert index.isValid()
    image = tree.viewport().grab(tree.visualRect(index)).toImage()
    return _best_contrast(image, image.pixelColor(image.width() - 3, image.height() // 2).name())


def _deactivate_window(qtbot, window: GalleryWindow) -> QWidget:
    """Make another window the active one, so the first one paints its inactive selection."""
    other = QWidget()
    qtbot.addWidget(other)
    other.show()
    other.activateWindow()
    qtbot.waitUntil(lambda: QApplication.activeWindow() is other, timeout=5000)
    assert not window.isActiveWindow()
    return other


# Sidebar selection, control labels, the error panel and clipping under an aggressive application style sheet


@pytest.mark.parametrize("active", [True, False], ids=["active", "inactive"])
@pytest.mark.parametrize("selection", _SELECTION_FORMS)
@pytest.mark.parametrize("theme", _THEMES)
def test_the_selected_sidebar_text_is_readable_under_an_application_style_sheet(
    qtbot, aggressive: Callable[[str], AggressiveProvider], theme: str, selection: str, *, active: bool
) -> None:
    window = _window(qtbot, aggressive(selection), theme)
    show_active(qtbot, window)
    if not active:
        _deactivate_window(qtbot, window)

    assert _selected_row_contrast(window) >= _MINIMUM_CONTRAST


@pytest.mark.parametrize("theme", _THEMES)
def test_the_control_labels_are_readable_under_an_application_style_sheet(qtbot, aggressive: Callable[[str], AggressiveProvider], theme: str) -> None:
    window = _window(qtbot, aggressive("both"), theme)
    show_active(qtbot, window)
    window.select_story("Inputs/Button")

    (panel,) = [found for found in window.findChildren(ControlsPanel) if found.isVisibleTo(window)]
    labels = [label for label in panel.findChildren(QLabel) if label.isVisibleTo(window)]
    assert [label.text() for label in labels] == ["Text"]
    for label in labels:
        assert _label_contrast(label) >= _MINIMUM_CONTRAST, label.text()


@pytest.mark.parametrize("theme", _THEMES)
def test_the_error_panel_title_is_readable_under_an_application_style_sheet(
    qtbot, aggressive: Callable[[str], AggressiveProvider], theme: str
) -> None:
    window = _window(qtbot, aggressive("both"), theme)
    show_active(qtbot, window)
    window.select_story("Broken/Story")

    def visible_titles() -> list[QLabel]:
        return [found for found in window.findChildren(QLabel, "sbkErrorTitle") if found.isVisibleTo(window)]

    qtbot.waitUntil(lambda: len(visible_titles()) == 1, timeout=5000)
    (title,) = visible_titles()
    assert _label_contrast(title) >= _MINIMUM_CONTRAST


@pytest.mark.parametrize("theme", _THEMES)
def test_no_chrome_label_is_clipped_at_an_18_point_font(qtbot, aggressive: Callable[[str], AggressiveProvider], theme: str) -> None:
    window = _window(qtbot, aggressive("both"), theme)
    window.resize(1500, 1000)
    show_active(qtbot, window)
    assert QFont(QApplication.font()).pointSize() > 0
    for story_id in ("Inputs/Button", "Broken/Story"):
        window.select_story(story_id)
        if story_id == "Broken/Story":
            qtbot.waitUntil(lambda: any(t.isVisible() for t in window.findChildren(QLabel, "sbkErrorTitle")), timeout=5000)
        labels = [
            label
            for label in window.findChildren(QLabel)
            if label.isVisible() and label.property(CHROME_PROPERTY) is True and label.objectName() != "sbkErrorIcon"
        ]
        assert labels
        for label in labels:
            assert label.font().pointSizeF() >= 18, (label.text(), label.font().pointSizeF())
            needed = label.heightForWidth(label.width()) if label.hasHeightForWidth() else label.sizeHint().height()
            assert needed <= label.height(), (label.text(), needed, label.height())


# The sidebar delegate's cache


def _tree(window: GalleryWindow) -> QTreeView:
    tree = window.findChild(QTreeView, "sbkStoryTree")
    assert tree is not None
    return tree


def _delegate(window: GalleryWindow) -> _SelectionDelegate:
    delegate = _tree(window).itemDelegate()
    assert isinstance(delegate, _SelectionDelegate)
    return delegate


def test_the_delegate_samples_the_selected_row_once_and_reuses_it_for_the_next_paint(qtbot, aggressive: Callable[[str], AggressiveProvider]) -> None:
    window = _window(qtbot, aggressive("item"), "Daylight")
    show_active(qtbot, window)
    delegate = _delegate(window)
    first = _selected_row_contrast(window)
    sampled = delegate.sample_count
    assert sampled >= 1

    second = _selected_row_contrast(window)

    assert delegate.sample_count == sampled
    assert second == first


def test_changing_only_an_item_selected_rule_samples_again(qtbot, aggressive: Callable[[str], AggressiveProvider]) -> None:
    provider = aggressive("item")
    window = _window(qtbot, provider, "Daylight")
    show_active(qtbot, window)
    delegate = _delegate(window)
    _selected_row_contrast(window)
    sampled = delegate.sample_count
    style_sheet = _application().styleSheet()
    assert "QTreeView::item:selected {\n    background: #ffb300;" in style_sheet

    _set_style_sheet(style_sheet.replace("background: #ffb300;", "background: #004d40;"))
    _selected_row_contrast(window)

    assert delegate.sample_count > sampled


def test_the_selected_text_follows_a_changed_item_selected_rule(qtbot, aggressive: Callable[[str], AggressiveProvider]) -> None:
    window = _window(qtbot, aggressive("item"), "Midnight")
    show_active(qtbot, window)
    style_sheet = _application().styleSheet()
    for colour in ("#ffeb3b", "#0d47a1"):
        _set_style_sheet(re.sub(r"(QTreeView::item:selected \{\s*background: )#[0-9a-f]{6}", rf"\g<1>{colour}", style_sheet))

        assert _selected_row_contrast(window) >= _MINIMUM_CONTRAST, colour


# Selectors


_STORY_BUTTON_SIZE = 12.0


def _buttons(window: GalleryWindow) -> tuple[QPushButton, QPushButton]:
    """Return a chrome button (the Actions panel's Clear) and the story's own button."""
    chrome = window.findChild(QPushButton, "sbkActionsClear")
    assert chrome is not None
    story_root = window.current_preview_widget()
    assert isinstance(story_root, QPushButton)
    return chrome, story_root


def _selector_window(qtbot, themes: BuiltinThemeProvider) -> tuple[GalleryWindow, QPushButton, QPushButton]:
    window = _window(qtbot, themes)
    window.select_story("Inputs/Button")
    chrome, story = _buttons(window)
    return window, chrome, story


def _point_size(widget: QWidget) -> float:
    widget.ensurePolished()
    return widget.font().pointSizeF()


def test_the_chrome_property_selector_restyles_a_chrome_button_and_not_a_story_button(qtbot, themes: BuiltinThemeProvider) -> None:
    _, chrome, story = _selector_window(qtbot, themes)
    story_before = _point_size(story)

    _set_style_sheet('*[sbkChrome="true"] { font-size: 23pt; }')

    assert _point_size(chrome) == 23
    assert _point_size(story) == story_before != 23


def test_a_descendant_rule_under_a_chrome_ancestor_does_not_reach_a_story_button(qtbot, themes: BuiltinThemeProvider) -> None:
    _, chrome, story = _selector_window(qtbot, themes)
    story_before = _point_size(story)

    _set_style_sheet('*[sbkChrome="true"] QPushButton { font-size: 23pt; }')

    assert _point_size(chrome) == 23
    assert _point_size(story) == story_before != 23


@pytest.mark.parametrize("chrome_rule_first", [True, False], ids=["chrome-first", "chrome-last"])
def test_a_type_and_property_rule_beats_type_rules_in_any_order(qtbot, themes: BuiltinThemeProvider, *, chrome_rule_first: bool) -> None:
    _, chrome, story = _selector_window(qtbot, themes)
    chrome_rule = 'QPushButton[sbkChrome="true"] { font-size: 25pt; }'
    general = f"QPushButton {{ font-size: {_STORY_BUTTON_SIZE:g}pt; }} QWidget QPushButton {{ font-size: {_STORY_BUTTON_SIZE:g}pt; }}"

    _set_style_sheet(f"{chrome_rule} {general}" if chrome_rule_first else f"{general} {chrome_rule}")

    assert _point_size(chrome) == 25
    assert _point_size(story) == _STORY_BUTTON_SIZE


def test_the_property_rule_ties_with_the_flat_attribute_rule_so_the_later_one_wins(qtbot, themes: BuiltinThemeProvider) -> None:
    _, chrome, _story = _selector_window(qtbot, themes)
    chrome_rule = 'QPushButton[sbkChrome="true"] { font-size: 25pt; }'
    flat_rule = 'QPushButton[flat="false"] { font-size: 13pt; }'

    _set_style_sheet(f"{flat_rule} {chrome_rule}")
    assert _point_size(chrome) == 25
    _set_style_sheet(f"{chrome_rule} {flat_rule}")
    assert _point_size(chrome) == 13


@pytest.mark.parametrize("name_rule_first", [True, False], ids=["name-first", "name-last"])
def test_an_object_name_rule_beats_every_other_rule_in_any_order(qtbot, themes: BuiltinThemeProvider, *, name_rule_first: bool) -> None:
    _, chrome, story = _selector_window(qtbot, themes)
    name_rule = "#sbkActionsClear { font-size: 27pt; }"
    others = (
        'QPushButton[sbkChrome="true"] { font-size: 25pt; } QPushButton[flat="false"] { font-size: 13pt; } '
        'QPushButton:hover { font-size: 13pt; } *[sbkChrome="true"] QPushButton { font-size: 23pt; }'
    )

    _set_style_sheet(f"{name_rule} {others}" if name_rule_first else f"{others} {name_rule}")

    assert _point_size(chrome) == 27
    assert _point_size(story) != 27


def test_a_widget_marked_after_it_was_polished_picks_up_a_chrome_rule(qtbot, themes: BuiltinThemeProvider) -> None:
    window, _chrome, _story = _selector_window(qtbot, themes)
    _set_style_sheet('*[sbkChrome="true"] { font-size: 26pt; }')
    late = QPushButton("Late", window)
    late.show()
    late.ensurePolished()
    before = _point_size(late)
    assert before != 26

    mark_chrome(late)

    assert late.font().pointSizeF() == 26


def test_a_widget_marked_with_a_name_after_it_was_polished_picks_up_an_object_name_rule(qtbot, themes: BuiltinThemeProvider) -> None:
    window, _chrome, _story = _selector_window(qtbot, themes)
    _set_style_sheet("#sbkLateButton { font-size: 26pt; }")
    late = QPushButton("Late", window)
    late.show()
    late.ensurePolished()
    assert late.font().pointSizeF() != 26

    mark_chrome(late, "sbkLateButton", chrome=False)

    assert late.font().pointSizeF() == 26
    assert late.property(CHROME_PROPERTY) is None


def test_the_ancestors_of_the_preview_surface_have_names_but_not_the_chrome_property(qtbot, themes: BuiltinThemeProvider) -> None:
    window, _chrome, story = _selector_window(qtbot, themes)

    ancestors = []
    widget: QWidget | None = story.parentWidget()
    while widget is not None:
        ancestors.append(widget)
        widget = widget.parentWidget()

    assert ancestors
    assert [str(a.property(CHROME_PROPERTY)) for a in ancestors if a.property(CHROME_PROPERTY)] == []
    assert {"sbkPreviewSurface", "sbkPreviewStack", "sbkPreviewScroll", "sbkCanvas", "sbkPreviewTabs"} <= {a.objectName() for a in ancestors}
    assert window in ancestors


# The names in the README


def _readme_names() -> set[str]:
    text = (_ROOT / "README.md").read_text(encoding="utf-8")
    section = re.search(r"^## Styling the gallery\n(.*?)(?=^## )", text, flags=re.MULTILINE | re.DOTALL)
    assert section is not None
    _, _, listing = section.group(1).partition("The object names:\n")
    names = re.findall(r"`(sbk[A-Z]\w*)`", listing)
    assert len(names) == len(set(names)), "a name is listed twice"
    return set(names)


def _source_names() -> set[str]:
    """Return every ``sbk`` string literal in the package but the property's: the object names passed to ``mark_chrome``."""
    names: set[str] = set()
    for path in (_ROOT / "src").rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Constant) and isinstance(node.value, str) and re.fullmatch(r"sbk[A-Z]\w*", node.value):
                names.add(node.value)
    return names - {CHROME_PROPERTY}  # the property's own name, not an object name


def test_the_readme_lists_exactly_the_object_names_the_source_gives(qtbot, themes: BuiltinThemeProvider) -> None:
    readme = _readme_names()
    source = _source_names()

    assert readme - source == set(), "listed in the README but not in the source"
    assert source - readme == set(), "in the source but not listed in the README"
    assert len(source) == 53


def test_every_object_name_on_a_shown_window_is_listed_in_the_readme(qtbot, themes: BuiltinThemeProvider) -> None:
    window = _window(qtbot, themes)
    show_active(qtbot, window)
    for story_id in ("Inputs/Button", "Broken/Story"):
        window.select_story(story_id)
    window._show_shortcuts_dialog()
    found = {widget.objectName() for widget in QApplication.allWidgets() if widget.objectName().startswith("sbk")}

    assert found
    assert found <= _readme_names()
    assert {"sbkStorySidebar", "sbkStoryTree", "sbkPreviewError", "sbkShortcutsDialog"} <= found
