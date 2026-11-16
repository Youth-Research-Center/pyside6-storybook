"""The editor of a ``ChoiceControl``: a combo box."""

from __future__ import annotations

from PySide6.QtWidgets import QComboBox, QHBoxLayout, QWidget

from pyside6_storybook.controls import ChoiceControl
from pyside6_storybook.gui.editors._wheel import guard_wheel
from pyside6_storybook.gui.editors.control_editor import ControlEditor


class ChoiceEditor(ControlEditor):
    """Edits a choice; emits the chosen option when the selection changes."""

    def __init__(self, control: ChoiceControl, value: str, parent: QWidget | None = None) -> None:
        """Create the editor.

        Args:
            control: The control to edit.
            value: The starting option.
            parent: The owning widget.
        """
        super().__init__(parent)
        self._options = tuple(control.options)
        self._combo = QComboBox(self)
        self._combo.addItems(self._options)
        self._combo.setCurrentIndex(self._options.index(value))
        guard_wheel(self._combo)
        self._combo.currentIndexChanged.connect(self._on_index_changed)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._combo)
        self.setFocusProxy(self._combo)

    def value(self) -> str:
        """Return the selected option."""
        return self._options[self._combo.currentIndex()]

    def _on_index_changed(self, index: int) -> None:
        if index >= 0:
            self.valueChanged.emit(self._options[index])


__all__ = ["ChoiceEditor"]
