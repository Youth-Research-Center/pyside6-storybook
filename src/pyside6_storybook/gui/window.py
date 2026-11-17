"""The gallery window: story list, preview and docs tabs, and a side pane with the theme switch, the controls and the actions log."""

from __future__ import annotations

import functools
import itertools
import logging
import traceback
import weakref
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from enum import Enum
from typing import TypeVar

import shiboken6
from PySide6.QtCore import QEvent, QSignalBlocker, Qt
from PySide6.QtGui import QAction, QCloseEvent, QFont, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHeaderView,
    QLabel,
    QMainWindow,
    QScrollArea,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from pyside6_storybook.controls import Control, EnumControl
from pyside6_storybook.discovery import LoadError
from pyside6_storybook.discovery.reload import ReloadResult, ReloadSession
from pyside6_storybook.gui.actions_panel import ActionsPanel
from pyside6_storybook.gui.canvas import Canvas
from pyside6_storybook.gui.controls_panel import ControlsPanel
from pyside6_storybook.gui.docs_panel import DocsPanel
from pyside6_storybook.gui.error_panel import ErrorPanel
from pyside6_storybook.gui.icons import ActionIcons
from pyside6_storybook.gui.reload_status import ReloadStatus
from pyside6_storybook.gui.reload_watcher import ReloadWatcher
from pyside6_storybook.gui.sidebar import LOAD_ERRORS_HEADING, StorySidebar
from pyside6_storybook.polishing import polish_all_widgets
from pyside6_storybook.registry import Layout, Story, StoryContext, StoryRegistry
from pyside6_storybook.registry.rendering import StoryRenderError, render_story
from pyside6_storybook.themes import ThemeProvider

NO_STORIES_MESSAGE = "No stories are registered."
NO_STORIES_FOUND_MESSAGE = "No stories were found"

_MARGIN = 10
_SPACING = 8
_SECTION_SPACING = 6
_HELP_KEYS = "F1"
_HELP_DESCRIPTION = "Show the keyboard shortcuts"
SHORTCUTS_HEADERS = ("Keys", "Action")
_THEME_ERROR_TITLE = "Theme provider failed"

_T = TypeVar("_T")


@dataclass(frozen=True)
class _Shortcut:
    """One window shortcut: the keys, the line the Keyboard shortcuts dialog shows, and the name of the window method it calls."""

    keys: str
    description: str
    handler: str


_WINDOW_SHORTCUTS = (
    _Shortcut("Ctrl+F", "Focus the search field", "_focus_search"),
    _Shortcut("/", "Focus the search field, except while typing in a field", "_on_slash_shortcut"),
    _Shortcut("Ctrl+Alt+Down", "Open the next story in the list", "_select_next_story"),
    _Shortcut("Ctrl+Alt+Up", "Open the previous story in the list", "_select_previous_story"),
    _Shortcut("Ctrl+T", "Switch to the next theme", "_select_next_theme"),
    _Shortcut("F6", "Move focus to the next pane", "_focus_next_pane"),
    _Shortcut("Shift+F6", "Move focus to the previous pane", "_focus_previous_pane"),
)
"""Every shortcut the window creates, and the rows of the Keyboard shortcuts dialog; the canvas lists its own through ``shortcut_help``."""


