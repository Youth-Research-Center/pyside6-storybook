"""``ActionsPanel``: the Actions tab, a log of the signals and actions a story reports, newest first."""

from __future__ import annotations

import reprlib
from datetime import datetime

from PySide6.QtCore import QEvent, QTimer
from PySide6.QtGui import QAccessible, QAccessibleAnnouncementEvent
from PySide6.QtWidgets import QAbstractItemView, QHBoxLayout, QLabel, QPushButton, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget

from pyside6_storybook.gui.icons import ActionIcons

MAX_ENTRIES = 500
MAX_ARGUMENT_CHARS = 200
ANNOUNCE_INTERVAL_MS = 500
HEADERS = ("Time", "Action", "Arguments")

_SPACING = 6
_ARGUMENT_REPR = reprlib.Repr()
_ARGUMENT_REPR.maxlevel = 3
_ARGUMENT_REPR.maxlist = _ARGUMENT_REPR.maxtuple = _ARGUMENT_REPR.maxdict = _ARGUMENT_REPR.maxset = 8
_ARGUMENT_REPR.maxstring = _ARGUMENT_REPR.maxother = 60


def format_arguments(args: tuple[object, ...]) -> str:
    """Return ``args`` as text for the Arguments column: the values separated by commas, at most 200 characters.

    Args:
        args: The arguments an action carried.

    Returns:
        The text; empty when there are none. A longer text ends with an ellipsis.
    """
    text = ", ".join(_ARGUMENT_REPR.repr(arg) for arg in args)
    if len(text) > MAX_ARGUMENT_CHARS:
        return text[: MAX_ARGUMENT_CHARS - 1] + "…"
    return text


class _GenerationSink:
    """The ``ActionSink`` the window creates for one render; the panel ignores it once a newer render has begun."""

    def __init__(self, panel: ActionsPanel, generation: int) -> None:
        self._panel = panel
        self._generation = generation

    def record(self, name: str, args: tuple[object, ...]) -> None:
        """Record an action unless this sink's render is no longer the current one.

        Args:
            name: The action's name.
            args: The arguments the action carried.
        """
        self._panel.record(name, args, generation=self._generation)


class ActionsPanel(QWidget):
    """A table of logged actions (time, action, arguments), newest first, with a Clear button and a count under it."""

    def __init__(self, parent: QWidget | None = None, *, icons: ActionIcons | None = None) -> None:
        """Create an empty panel.

        Args:
            parent: The owning widget.
            icons: The registry that tints the Clear button's icon. ``None`` gives the panel its own, retinted when its palette changes;
                the gallery window passes its own, which it retints.
        """
        super().__init__(parent)
        self.setObjectName("actionsPanel")
        self._own_icons = icons is None
        self._icons = icons if icons is not None else ActionIcons()
        self._generation = 0

        self._tree = QTreeWidget(self)
        self._tree.setObjectName("actionsTree")
        self._tree.setAccessibleName("Logged actions")
        self._tree.setHeaderLabels(list(HEADERS))
        self._tree.setRootIsDecorated(False)
        self._tree.setUniformRowHeights(True)
        self._tree.setAlternatingRowColors(True)
        self._tree.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._tree.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)

        self._status = QLabel(self)
        self._status.setObjectName("actionsStatus")
        self._status.setAccessibleName("Number of logged actions")

        self._clear_button = QPushButton("Clear", self)
        self._clear_button.setObjectName("actionsClear")
        self._clear_button.setAccessibleName("Clear logged actions")
        self._clear_button.setToolTip("Remove every logged action")
        self._icons.bind(self._clear_button, "trash")
        self._clear_button.clicked.connect(self.clear)

        self._announce_timer = QTimer(self)
        self._announce_timer.setSingleShot(True)
        self._announce_timer.setInterval(ANNOUNCE_INTERVAL_MS)
        self._announce_timer.timeout.connect(self._announce)

        footer = QHBoxLayout()
        footer.setContentsMargins(0, 0, 0, 0)
        footer.setSpacing(_SPACING)
        footer.addWidget(self._status, stretch=1)
        footer.addWidget(self._clear_button)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(_SPACING)
        layout.addWidget(self._tree, stretch=1)
        layout.addLayout(footer)
        self._update_status()

    def new_sink(self) -> _GenerationSink:
        """Start a new generation and return the sink for it; sinks of earlier generations stop recording.

        Returns:
            A sink for the story widget about to be built, to pass as ``StoryContext.actions``.
        """
        self._generation += 1
        return _GenerationSink(self, self._generation)

    def invalidate(self) -> None:
        """Stop every sink handed out so far from recording, for example when the preview they belong to is gone."""
        self._generation += 1

    def record(self, name: str, args: tuple[object, ...], *, generation: int | None = None) -> None:
        """Add an action at the top of the list.

        Args:
            name: The action's name.
            args: The arguments the action carried.
            generation: The generation of the sink that recorded it; the action is ignored when this is not the current one.
                ``None`` always records.
        """
        if generation is not None and generation != self._generation:
            return
        item = QTreeWidgetItem([datetime.now().strftime("%H:%M:%S.%f")[:-3], name, format_arguments(args)])
        self._tree.insertTopLevelItem(0, item)
        while self._tree.topLevelItemCount() > MAX_ENTRIES:
            self._tree.takeTopLevelItem(self._tree.topLevelItemCount() - 1)
        self._update_status()
        if not self._announce_timer.isActive():
            self._announce_timer.start()

    def clear(self) -> None:
        """Remove every logged action."""
        self._tree.clear()
        self._update_status()

    def count(self) -> int:
        """Return the number of logged actions."""
        return self._tree.topLevelItemCount()

    def rows(self) -> list[tuple[str, str, str]]:
        """Return the logged actions newest first, each as ``(time, action, arguments)`` text."""
        items = (self._tree.topLevelItem(index) for index in range(self._tree.topLevelItemCount()))
        return [(item.text(0), item.text(1), item.text(2)) for item in items if item is not None]

    def status_text(self) -> str:
        """Return the text under the list, such as ``"3 actions logged"``."""
        return self._status.text()

    def changeEvent(self, event: QEvent) -> None:
        """Render the Clear button's icon again when the palette changes, if the panel owns its icons."""
        super().changeEvent(event)
        if self._own_icons and event.type() in (QEvent.Type.ApplicationPaletteChange, QEvent.Type.PaletteChange):
            self._icons.retint(self.palette())

    def _update_status(self) -> None:
        count = self.count()
        self._status.setText(f"{count} action logged" if count == 1 else f"{count} actions logged")

    def _announce(self) -> None:
        """Tell assistive technology how many actions are logged; a burst of actions is announced once, with its final count."""
        if self.count() == 0:
            return
        event = QAccessibleAnnouncementEvent(self._status, self._status.text())
        event.setPoliteness(QAccessible.AnnouncementPoliteness.Polite)
        QAccessible.updateAccessibility(event)


__all__ = ["ActionsPanel", "format_arguments"]
