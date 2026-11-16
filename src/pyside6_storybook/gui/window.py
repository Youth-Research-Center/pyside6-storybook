"""The gallery window: story list, preview and docs tabs, and a side pane with the theme switch and the controls."""

from __future__ import annotations

import logging
from collections.abc import Sequence

from PySide6.QtCore import QEvent, QSignalBlocker, QSize, Qt
from PySide6.QtGui import QCloseEvent, QFont, QKeySequence, QPalette, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFrame,
    QLabel,
    QMainWindow,
    QScrollArea,
    QSplitter,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from pyside6_storybook.discovery import LoadError
from pyside6_storybook.gui.controls_panel import ControlsPanel
from pyside6_storybook.gui.docs_panel import DocsPanel
from pyside6_storybook.gui.error_panel import ErrorPanel
from pyside6_storybook.gui.icons import ActionIcons
from pyside6_storybook.gui.sidebar import LOAD_ERRORS_HEADING, StorySidebar
from pyside6_storybook.registry import Layout, Story, StoryContext, StoryRegistry
from pyside6_storybook.registry.rendering import StoryRenderError, render_story
from pyside6_storybook.themes import BuiltinThemes

NO_STORIES_MESSAGE = "No stories are registered."

_MARGIN = 10
_SPACING = 8
_SECTION_SPACING = 6
_LAYOUT_ALIGNMENTS = {
    Layout.PADDED: Qt.AlignmentFlag.AlignTop,
    Layout.CENTERED: Qt.AlignmentFlag.AlignCenter,
    Layout.FILL: Qt.AlignmentFlag(0),
}
"""The alignment of the previewed widget inside the surface's margins. An empty alignment lets the widget grow in each direction its
size policy allows; where it cannot grow, the layout centres it."""
_SCROLLABLE_LAYOUTS = frozenset({Layout.PADDED, Layout.CENTERED})