class GalleryWindow(QMainWindow):
    """Three panes in a splitter: the story list, the selected story's preview and docs (in tabs), and the side pane.

    The side pane is the theme switch over Controls and Actions tabs.

    The preview is rebuilt from scratch whenever a control value or the theme changes. A story or decorator that raises, or returns
    something that is not a ``QWidget``, shows an ``ErrorPanel`` in the preview instead; nothing it raises reaches the Qt event loop. Story
    sources that failed to load are listed under a "Load errors" entry at the end of the story list. The chrome is drawn from
    palette roles, so it follows whatever palette the application has.
    """

    def __init__(
        self,
        registry: StoryRegistry,
        theme_provider: ThemeProvider,
        parent: QWidget | None = None,
        *,
        load_errors: Sequence[LoadError] = (),
        reload: ReloadSession | None = None,
    ) -> None:
        """Create the window and select the first entry of the story list.

        Args:
            registry: The stories to show.
            theme_provider: The provider of the themes to switch between. The caller activates and deactivates it. The window
                registers one callback with it and guards every call into it: an exception is logged and shown in the preview.
            parent: The owning widget.
            load_errors: Story sources that failed to load, shown under a "Load errors" entry when there are any.
            reload: What to load again when a story file changes. The window then watches the files, applies each reload and shows
                its status in the status bar. Without it nothing is reloaded and the status bar is hidden.
        """
        super().__init__(parent)
        self.setWindowTitle("pyside6-storybook")
        self._logger = logging.getLogger(self.__class__.__name__)
        self._registry = registry
        self._theme_provider = theme_provider
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

        self._canvas = Canvas(self, icons=self._icons)
        self._canvas.set_size_presets(registry.size_presets)
        self._canvas.set_empty_message(NO_STORIES_MESSAGE if len(registry) == 0 and not self._load_errors else None)

        self._docs_panel = DocsPanel(self, icons=self._icons)
        self._docs_scroll = QScrollArea(self)
        self._docs_scroll.setObjectName("docsScroll")
        self._docs_scroll.setAccessibleName("Docs")
        self._docs_scroll.setFrameShape(QFrame.Shape.StyledPanel)
        self._docs_scroll.setWidgetResizable(True)
        self._docs_scroll.setWidget(self._docs_panel)
        self._docs_panel.storyRequested.connect(self.select_story)

        # Document mode keeps the tab frame from taking width away from the preview.
        self._preview_tabs = QTabWidget(self)
        self._preview_tabs.setObjectName("previewTabs")
        self._preview_tabs.tabBar().setAccessibleName("Preview tabs")
        self._preview_tabs.setDocumentMode(True)
        self._preview_tabs.addTab(self._canvas, "Canvas")
        self._preview_tabs.addTab(self._docs_scroll, "Docs")

        preview_pane = QWidget(self)
        preview_pane.setAccessibleName("Preview")
        preview_layout = QVBoxLayout(preview_pane)
        preview_layout.setContentsMargins(_MARGIN, _MARGIN, _MARGIN, _MARGIN)
        preview_layout.setSpacing(_SPACING)
        preview_layout.addWidget(self._heading)
        preview_layout.addWidget(self._preview_tabs, stretch=1)

        self._theme_switch = QComboBox(self)
        self._theme_switch.setObjectName("themeSwitch")
        self._theme_switch.setAccessibleName("Theme")
        # A provider that fails while the window is built is shown in the preview once the window is complete.
        self._startup_provider_error: Exception | None = None
        self._theme_switch.addItems(self._call_provider(self._theme_provider.theme_names, default=(), report=False))
        self._sync_theme_switch()
        self._theme_switch.currentIndexChanged.connect(self._on_theme_switch_changed)
        # The provider can outlive the window, so it gets a callback that does not keep the window alive.
        handler: weakref.WeakMethod[Callable[[], None]] = weakref.WeakMethod(self._on_provider_changed)
        self._call_provider(self._theme_provider.on_changed, functools.partial(_call_weak_method, handler), default=None, report=False)

        self._controls_host = QWidget(self)
        self._controls_host_layout = QVBoxLayout(self._controls_host)
        self._controls_host_layout.setContentsMargins(0, 0, 0, 0)
        self._controls_host_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._controls_scroll = QScrollArea(self)
        self._controls_scroll.setObjectName("controlsScroll")
        # The editors in it take focus and the scroll area follows them, so it is not a stop of its own.
        self._controls_scroll.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._controls_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._controls_scroll.setWidgetResizable(True)
        self._controls_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._controls_scroll.setWidget(self._controls_host)

        self._actions_panel = ActionsPanel(self, icons=self._icons)
        self._side_tabs = QTabWidget(self)
        self._side_tabs.setObjectName("sideTabs")
        self._side_tabs.tabBar().setAccessibleName("Controls and actions tabs")
        self._side_tabs.setDocumentMode(True)
        self._side_tabs.addTab(self._controls_scroll, "Controls")
        self._side_tabs.addTab(self._actions_panel, "Actions")

        side_pane = QWidget(self)
        side_pane.setAccessibleName("Controls and actions")
        side_layout = QVBoxLayout(side_pane)
        side_layout.setContentsMargins(_MARGIN, _MARGIN, _MARGIN, _MARGIN)
        side_layout.setSpacing(_SPACING * 2)
        side_layout.addWidget(self._build_section("Theme", self._theme_switch, side_pane))
        side_layout.addWidget(self._side_tabs, stretch=1)

        self._preview_pane = preview_pane
        self._side_pane = side_pane
        splitter = QSplitter(self)
        splitter.addWidget(self._sidebar)
        splitter.addWidget(preview_pane)
        splitter.addWidget(side_pane)
        splitter.setSizes([200, 560, 300])
        self.setCentralWidget(splitter)

        self._sidebar.storySelected.connect(self._on_story_selected)
        self._sidebar.loadErrorsSelected.connect(self._on_load_errors_selected)
        self._shortcuts = [QShortcut(QKeySequence(shortcut.keys), self, getattr(self, shortcut.handler)) for shortcut in _WINDOW_SHORTCUTS]
        self._shortcuts_dialog: QDialog | None = None
        self._last_focus: dict[QWidget, QWidget] = {}
        self._build_help_menu()
        app = QApplication.instance()
        if isinstance(app, QApplication):
            app.focusChanged.connect(self._on_focus_changed)
        self._reload_status = ReloadStatus(self)
        self.statusBar().addWidget(self._reload_status, 1)
        self.statusBar().setVisible(reload is not None)
        if reload is not None:
            self._reload_watcher = ReloadWatcher(reload, self)
            self._reload_watcher.reloaded.connect(self._on_reloaded)
        self._apply_tab_order()
        self._polish_widgets()
        self._sidebar.select_first()
        if self._startup_provider_error is not None:
            self._show_provider_error(self._startup_provider_error)

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

        The selected story stays selected if the new registry still has its id. Each of its controls keeps its value when the new
        control of the same name accepts it, and starts at its default otherwise; for an ``EnumControl`` whose old member belongs to
        another enum class (a reloaded project enum) the member of the same name counts as accepted. If the story is gone, the story
        that took its row position is selected, or else the last one; with no stories, the "Load errors" entry or nothing. The actions
        log is kept when the same story stays selected.

        Args:
            registry: The stories to show.
            load_errors: Story sources that failed to load, shown under a "Load errors" entry when there are any.
        """
        previous_id = self.current_story_id()
        previous_values = self._controls_panel.values() if self._controls_panel is not None else {}
        previous_order = self._sidebar.story_ids()
        showing_errors = self._sidebar.load_errors_selected()
        self._registry = registry
        self._load_errors = tuple(load_errors)
        self._canvas.set_empty_message(NO_STORIES_MESSAGE if len(registry) == 0 and not self._load_errors else None)
        self._canvas.set_size_presets(registry.size_presets)
        self._sidebar.set_registry(registry, load_errors=self._load_errors)
        order = self._sidebar.story_ids()
        if previous_id is not None and previous_id in order:
            story = registry.get(previous_id)
            self._show_story(story, _carried_values(story, previous_values))
        elif previous_id is not None and order:
            position = previous_order.index(previous_id) if previous_id in previous_order else 0
            self._sidebar.select_story(order[min(position, len(order) - 1)])
        elif showing_errors and self._sidebar.load_errors_selected():
            self._show_load_errors()
        elif not self._sidebar.select_first():
            self._show_nothing()

    def set_theme(self, name: str) -> None:
        """Ask the theme provider for a theme. The provider's change notification then updates the switch and rebuilds the preview.

        If the provider raises, the error is logged and shown in the preview, and the switch shows the provider's current theme.

        Args:
            name: One of the names the provider lists in ``theme_names``.

        Raises:
            ValueError: If ``name`` is not one of them. The provider is not called and the preview does not change.
        """
        names = self._call_provider(self._theme_provider.theme_names, default=None)
        if names is None:
            return
        if name not in names:
            raise ValueError(f"Unknown theme {name!r}; expected one of {tuple(names)}")
        polish_all_widgets()  # the provider may change the application style sheet; see pyside6_storybook.polishing
        self._call_provider(self._theme_provider.set_theme, name, default=None)

    def _call_provider(self, function: Callable[..., _T], *args: object, default: _T, report: bool = True) -> _T:
        """Call into the theme provider; an exception is logged and ``default`` returned.

        The exception is shown in the preview at once when ``report`` is set; otherwise (while the window is being built) the first one is
        kept and shown when the window is complete.
        """
        try:
            return function(*args)
        except Exception as error:
            self._logger.error("Theme provider call %s failed", getattr(function, "__name__", function), exc_info=error)
            if report:
                self._show_provider_error(error)
            elif self._startup_provider_error is None:
                self._startup_provider_error = error
            return default

    def _show_provider_error(self, error: Exception) -> None:
        details = "".join(traceback.format_exception(error))
        self._show_error(f"{_THEME_ERROR_TITLE}: {type(error).__name__}: {error}", details)
        self._sync_theme_switch()

    def _sync_theme_switch(self) -> None:
        """Select the provider's current theme in the switch, or leave the switch as it was if the provider fails."""
        try:
            name = self._theme_provider.current_theme()
        except Exception:
            self._logger.exception("Theme provider call current_theme failed")
            return
        with QSignalBlocker(self._theme_switch):
            self._theme_switch.setCurrentIndex(self._theme_switch.findText(name))

    def _on_provider_changed(self) -> None:
        """Follow a theme change the provider announces: update the switch and rebuild the preview. Never raises."""
        if not shiboken6.isValid(self):
            return
        try:
            self._sync_theme_switch()
            self._rebuild_preview()
        except Exception:
            self._logger.exception("Handling a theme change failed")

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

    def _focus_search(self) -> None:
        self._sidebar.focus_search()

    def _step_story(self, step: int) -> None:
        """Open the story ``step`` rows after the current one among the stories the search keeps; the ends do not wrap.

        When the current story is hidden by the search, a step forward opens the first visible story and a step back the last.
        """
        ids = self._sidebar.visible_story_ids()
        if not ids:
            return
        current = self.current_story_id()
        if current in ids:
            index = ids.index(current) + step
        else:
            index = 0 if step > 0 else len(ids) - 1
        target = ids[max(0, min(index, len(ids) - 1))]
        if target != current:
            self.select_story(target)

    def _select_next_story(self) -> None:
        self._step_story(1)

    def _select_previous_story(self) -> None:
        self._step_story(-1)

    def _select_next_theme(self) -> None:
        names = tuple(self._call_provider(self._theme_provider.theme_names, default=()))
        current = self._call_provider(self._theme_provider.current_theme, default=None)
        if len(names) > 1 and current in names:
            self.set_theme(names[(names.index(current) + 1) % len(names)])

    def _panes(self) -> tuple[QWidget, ...]:
        return (self._sidebar, self._preview_pane, self._side_pane)

    def _first_in_pane(self, pane: QWidget) -> QWidget:
        if pane is self._sidebar:
            return self._sidebar.focus_chain()[0]
        return self._preview_tabs.tabBar() if pane is self._preview_pane else self._theme_switch

    def _pane_of(self, widget: QWidget | None) -> QWidget | None:
        if widget is None:
            return None
        return next((pane for pane in self._panes() if pane is widget or pane.isAncestorOf(widget)), None)

    def _on_focus_changed(self, _old: QWidget | None, new: QWidget | None) -> None:
        """Remember the last widget that had focus in each pane, for F6."""
        if not shiboken6.isValid(self) or new is None:
            return
        pane = self._pane_of(new)
        if pane is not None:
            self._last_focus[pane] = new

    def _move_to_pane(self, step: int) -> None:
        """Focus the pane ``step`` places after the one with focus, at its last focused widget or else its first."""
        panes = self._panes()
        current = self._pane_of(QApplication.focusWidget())
        index = panes.index(current) + step if current is not None else (0 if step > 0 else len(panes) - 1)
        pane = panes[index % len(panes)]
        remembered = self._last_focus.get(pane)
        usable = (
            remembered is not None
            and shiboken6.isValid(remembered)
            and remembered.isVisible()
            and remembered.isEnabled()
            and pane.isAncestorOf(remembered)
        )
        target = remembered if usable and remembered is not None else self._first_in_pane(pane)
        target.setFocus(Qt.FocusReason.TabFocusReason)

    def _focus_next_pane(self) -> None:
        self._move_to_pane(1)

    def _focus_previous_pane(self) -> None:
        self._move_to_pane(-1)

    def _build_help_menu(self) -> None:
        menu = self.menuBar().addMenu("&Help")
        action = QAction("&Keyboard shortcuts", menu)
        action.setShortcut(QKeySequence(_HELP_KEYS))
        action.triggered.connect(self._show_shortcuts_dialog)
        menu.addAction(action)

    def shortcut_rows(self) -> list[tuple[str, str]]:
        """Return every shortcut the window has as ``(keys, description)`` pairs, in the order the Keyboard shortcuts dialog lists them.

        The rows come from the tables that create the shortcuts, so a shortcut cannot be missing from the dialog.
        """
        native = QKeySequence.SequenceFormat.NativeText
        rows = [(QKeySequence(shortcut.keys).toString(native), shortcut.description) for shortcut in _WINDOW_SHORTCUTS]
        rows.extend(self._canvas.shortcut_help())
        rows.append((QKeySequence(_HELP_KEYS).toString(native), _HELP_DESCRIPTION))
        return rows

    def _show_shortcuts_dialog(self) -> None:
        """Open the Keyboard shortcuts dialog without blocking; it is deleted when it closes."""
        existing = self._shortcuts_dialog
        if existing is not None and shiboken6.isValid(existing):
            existing.raise_()
            existing.activateWindow()
            return
        dialog = QDialog(self)
        dialog.setObjectName("shortcutsDialog")
        dialog.setWindowTitle("Keyboard shortcuts")
        rows = self.shortcut_rows()
        table = QTableWidget(len(rows), len(SHORTCUTS_HEADERS), dialog)
        table.setObjectName("shortcutsTable")
        table.setAccessibleName("Keyboard shortcuts")
        table.setHorizontalHeaderLabels(list(SHORTCUTS_HEADERS))
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        table.setSizeAdjustPolicy(QAbstractItemView.SizeAdjustPolicy.AdjustToContents)
        table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        table.horizontalHeader().setStretchLastSection(True)
        for row, cells in enumerate(rows):
            for column, text in enumerate(cells):
                table.setItem(row, column, QTableWidgetItem(text))
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, dialog)
        buttons.rejected.connect(dialog.reject)
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(_MARGIN, _MARGIN, _MARGIN, _MARGIN)
        layout.setSpacing(_SPACING)
        layout.addWidget(table)
        layout.addWidget(buttons)
        dialog.finished.connect(self._on_shortcuts_dialog_finished)
        self._shortcuts_dialog = dialog
        dialog.open()

    def _on_shortcuts_dialog_finished(self) -> None:
        dialog, self._shortcuts_dialog = self._shortcuts_dialog, None
        if dialog is not None and shiboken6.isValid(dialog):
            dialog.deleteLater()

    def _polish_widgets(self) -> None:
        """Polish every widget now, also those that are hidden and were never shown.

        An application style sheet that is cleared while a widget has never been polished can crash Qt later (see
        ``pyside6_storybook.polishing``), and a theme provider or the application may change the style sheet at any time. Every widget
        of the application is polished, not only the window's: a failed render leaves the story's widget and a decorator's wrapper
        outside the window until their deferred deletion.
        """
        polish_all_widgets()

    def _apply_tab_order(self) -> None:
        """Chain Tab through the window in reading order: search, tree, preview tabs, canvas controls, the preview, then the side pane.

        Widgets are created over time (the story's widget, the controls, the docs), so Qt's creation order would put them last; this runs
        again whenever they change. Hidden widgets stay in the chain and Tab skips them.
        """
        chain: list[QWidget] = [*self._sidebar.focus_chain(), self._preview_tabs, *self._canvas.focus_chain()]
        placed = self._canvas.placed_widget()
        if placed is not None:
            chain.extend(_focus_targets(placed))
        chain.append(self._docs_scroll)
        chain.extend(_focus_targets(self._docs_panel, only_visible=True))
        chain.extend([self._theme_switch, self._side_tabs])
        if self._controls_panel is not None:
            chain.extend(_focus_targets(self._controls_panel))
        chain.extend(_focus_targets(self._actions_panel))
        for first, second in itertools.pairwise(chain):
            if first is not second:
                QWidget.setTabOrder(first, second)

    def _on_story_selected(self, story_id: str) -> None:
        if self._current_story is not None and self._current_story.id == story_id and self._controls_panel is not None:
            return
        self._show_story(self._registry.get(story_id), {})

    def _on_load_errors_selected(self) -> None:
        if self._current_story is None and self._heading.text() == LOAD_ERRORS_HEADING:
            return
        self._show_load_errors()

    def _show_nothing(self, *, keep_actions: bool = False) -> None:
        self._clear_preview()
        if not keep_actions:
            self._actions_panel.clear()
        self._clear_controls()
        self._current_story = None
        self._heading.setText("")
        self._docs_panel.clear()
        self._canvas.clear()
        self._canvas.set_preview_name(None)

    def _show_load_errors(self) -> None:
        self._show_nothing()
        self._heading.setText(LOAD_ERRORS_HEADING)
        self._show_error(_load_errors_title(self._load_errors), _load_errors_details(self._load_errors))

    def _on_reloaded(self, result: ReloadResult) -> None:
        """Apply an accepted reload, or show why a rejected one was not used and keep the stories as they were."""
        if result.accepted:
            self.set_registry(result.load.registry, load_errors=result.load.errors)
            self._reload_status.show_success()
            return
        errors = result.new_errors or result.load.errors
        if errors:
            title, details = _load_errors_title(errors), _load_errors_details(errors)
        else:
            title, details = NO_STORIES_FOUND_MESSAGE, ""
        self._reload_status.show_failure(title)
        self._show_error(title, details)

    def _show_story(self, story: Story, values: dict[str, object]) -> None:
        """Show a story with its controls.

        Each control starts at the story's value for it, or at its value in ``values`` when ``values`` has one that the control accepts.
        """
        self._show_nothing(keep_actions=self._current_story is not None and self._current_story.id == story.id)
        self._current_story = story
        self._heading.setText(story.id)
        self._canvas.set_preview_name(story.id)
        self._docs_panel.show_story(story, self._registry)
        panel = ControlsPanel(story.controls, self._controls_host, values=self._starting_values(story, values))
        panel.valuesChanged.connect(self._on_values_changed)
        self._controls_host_layout.addWidget(panel)
        self._controls_panel = panel
        self._rebuild_preview()

    def _starting_values(self, story: Story, previous: dict[str, object]) -> dict[str, object]:
        starting = story.default_args()
        for control in story.controls:
            if control.name not in previous:
                continue
            try:
                starting[control.name] = control.coerce(previous[control.name])
            except (TypeError, ValueError):
                self._logger.debug("Control %r of story %r rejected its previous value", control.name, story.id)
        return starting

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
        try:
            theme = self._theme_provider.current_theme()
        except Exception as error:
            self._logger.error("Theme provider call current_theme failed", exc_info=error)
            self._show_provider_error(error)
            return
        self._clear_preview()
        try:
            rendered = render_story(
                story,
                StoryContext(args=panel.values(), theme=theme, actions=self._actions_panel.new_sink()),
                registry=self._registry,
            )
        except StoryRenderError as error:
            self._logger.error("Story %r failed to render: %s", story.id, error.title, exc_info=error)
            self._show_error(error.title, error.details)
            return
        self._preview_widget = rendered.widget
        self._preview_root = rendered.root
        self._canvas.place(rendered.root, story.layout if story.layout is not None else self._registry.default_layout)
        self._apply_tab_order()
        self._polish_widgets()

    def _show_error(self, title: str, details: str) -> None:
        self._clear_preview()
        self._error_panel = ErrorPanel(title, details, self._canvas.surface)
        self._canvas.place(self._error_panel, Layout.FILL)
        self._apply_tab_order()
        self._polish_widgets()

    def _clear_preview(self) -> None:
        """Remove the preview, first stopping its widget's actions from being logged, including signals it emits while it is hidden."""
        self._actions_panel.invalidate()
        self._canvas.clear()
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


