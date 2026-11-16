"""The editor of a ``TextControl``: a line edit, or a plain-text edit when the control is multiline."""

from __future__ import annotations

from PySide6.QtWidgets import QLineEdit, QPlainTextEdit, QVBoxLayout, QWidget

from pyside6_storybook.controls import TextControl
from pyside6_storybook.gui.editors.control_editor import ControlEditor

_MULTILINE_VISIBLE_LINES = 4


class TextEditor(ControlEditor):
    """Edits a string; emits once per keystroke."""

    def __init__(self, control: TextControl, value: str, parent: QWidget | None = None) -> None:
        """Create the editor.

        Args:
            control: The control to edit.
            value: The starting text.
            parent: The owning widget.
        """
        super().__init__(parent)
        self._input: QLineEdit | QPlainTextEdit
        if control.multiline:
            multiline = QPlainTextEdit(value, self)
            multiline.setTabChangesFocus(True)
            multiline.setMinimumHeight(multiline.fontMetrics().lineSpacing() * _MULTILINE_VISIBLE_LINES + 2 * multiline.frameWidth() + 12)
            multiline.textChanged.connect(self._on_text_changed)
            self._input = multiline
        else:
            line_edit = QLineEdit(value, self)
            line_edit.textChanged.connect(self._on_text_changed)
            self._input = line_edit
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._input)
        self.setFocusProxy(self._input)

    def value(self) -> str:
        """Return the current text."""
        return self._input.toPlainText() if isinstance(self._input, QPlainTextEdit) else self._input.text()

    def _on_text_changed(self, *_args: object) -> None:
        self.valueChanged.emit(self.value())


__all__ = ["TextEditor"]
