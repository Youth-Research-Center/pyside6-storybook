"""The gallery window: story list, preview and a side pane with the theme switch and the controls."""

from __future__ import annotations

from PySide6.QtCore import QSignalBlocker, Qt
from PySide6.QtGui import QCloseEvent, QFont, QPalette
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from pyside6_storybook.controls_panel import ControlsPanel
from pyside6_storybook.registry import Story, StoryContext, StoryRegistry
from pyside6_storybook.themes import BuiltinThemes

NO_STORIES_MESSAGE = "No stories are registered."

_MARGIN = 10
_SPACING = 8
_SECTION_SPACING = 6


class GalleryWindow(QMainWindow):
    """Three panes in a splitter: the story list, the selected story's preview and the theme and controls pane.

    The preview is rebuilt from scratch whenever a control value or the theme changes. The chrome is drawn from palette roles,
    so it follows whatever palette the application has.
    """

    def __init__(self, registry: StoryRegistry, themes: BuiltinThemes, parent: QWidget | None = None) -> None:
        """Create the window and select the first story.

        Args:
            registry: The stories to show.
            themes: The themes to switch between. The caller activates and deactivates them.
            parent: The owning widget.
        """
        super().__init__(parent)
        self.setWindowTitle("pyside6-storybook")
        self._registry = registry
        self._themes = themes
        self._current_story: Story | None = None
        self._controls_panel: ControlsPanel | None = None
        self._preview_widget: QWidget | None = None

        self._sidebar = QListWidget(self)
        self._sidebar.setObjectName("storySidebar")
        self._sidebar.setAccessibleName("Stories")
        for story in registry:
            item = QListWidgetItem(story.id, self._sidebar)
            item.setData(Qt.ItemDataRole.UserRole, story.id)

        self._heading = QLabel("", self)
        self._heading.setObjectName("previewHeading")
        self._heading.setFont(self._bold_font(self._heading))

        self._preview_surface = QFrame(self)
        self._preview_surface.setObjectName("previewSurface")
        self._preview_surface.setFrameShape(QFrame.Shape.StyledPanel)
        self._preview_surface.setBackgroundRole(QPalette.ColorRole.Base)
        self._preview_surface.setAutoFillBackground(True)
        self._preview_layout = QVBoxLayout(self._preview_surface)
        self._preview_layout.setContentsMargins(_MARGIN, _MARGIN, _MARGIN, _MARGIN)
        self._preview_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._empty_label = QLabel(NO_STORIES_MESSAGE, self._preview_surface)
        self._empty_label.setObjectName("previewEmptyState")
        self._empty_label.setForegroundRole(QPalette.ColorRole.PlaceholderText)
        self._empty_label.setVisible(len(registry) == 0)
        self._preview_layout.addWidget(self._empty_label)

        preview_pane = QWidget(self)
        preview_layout = QVBoxLayout(preview_pane)
        preview_layout.setContentsMargins(_MARGIN, _MARGIN, _MARGIN, _MARGIN)
        preview_layout.setSpacing(_SPACING)
        preview_layout.addWidget(self._heading)
        preview_layout.addWidget(self._preview_surface, stretch=1)

        self._theme_switch = QComboBox(self)
        self._theme_switch.setObjectName("themeSwitch")
        self._theme_switch.setAccessibleName("Theme")
        self._theme_switch.addItems(themes.names)
        self._theme_switch.setCurrentIndex(self._theme_switch.findText(themes.current))
        self._theme_switch.currentIndexChanged.connect(self._on_theme_switch_changed)

        self._controls_host = QWidget(self)
        self._controls_host_layout = QVBoxLayout(self._controls_host)
        self._controls_host_layout.setContentsMargins(0, 0, 0, 0)

        side_pane = QWidget(self)
        side_layout = QVBoxLayout(side_pane)
        side_layout.setContentsMargins(_MARGIN, _MARGIN, _MARGIN, _MARGIN)
        side_layout.setSpacing(_SPACING * 2)
        side_layout.addWidget(self._build_section("Theme", self._theme_switch, side_pane))
        side_layout.addWidget(self._build_section("Controls", self._controls_host, side_pane))
        side_layout.addStretch(1)

        splitter = QSplitter(self)
        splitter.addWidget(self._sidebar)
        splitter.addWidget(preview_pane)
        splitter.addWidget(side_pane)
        splitter.setSizes([200, 500, 300])
        self.setCentralWidget(splitter)

        self._sidebar.currentItemChanged.connect(self._on_story_selected)
        if self._sidebar.count():
            self._sidebar.setCurrentRow(0)

    def current_preview_widget(self) -> QWidget | None:
        """Return the widget currently shown in the preview, or ``None`` if there is none."""
        return self._preview_widget

    def current_story_id(self) -> str | None:
        """Return the id of the selected story, or ``None`` if there is none."""
        return self._current_story.id if self._current_story is not None else None

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

    def _on_story_selected(self, current: QListWidgetItem | None, _previous: QListWidgetItem | None) -> None:
        self._clear_preview()
        self._clear_controls()
        if current is None:
            self._current_story = None
            self._heading.setText("")
            return
        story = self._registry.get(current.data(Qt.ItemDataRole.UserRole))
        self._current_story = story
        self._heading.setText(story.id)
        panel = ControlsPanel(story.controls, self._controls_host)
        panel.valuesChanged.connect(self._on_values_changed)
        self._controls_host_layout.addWidget(panel)
        self._controls_panel = panel
        self._rebuild_preview()

    def _on_values_changed(self, _values: dict[str, object]) -> None:
        self._rebuild_preview()

    def _rebuild_preview(self) -> None:
        """Build the selected story's widget with the current arguments and theme and show it in place of the previous one.

        Raises:
            TypeError: If the story returns something that is not a ``QWidget``.
        """
        story = self._current_story
        panel = self._controls_panel
        if story is None or panel is None:
            return
        self._clear_preview()
        widget = story(StoryContext(args=panel.values(), theme=self._themes.current))
        if not isinstance(widget, QWidget):
            raise TypeError(f"Story {story.id!r} returned {widget!r}, expected a QWidget")
        self._preview_layout.addWidget(widget)
        self._preview_widget = widget

    def _clear_preview(self) -> None:
        widget = self._preview_widget
        self._preview_widget = None
        if widget is not None:
            self._preview_layout.removeWidget(widget)
            widget.hide()
            widget.deleteLater()

    def _clear_controls(self) -> None:
        panel = self._controls_panel
        self._controls_panel = None
        if panel is not None:
            self._controls_host_layout.removeWidget(panel)
            panel.hide()
            panel.deleteLater()


__all__ = ["NO_STORIES_MESSAGE", "GalleryWindow"]
