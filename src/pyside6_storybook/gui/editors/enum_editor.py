"""The editor of an ``EnumControl``: a combo box of the option names."""

from __future__ import annotations

from enum import Enum

from PySide6.QtWidgets import QComboBox, QHBoxLayout, QWidget

from pyside6_storybook.controls import EnumControl
from pyside6_storybook.gui.editors._wheel import guard_wheel
from pyside6_storybook.gui.editors.control_editor import ControlEditor


class EnumEditor(ControlEditor):
    """Edits an enum member; emits the chosen member when the selection changes."""

    def __init__(self, control: EnumControl, value: Enum, parent: QWidget | None = None) -> None:
        """Create the editor.

        Args:
            control: The control to edit.
            value: The starting member, one of the control's options.
            parent: The owning widget.
        """
        super().__init__(parent)
        self._options = control.options
        self._combo = QComboBox(self)
        for option in self._options:
            self._combo.addItem(option.name or str(option.value))
        self._combo.setCurrentIndex(self._options.index(value))
        guard_wheel(self._combo)
        self._combo.currentIndexChanged.connect(self._on_index_changed)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._combo)
        self.setFocusProxy(self._combo)

    def value(self) -> Enum:
        """Return the selected member."""
        return self._options[self._combo.currentIndex()]

    def _on_index_changed(self, index: int) -> None:
        if index >= 0:
            self.valueChanged.emit(self._options[index])


__all__ = ["EnumEditor"]