class GalleryWindow(QMainWindow):
    """Three panes in a splitter: the story list, the selected story's preview and docs (in tabs), and the theme and controls pane.

    The preview is rebuilt from scratch whenever a control value or the theme changes. A story or decorator that raises, or returns
    something that is not a ``QWidget``, shows an ``ErrorPanel`` in the preview instead; nothing it raises reaches the Qt event loop. Story
    sources that failed to load are listed under a "Load errors" entry at the end of the story list. The chrome is drawn from
    palette roles, so it follows whatever palette the application has.
    """

    def __init__(
        self,
        registry: StoryRegistry,
        themes: BuiltinThemes,
        parent: QWidget | None = None,
        *,
        load_errors: Sequence[LoadError] = (),
    ) -> None:
        """Create the window and select the first entry of the story list.

        Args:
            registry: The stories to show.
            themes: The themes to switch between. The caller activates and deactivates them.
            parent: The owning widget.
            load_errors: Story sources that failed to load, shown under a "Load errors" entry when there are any.
        """
        super().__init__(parent)
        self.setWindowTitle("pyside6-storybook")
        self._logger = logging.getLogger(self.__class__.__name__)
        self._registry = registry
        self._themes = themes
        self._load_errors = tuple(load_errors)
        self._current_story: Story | None = None
        self._controls_panel: ControlsPanel | None = None
        self._preview_widget: QWidget | None = None
        self._preview_root: QWidget | None = None
        self._error_panel: ErrorPanel | None = None
        self._icons = ActionIcons()

        self._sidebar = StorySidebar(self, icons=self._icons)
        self._sidebar.setObjectName("storySidebar")
        self._sidebar.set_registry(registry, load_errors=self._load_errors)

        self._heading = QLabel("", self)
        self._heading.setObjectName("previewHeading")
        self._heading.setFont(self._bold_font(self._heading))

        self._preview_scroll = QScrollArea(self)
        self._preview_scroll.setObjectName("previewScroll")
        self._preview_scroll.setFrameShape(QFrame.Shape.StyledPanel)
        self._preview_scroll.setWidgetResizable(True)
        self._preview_scroll.viewport().setBackgroundRole(QPalette.ColorRole.Window)
        self._preview_surface = QFrame(self._preview_scroll)
        self._preview_surface.setObjectName("previewSurface")
        self._preview_surface.setFrameShape(QFrame.Shape.NoFrame)
        # Window, not Base: stories are shown on the background they sit on in an application window, where Fusion's input fields
        # and check boxes (drawn in Base with an outline derived from Window) stand out. On Base they vanish in the Dark theme.
        self._preview_surface.setBackgroundRole(QPalette.ColorRole.Window)
        self._preview_surface.setAutoFillBackground(True)
        self._preview_layout = QVBoxLayout(self._preview_surface)
        self._preview_layout.setContentsMargins(_MARGIN, _MARGIN, _MARGIN, _MARGIN)
        self._preview_scroll.setWidget(self._preview_surface)
        self._empty_label = QLabel(NO_STORIES_MESSAGE, self._preview_surface)
        self._empty_label.setObjectName("previewEmptyState")
        self._empty_label.setForegroundRole(QPalette.ColorRole.PlaceholderText)
        self._empty_label.setVisible(len(registry) == 0 and not self._load_errors)
        self._preview_layout.addWidget(self._empty_label, alignment=Qt.AlignmentFlag.AlignTop)

        self._docs_panel = DocsPanel(self, icons=self._icons)
        self._docs_scroll = QScrollArea(self)
        self._docs_scroll.setObjectName("docsScroll")
        self._docs_scroll.setFrameShape(QFrame.Shape.StyledPanel)
        self._docs_scroll.setWidgetResizable(True)
        self._docs_scroll.setWidget(self._docs_panel)
        self._docs_panel.storyRequested.connect(self.select_story)

        # Document mode keeps the tab frame from taking width away from the preview.
        self._preview_tabs = QTabWidget(self)
        self._preview_tabs.setObjectName("previewTabs")
        self._preview_tabs.setAccessibleName("Preview")
        self._preview_tabs.setDocumentMode(True)
        self._preview_tabs.addTab(self._preview_scroll, "Canvas")
        self._preview_tabs.addTab(self._docs_scroll, "Docs")

        preview_pane = QWidget(self)
        preview_layout = QVBoxLayout(preview_pane)
        preview_layout.setContentsMargins(_MARGIN, _MARGIN, _MARGIN, _MARGIN)
        preview_layout.setSpacing(_SPACING)
        preview_layout.addWidget(self._heading)
        preview_layout.addWidget(self._preview_tabs, stretch=1)

        self._theme_switch = QComboBox(self)
        self._theme_switch.setObjectName("themeSwitch")
        self._theme_switch.setAccessibleName("Theme")
        self._theme_switch.addItems(themes.names)
        self._theme_switch.setCurrentIndex(self._theme_switch.findText(themes.current))
        self._theme_switch.currentIndexChanged.connect(self._on_theme_switch_changed)

        self._controls_host = QWidget(self)
        self._controls_host_layout = QVBoxLayout(self._controls_host)
        self._controls_host_layout.setContentsMargins(0, 0, 0, 0)
        self._controls_host_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._controls_scroll = QScrollArea(self)
        self._controls_scroll.setObjectName("controlsScroll")
        self._controls_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._controls_scroll.setWidgetResizable(True)
        self._controls_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._controls_scroll.setWidget(self._controls_host)

        side_pane = QWidget(self)
        side_layout = QVBoxLayout(side_pane)
        side_layout.setContentsMargins(_MARGIN, _MARGIN, _MARGIN, _MARGIN)
        side_layout.setSpacing(_SPACING * 2)
        side_layout.addWidget(self._build_section("Theme", self._theme_switch, side_pane))
        side_layout.addWidget(self._build_section("Controls", self._controls_scroll, side_pane), stretch=1)

        splitter = QSplitter(self)
        splitter.addWidget(self._sidebar)
        splitter.addWidget(preview_pane)
        splitter.addWidget(side_pane)
        splitter.setSizes([200, 500, 300])
        self.setCentralWidget(splitter)

        self._sidebar.storySelected.connect(self._on_story_selected)
        self._sidebar.loadErrorsSelected.connect(self._on_load_errors_selected)
        self._search_shortcuts = (
            QShortcut(QKeySequence("Ctrl+F"), self, self._sidebar.focus_search),
            QShortcut(QKeySequence(Qt.Key.Key_Slash), self, self._on_slash_shortcut),
        )
        self._sidebar.select_first()

    def current_preview_widget(self) -> QWidget | None:
        """Return the widget the story built, without its decorators, or ``None`` if there is none (also while an error is shown)."""
        return self._preview_widget

    def current_story_id(self) -> str | None:
        """Return the id of the selected story, or ``None`` if there is none."""
        return self._current_story.id if self._current_story is not None else None

    def select_story(self, story_id: str) -> bool:
        """Select a story in the sidebar, clearing the search if it hides the story, and show it.

        Args:
            story_id: The id of the story.

        Returns:
            ``False`` if there is no story with this id, else ``True``.
        """
        return self._sidebar.select_story(story_id)

    def set_registry(self, registry: StoryRegistry, *, load_errors: Sequence[LoadError] = ()) -> None:
        """Show another set of stories and render the selected one again, once.

        The selected story stays selected if the new registry still has its id, and keeps its control values when each control still
        accepts its value; otherwise the controls start at their defaults. When the story is gone, the first entry is selected.

        Args:
            registry: The stories to show.
            load_errors: Story sources that failed to load, shown under a "Load errors" entry when there are any.
        """
        previous_id = self.current_story_id()
        previous_values = self._controls_panel.values() if self._controls_panel is not None else {}
        showing_errors = self._sidebar.load_errors_selected()
        self._registry = registry
        self._load_errors = tuple(load_errors)
        self._empty_label.setVisible(len(registry) == 0 and not self._load_errors)
        self._sidebar.set_registry(registry, load_errors=self._load_errors)
        if previous_id is not None and self._sidebar.selected_story_id() == previous_id:
            self._show_story(registry.get(previous_id), previous_values)
        elif showing_errors and self._sidebar.load_errors_selected():
            self._show_load_errors()
        elif not self._sidebar.select_first():
            self._show_nothing()

    def set_theme(self, name: str) -> None:
        """Switch the theme and rebuild the preview.

        Args:
            name: One of the theme names of the ``BuiltinThemes`` the window was created with.

        Raises:
            ValueError: If ``name`` is not a theme name.
        """
        self._themes.set_theme(name)
        with QSignalBlocker(self._theme_switch):
            self._theme_switch.setCurrentIndex(self._theme_switch.findText(name))
        self._rebuild_preview()

    def changeEvent(self, event: QEvent) -> None:
        """Render the chrome's icons again when the application's or the window's palette changes."""
        super().changeEvent(event)
        if event.type() in (QEvent.Type.ApplicationPaletteChange, QEvent.Type.PaletteChange):
            self._icons.retint(self.palette())

    def closeEvent(self, event: QCloseEvent) -> None:
        """Release the previewed widget when the window closes."""
        self._clear_preview()
        super().closeEvent(event)

    @staticmethod
    def _bold_font(widget: QWidget) -> QFont:
        font = widget.font()
        font.setBold(True)
        return font

    def _build_section(self, title: str, content: QWidget, parent: QWidget) -> QWidget:
        section = QWidget(parent)
        layout = QVBoxLayout(section)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(_SECTION_SPACING)
        title_label = QLabel(title, section)
        title_label.setFont(self._bold_font(title_label))
        layout.addWidget(title_label)
        layout.addWidget(content)
        return section

    def _on_theme_switch_changed(self, index: int) -> None:
        if index >= 0:
            self.set_theme(self._theme_switch.itemText(index))

    def _on_slash_shortcut(self) -> None:
        focus = QApplication.focusWidget()
        if isinstance(focus, QComboBox) and not focus.isEditable():
            return
        self._sidebar.focus_search()

    def _on_story_selected(self, story_id: str) -> None:
        if self._current_story is not None and self._current_story.id == story_id and self._controls_panel is not None:
            return
        self._show_story(self._registry.get(story_id), {})

    def _on_load_errors_selected(self) -> None:
        if self._current_story is None and self._heading.text() == LOAD_ERRORS_HEADING:
            return
        self._show_load_errors()

    def _show_nothing(self) -> None:
        self._clear_preview()
        self._clear_controls()
        self._current_story = None
        self._heading.setText("")
        self._docs_panel.clear()
        self._place_preview(None, Layout.FILL)

    def _show_load_errors(self) -> None:
        self._show_nothing()
        self._heading.setText(LOAD_ERRORS_HEADING)
        self._show_error(_load_errors_title(self._load_errors), _load_errors_details(self._load_errors))

    def _show_story(self, story: Story, values: dict[str, object]) -> None:
        """Show a story with its controls, starting each control at its value in ``values`` if every control accepts it."""
        self._show_nothing()
        self._current_story = story
        self._heading.setText(story.id)
        self._docs_panel.show_story(story, self._registry)
        try:
            panel = ControlsPanel(story.controls, self._controls_host, values=values or story.default_args())
        except (TypeError, ValueError):
            panel = ControlsPanel(story.controls, self._controls_host, values=story.default_args())
        panel.valuesChanged.connect(self._on_values_changed)
        self._controls_host_layout.addWidget(panel)
        self._controls_panel = panel
        self._rebuild_preview()

    def _on_values_changed(self, _values: dict[str, object]) -> None:
        self._rebuild_preview()

    def _rebuild_preview(self) -> None:
        """Build the selected story's widget with the current arguments and theme and show it in place of the previous one.

        If the story or a decorator fails, the error is logged and shown in an ``ErrorPanel``.
        """
        story = self._current_story
        panel = self._controls_panel
        if story is None or panel is None:
            return
        self._clear_preview()
        try:
            rendered = render_story(story, StoryContext(args=panel.values(), theme=self._themes.current), registry=self._registry)
        except StoryRenderError as error:
            self._logger.error("Story %r failed to render: %s", story.id, error.title, exc_info=error)
            self._show_error(error.title, error.details)
            return
        self._preview_widget = rendered.widget
        self._preview_root = rendered.root
        self._place_preview(rendered.root, story.layout if story.layout is not None else self._registry.default_layout)

    def _show_error(self, title: str, details: str) -> None:
        self._clear_preview()
        self._error_panel = ErrorPanel(title, details, self._preview_surface)
        self._place_preview(self._error_panel, Layout.FILL)

    def _place_preview(self, widget: QWidget | None, layout: Layout) -> None:
        """Put ``widget`` in the preview surface for ``layout``, or reset the surface when ``widget`` is ``None``.

        This sets the widget's alignment in the surface, the surface's minimum size and the scroll bar policies. In ``PADDED`` and
        ``CENTERED`` the surface is at least as large as the widget's natural size plus the margins, so the preview scrolls instead
        of squashing the widget. In ``FILL`` there is no minimum and no scroll bar.

        Args:
            widget: A child of the preview surface, or ``None`` to reset the surface.
            layout: How to place the widget.
        """
        policy = Qt.ScrollBarPolicy.ScrollBarAsNeeded if layout in _SCROLLABLE_LAYOUTS else Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        self._preview_scroll.setHorizontalScrollBarPolicy(policy)
        self._preview_scroll.setVerticalScrollBarPolicy(policy)
        self._preview_surface.setMinimumSize(0, 0)
        if widget is None:
            return
        self._preview_layout.addWidget(widget)
        self._preview_layout.setAlignment(widget, _LAYOUT_ALIGNMENTS[layout])
        if layout not in _SCROLLABLE_LAYOUTS:
            return
        margins = self._preview_layout.contentsMargins()
        extra = QSize(margins.left() + margins.right(), margins.top() + margins.bottom())
        if widget.hasHeightForWidth():
            self._preview_surface.setMinimumWidth(widget.minimumSizeHint().width() + extra.width())
        else:
            natural = widget.sizeHint().expandedTo(widget.minimumSize()).boundedTo(widget.maximumSize())
            self._preview_surface.setMinimumSize(natural + extra)

    def _clear_preview(self) -> None:
        for widget in (self._preview_root, self._error_panel):
            if widget is not None:
                self._preview_layout.removeWidget(widget)
                widget.hide()
                widget.deleteLater()
        self._preview_widget = None
        self._preview_root = None
        self._error_panel = None

    def _clear_controls(self) -> None:
        panel = self._controls_panel
        self._controls_panel = None
        if panel is not None:
            self._controls_host_layout.removeWidget(panel)
            panel.hide()
            panel.deleteLater()


def _load_errors_title(errors: Sequence[LoadError]) -> str:
    noun = "story source" if len(errors) == 1 else "story sources"
    return f"{len(errors)} {noun} failed to load"


def _load_errors_details(errors: Sequence[LoadError]) -> str:
    sections = []
    for error in errors:
        lines = [error.source, error.message]
        if error.details:
            lines += ["", error.details.rstrip("\n")]
        sections.append("\n".join(lines))
    return "\n\n".join(sections)


__all__ = ["LOAD_ERRORS_HEADING", "NO_STORIES_MESSAGE", "GalleryWindow"]
