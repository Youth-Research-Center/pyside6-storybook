"""The story sidebar: a search field above a tree of the stories, grouped by the segments of their ids."""

from __future__ import annotations

import logging
from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field

import shiboken6
from PySide6.QtCore import QEvent, QItemSelectionModel, QModelIndex, QObject, QPersistentModelIndex, QSortFilterProxyModel, Qt, Signal
from PySide6.QtGui import QAction, QKeyEvent, QPalette, QStandardItem, QStandardItemModel
from PySide6.QtWidgets import QAbstractItemView, QFrame, QLabel, QLineEdit, QTreeView, QVBoxLayout, QWidget

from pyside6_storybook.discovery import LoadError
from pyside6_storybook.gui.icons import ActionIcons, IconRole
from pyside6_storybook.registry import Story, StoryRegistry

LOAD_ERRORS_HEADING = "Load errors"

_STORY_ID_ROLE = Qt.ItemDataRole.UserRole
_ENTRY_KIND_ROLE = Qt.ItemDataRole.UserRole + 1
_PATH_ROLE = Qt.ItemDataRole.UserRole + 2
_LOAD_ERRORS_ENTRY = "load-errors"
_LOAD_ERRORS_KEY = ""
_MARGIN = 10
_SPACING = 8


@dataclass
class _Node:
    """One row of the tree before it is turned into a ``QStandardItem``."""

    label: str
    path: str
    story: Story | None = None
    children: list[_Node] = field(default_factory=list)


def _build_nodes(registry: StoryRegistry) -> list[_Node]:
    """Group the stories by the segments of their ids: one branch per segment but the last, in the order they first appear.

    A story whose id is also the path of a branch becomes that branch's row, so it is a story row with children.
    """
    roots: list[_Node] = []
    by_path: dict[str, _Node] = {}
    for story in registry:
        siblings = roots
        segments = story.id.split("/")
        for depth, segment in enumerate(segments):
            path = "/".join(segments[: depth + 1])
            node = by_path.get(path)
            if node is None:
                node = _Node(segment, path)
                by_path[path] = node
                siblings.append(node)
            if depth == len(segments) - 1:
                node.story = story
            siblings = node.children
    return roots


def _collapses(node: _Node, depth: int) -> _Node | None:
    """Return the story a branch below the top level stands for when its only child is a story without children, else ``None``."""
    if depth == 0 or node.story is not None or len(node.children) != 1:
        return None
    (child,) = node.children
    return child if child.story is not None and not child.children else None


class _StoryFilterModel(QSortFilterProxyModel):
    """Keeps the story rows whose id contains the search text, and with recursive filtering their ancestors.

    Branches never match by themselves, and the "Load errors" row is hidden while a search is active.
    """

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._text = ""
        self.setRecursiveFilteringEnabled(True)

    def set_text(self, text: str) -> None:
        """Set the search text and filter again."""
        self._text = text.strip().casefold()
        self.refilter()

    def refilter(self) -> None:
        """Evaluate every row again, with the API that replaced ``invalidateFilter`` in Qt 6.10 when this Qt has all of it.

        ``beginFilterChange`` exists since Qt 6.9, but ``endFilterChange`` and the ``Direction`` enum only since Qt 6.10.
        """
        begin = getattr(self, "beginFilterChange", None)
        end = getattr(self, "endFilterChange", None)
        direction = getattr(QSortFilterProxyModel, "Direction", None)
        if begin is None or end is None or direction is None:
            self.invalidateFilter()
            return
        begin()
        end(direction.Rows)

    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex | QPersistentModelIndex) -> bool:
        """Accept every row without a search, else the story rows whose id contains the search text."""
        if not self._text:
            return True
        model = self.sourceModel()
        story_id = model.index(source_row, 0, source_parent).data(_STORY_ID_ROLE)
        return isinstance(story_id, str) and self._text in story_id.casefold()