def _call_weak_method(method: weakref.WeakMethod[Callable[[], None]]) -> None:
    """Call a method through a weak reference, if its object is still alive."""
    target = method()
    if target is not None:
        target()


def _focus_targets(root: QWidget, *, only_visible: bool = False) -> list[QWidget]:
    """Return the widgets in ``root`` (``root`` included) that Tab stops at, in creation order, which is reading order.

    A compound widget, one whose focus proxy is one of its children (an editor, a tab widget), is returned as one entry and its
    children are not searched: ``QWidget.setTabOrder`` moves it together with its inputs. A widget that forwards focus to its parent
    (the line edit inside a spin box) is left to the parent.

    Args:
        root: The widget to search.
        only_visible: Skip hidden widgets and everything inside them. A panel that deletes its content later keeps the old, hidden
            widgets until then.

    Returns:
        The widgets, outermost first.
    """
    targets: list[QWidget] = []

    def visit(widget: QWidget) -> None:
        if only_visible and widget is not root and not widget.isVisibleTo(root):
            return
        if widget.focusPolicy() != Qt.FocusPolicy.NoFocus:
            proxy = widget.focusProxy()
            if proxy is None:
                targets.append(widget)
            elif widget.isAncestorOf(proxy):
                targets.append(widget)
                return
            else:
                return
        for child in widget.children():
            if isinstance(child, QWidget) and not child.isWindow():
                visit(child)

    visit(root)
    return targets


def _carried_values(story: Story, previous: dict[str, object]) -> dict[str, object]:
    """Return the story's starting values, replacing the ones a control of the same name accepts from ``previous``."""
    values = story.default_args()
    for control in story.controls:
        if control.name in previous:
            accepted = _accepted_value(control, previous[control.name])
            if accepted is not _REJECTED:
                values[control.name] = accepted
    return values


_REJECTED = object()
"""Returned by ``_accepted_value`` for a value the control does not accept; ``None`` is a valid value (an empty ``FileControl``)."""


def _accepted_value(control: Control, value: object) -> object:
    """Return ``value`` as the control's value, or the same-named member of a reloaded enum, or ``_REJECTED``."""
    try:
        return control.coerce(value)
    except (TypeError, ValueError):
        if isinstance(control, EnumControl) and isinstance(value, Enum):
            return next((option for option in control.options if option.name == value.name), _REJECTED)
    return _REJECTED


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


__all__ = ["LOAD_ERRORS_HEADING", "NO_STORIES_FOUND_MESSAGE", "NO_STORIES_MESSAGE", "SHORTCUTS_HEADERS", "GalleryWindow"]
