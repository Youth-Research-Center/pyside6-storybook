"""The editor of a ``FileControl``: a path field and a Browse button."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QFileDialog, QHBoxLayout, QLineEdit, QPushButton, QWidget

from pyside6_storybook.controls import FileControl
from pyside6_storybook.gui.editors.control_editor import ControlEditor


def _ask_file(parent: QWidget, current: Path | None, *, name_filter: str, title: str) -> Path | None:
    """Open the file dialog and return the chosen path, or ``None`` when it is cancelled. Tests replace this function."""
    start = str(current) if current is not None else ""
    chosen, _selected_filter = QFileDialog.getOpenFileName(parent, title, start, name_filter)
    return Path(chosen) if chosen else None


class FileEditor(ControlEditor):
    """Edits a file path; emits the new ``Path`` (or ``None`` for an empty field) once per edit that changes it."""

    def __init__(self, control: FileControl, value: Path | None, parent: QWidget | None = None) -> None:
        """Create the editor.

        Args:
            control: The control to edit.
            value: The starting path, or ``None`` for none.
            parent: The owning widget.
        """
        super().__init__(parent)
        self._control = control
        self._path = value
        self._title = control.display_label
        self._input = QLineEdit(self._text(), self)
        self._input.editingFinished.connect(self._on_editing_finished)
        self._browse = QPushButton("Browse…", self)
        self._browse.setAutoDefault(False)
        self._browse.clicked.connect(self._on_browse_clicked)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._input, stretch=1)
        layout.addWidget(self._browse)
        self.setFocusProxy(self._input)

    def value(self) -> Path | None:
        """Return the current path, or ``None`` when there is none."""
        return self._path

    def set_accessible_texts(self, label: str, description: str) -> None:
        """Name the path field with the label and the button "Browse for <label>"."""
        super().set_accessible_texts(label, description)
        self._title = label
        self._browse.setAccessibleName(f"Browse for {label}")
        self._browse.setAccessibleDescription(description)

    def _text(self) -> str:
        return str(self._path) if self._path is not None else ""

    def _commit(self, path: Path | None) -> None:
        changed = path != self._path
        self._path = path
        self._input.setText(self._text())
        if changed:
            self.valueChanged.emit(path)

    def _on_browse_clicked(self) -> None:
        chosen = _ask_file(self, self._path, name_filter=self._control.filter, title=f"Choose file for {self._title}")
        if chosen is not None:
            self._commit(self._control.coerce(chosen))

    def _on_editing_finished(self) -> None:
        self._commit(self._control.coerce(self._input.text()))


__all__ = ["FileEditor"]