class StorySidebar(QWidget):
    """A search field and a tree of the stories.

    Moving the current row onto a story, with the keyboard or the mouse, opens it at once. A change of the filter never does: the
    selected story stays selected in the model while the filter hides it, and it is shown selected again when it matches.

    Signals:
        storySelected: Emitted with a story id when the user chose that story, or ``select_story`` did.
        loadErrorsSelected: Emitted when the "Load errors" row was chosen.
    """

    storySelected = Signal(str)
    loadErrorsSelected = Signal()

    def __init__(self, parent: QWidget | None = None, *, icons: ActionIcons | None = None) -> None:
        """Create an empty sidebar; ``set_registry`` fills it.

        Args:
            parent: The owning widget.
            icons: The registry that keeps the search icon tinted from the palette. The sidebar keeps its own when omitted.
        """
        super().__init__(parent)
        self._logger = logging.getLogger(self.__class__.__name__)
        self.setAccessibleName("Story list")
        self._own_icons = icons is None
        self._icons = ActionIcons() if icons is None else icons
        self._filtering = False
        self._selected_key: str | None = None
        self._story_items: dict[str, QStandardItem] = {}
        self._errors_item: QStandardItem | None = None
        self._saved_expansion: set[str] | None = None
        self._known_paths: set[str] = set()

        self._search = QLineEdit(self)
        self._search.setObjectName("storySearch")
        self._search.setPlaceholderText("Search stories")
        self._search.setAccessibleName("Search stories")
        self._search.setClearButtonEnabled(True)
        search_icon = QAction(self._search)
        self._search.addAction(search_icon, QLineEdit.ActionPosition.LeadingPosition)
        self._icons.bind(search_icon, "magnifying-glass", role=IconRole.MUTED)
        self._search.textChanged.connect(self._on_search_changed)
        self._search.returnPressed.connect(self._open_first_visible)
        self._search.installEventFilter(self)

        self._model = QStandardItemModel(self)
        self._proxy = _StoryFilterModel(self)
        self._proxy.setSourceModel(self._model)

        self._tree = QTreeView(self)
        self._tree.setObjectName("storyTree")
        self._tree.setAccessibleName("Stories")
        self._tree.setModel(self._proxy)
        self._tree.setHeaderHidden(True)
        self._tree.setUniformRowHeights(True)
        self._tree.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._tree.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._tree.setFrameShape(QFrame.Shape.NoFrame)
        self._tree.installEventFilter(self)
        self._tree.activated.connect(self._on_activated)
        self._tree.selectionModel().currentChanged.connect(self._on_current_changed)

        self._empty_label = QLabel("", self)
        self._empty_label.setObjectName("storySearchEmptyState")
        self._empty_label.setWordWrap(True)
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self._empty_label.setForegroundRole(QPalette.ColorRole.PlaceholderText)
        self._empty_label.hide()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(_MARGIN, _MARGIN, _MARGIN, _MARGIN)
        layout.setSpacing(_SPACING)
        layout.addWidget(self._search)
        layout.addWidget(self._tree, stretch=1)
        layout.addWidget(self._empty_label, stretch=1)
        self.setFocusProxy(self._search)

    def set_registry(self, registry: StoryRegistry, *, load_errors: Sequence[LoadError] = ()) -> None:
        """Rebuild the tree and keep the selected story selected if it still exists, without emitting.

        Branches the user collapsed stay collapsed, and branches new to the tree start expanded.

        Args:
            registry: The stories to list.
            load_errors: Story sources that failed to load, listed in a "Load errors (N)" row at the end.
        """
        expanded = self._expanded_paths() if not self._search.text().strip() else self._saved_expansion
        known = set(self._known_paths)
        self._filtering = True
        try:
            self._model.clear()
            self._story_items = {}
            self._errors_item = None
            self._known_paths = set()
            root = self._model.invisibleRootItem()
            for node in _build_nodes(registry):
                self._append(root, node, depth=0)
            if load_errors:
                item = QStandardItem(f"{LOAD_ERRORS_HEADING} ({len(load_errors)})")
                item.setEditable(False)
                item.setData(_LOAD_ERRORS_ENTRY, _ENTRY_KIND_ROLE)
                root.appendRow(item)
                self._errors_item = item
            self._proxy.refilter()
            if self._selected_key is not None and self._item_for_key(self._selected_key) is None:
                self._selected_key = None
            if self._search.text().strip():
                self._saved_expansion = expanded
                self._tree.expandAll()
            elif expanded is None:
                self._tree.expandAll()
            else:
                self._apply_expansion(expanded, known)
            self._restore_current()
        finally:
            self._filtering = False
        self._update_empty_state()

    def select_story(self, story_id: str) -> bool:
        """Select a story's row, clearing the search first if the filter hides it, and emit ``storySelected``.

        Args:
            story_id: The id of the story.

        Returns:
            ``False`` if there is no story with this id in the tree, else ``True``.
        """
        item = self._story_items.get(story_id)
        if item is None:
            return False
        if not self._proxy.mapFromSource(item.index()).isValid():
            self._search.clear()
        self._select_key(story_id)
        self.storySelected.emit(story_id)
        return True

    def select_first(self) -> bool:
        """Select the first row that opens something, and emit for it.

        That is the first story the filter keeps, else the first story of the whole tree (``select_story`` then clears the search),
        else the "Load errors" row.

        Returns:
            ``False`` if the tree has no such row.
        """
        ids = self.visible_story_ids() or self._all_story_ids()
        if ids:
            return self.select_story(ids[0])
        if self._errors_item is not None:
            self.select_load_errors()
            return True
        return False

    def select_load_errors(self) -> bool:
        """Select the "Load errors" row, clearing the search first, and emit ``loadErrorsSelected``.

        Returns:
            ``False`` if there is no such row.
        """
        if self._errors_item is None:
            return False
        if not self._proxy.mapFromSource(self._errors_item.index()).isValid():
            self._search.clear()
        self._select_key(_LOAD_ERRORS_KEY)
        self.loadErrorsSelected.emit()
        return True

    def selected_story_id(self) -> str | None:
        """Return the id of the selected story, which may be hidden by the filter, or ``None`` if a story is not selected."""
        return self._selected_key if self._selected_key in self._story_items else None

    def load_errors_selected(self) -> bool:
        """Return whether the "Load errors" row is the selected one."""
        return self._selected_key == _LOAD_ERRORS_KEY and self._errors_item is not None

    def visible_story_ids(self) -> list[str]:
        """Return the ids of the story rows the filter keeps, in tree order, whether or not their branch is expanded."""
        return [str(story_id) for story_id in (index.data(_STORY_ID_ROLE) for index in self._walk(QModelIndex())) if story_id is not None]

    def story_ids(self) -> list[str]:
        """Return the ids of every story row in tree order, including the ones the filter hides."""
        return list(self._story_items)

    def load_errors_label(self) -> str | None:
        """Return the text of the "Load errors (N)" row, or ``None`` when there is no such row."""
        return self._errors_item.text() if self._errors_item is not None else None

    def focus_chain(self) -> list[QWidget]:
        """Return the widgets Tab visits in the sidebar, in order: the search field, then the tree."""
        return [self._search, self._tree]

    def focus_search(self) -> None:
        """Move focus to the search field and select its text."""
        self._search.setFocus(Qt.FocusReason.ShortcutFocusReason)
        self._search.selectAll()

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        """Handle Down and Escape in the search field, and Escape in the tree."""
        if event.type() != QEvent.Type.KeyPress or not isinstance(event, QKeyEvent):
            return super().eventFilter(watched, event)
        if event.modifiers() & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.AltModifier | Qt.KeyboardModifier.MetaModifier):
            return super().eventFilter(watched, event)
        key = event.key()
        if watched is self._search and key == Qt.Key.Key_Down:
            ids = self.visible_story_ids()
            if ids:
                self.select_story(ids[0])
                self._tree.setFocus(Qt.FocusReason.TabFocusReason)
            return True
        if watched is self._search and key == Qt.Key.Key_Escape:
            if self._search.text():
                self._search.clear()
            else:
                self._tree.setFocus(Qt.FocusReason.TabFocusReason)
            return True
        if watched is self._tree and key == Qt.Key.Key_Escape:
            self._search.clear()
            return True
        return super().eventFilter(watched, event)

    def changeEvent(self, event: QEvent) -> None:
        """Render the search icon again on a palette change, when the sidebar owns its icon registry."""
        super().changeEvent(event)
        if self._own_icons and event.type() in (QEvent.Type.ApplicationPaletteChange, QEvent.Type.PaletteChange):
            self._icons.retint(self.palette())

    def _append(self, parent: QStandardItem, node: _Node, *, depth: int) -> None:
        collapsed = _collapses(node, depth)
        story = collapsed.story if collapsed is not None else node.story
        item = QStandardItem(node.label)
        item.setEditable(False)
        item.setData(node.path, _PATH_ROLE)
        if story is not None:
            item.setData(story.id, _STORY_ID_ROLE)
            item.setData(story.id, Qt.ItemDataRole.ToolTipRole)
            item.setData(story.id, Qt.ItemDataRole.AccessibleDescriptionRole)
            self._story_items[story.id] = item
        parent.appendRow(item)
        if collapsed is not None:
            return
        self._known_paths.add(node.path)
        for child in node.children:
            self._append(item, child, depth=depth + 1)

    def _item_for_key(self, key: str) -> QStandardItem | None:
        return self._errors_item if key == _LOAD_ERRORS_KEY else self._story_items.get(key)

    def _all_story_ids(self, parent: QStandardItem | None = None) -> list[str]:
        """Return the ids of every story row below ``parent`` (the root by default) in tree order, whatever the filter hides."""
        parent = parent if parent is not None else self._model.invisibleRootItem()
        ids: list[str] = []
        for row in range(parent.rowCount()):
            child = parent.child(row)
            story_id = child.data(_STORY_ID_ROLE)
            if isinstance(story_id, str):
                ids.append(story_id)
            ids.extend(self._all_story_ids(child))
        return ids

    def _walk(self, parent: QModelIndex) -> Iterator[QModelIndex]:
        for row in range(self._proxy.rowCount(parent)):
            index = self._proxy.index(row, 0, parent)
            yield index
            yield from self._walk(index)

    def _expanded_paths(self) -> set[str]:
        return {str(index.data(_PATH_ROLE)) for index in self._walk(QModelIndex()) if self._tree.isExpanded(index)}

    def _apply_expansion(self, expanded: set[str], known: set[str]) -> None:
        for index in self._walk(QModelIndex()):
            if not self._proxy.hasChildren(index):
                continue
            path = str(index.data(_PATH_ROLE))
            self._tree.setExpanded(index, path in expanded or path not in known)

    def _select_key(self, key: str) -> None:
        """Make the row for ``key`` the current one without emitting, and show it."""
        self._selected_key = key
        self._filtering = True
        try:
            self._restore_current(reveal=True)
        finally:
            self._filtering = False

    def _restore_current(self, *, reveal: bool = False) -> None:
        """Show the selected row as current, or clear the current row while the filter hides the selected one.

        Args:
            reveal: Whether to expand the row's ancestors and scroll to it. Only an explicit selection does; restoring the current row
                after a filter or registry change leaves the branches as the user left them.
        """
        selection = self._tree.selectionModel()
        item = self._item_for_key(self._selected_key) if self._selected_key is not None else None
        index = self._proxy.mapFromSource(item.index()) if item is not None else QModelIndex()
        if not index.isValid():
            selection.clear()
            return
        if reveal:
            parent = index.parent()
            while parent.isValid():
                self._tree.expand(parent)
                parent = parent.parent()
        selection.setCurrentIndex(index, QItemSelectionModel.SelectionFlag.ClearAndSelect)
        if reveal:
            self._tree.scrollTo(index)

    def _on_search_changed(self, text: str) -> None:
        searching = bool(text.strip())
        was_searching = self._saved_expansion is not None
        self._filtering = True
        try:
            if searching and not was_searching:
                self._saved_expansion = self._expanded_paths()
            self._proxy.set_text(text)
            if searching:
                self._tree.expandAll()
            elif was_searching:
                saved, self._saved_expansion = self._saved_expansion, None
                self._apply_expansion(saved if saved is not None else set(), self._known_paths)
            self._restore_current()
        finally:
            self._filtering = False
        self._update_empty_state()

    def _update_empty_state(self) -> None:
        text = self._search.text().strip()
        empty = bool(text) and not self.visible_story_ids()
        self._empty_label.setText(f"No stories match '{text}'." if empty else "")
        self._empty_label.setVisible(empty)
        self._tree.setVisible(not empty)

    def _open_first_visible(self) -> None:
        ids = self.visible_story_ids()
        if ids:
            self.select_story(ids[0])

    def _on_current_changed(self, current: QModelIndex, _previous: QModelIndex) -> None:
        if self._filtering or not shiboken6.isValid(self) or not current.isValid():
            return
        self._emit_for(current)

    def _on_activated(self, index: QModelIndex) -> None:
        self._emit_for(index)

    def _emit_for(self, index: QModelIndex) -> None:
        story_id = index.data(_STORY_ID_ROLE)
        if isinstance(story_id, str):
            self._selected_key = story_id
            self.storySelected.emit(story_id)
        elif index.data(_ENTRY_KIND_ROLE) == _LOAD_ERRORS_ENTRY:
            self._selected_key = _LOAD_ERRORS_KEY
            self.loadErrorsSelected.emit()


__all__ = ["LOAD_ERRORS_HEADING", "StorySidebar"]
