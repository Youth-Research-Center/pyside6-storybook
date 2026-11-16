"""The editor of a ``BoolControl``: a check box."""

from __future__ import annotations

from PySide6.QtWidgets import QCheckBox, QHBoxLayout, QWidget

from pyside6_storybook.controls import BoolControl
from pyside6_storybook.gui.editors.control_editor import ControlEditor


class BoolEditor(ControlEditor):
    """Edits a bool; emits when the check box is toggled."""

    def __init__(self, control: BoolControl, value: bool, parent: QWidget | None = None) -> None:  # noqa: FBT001 (the editors share one constructor signature)
        """Create the editor.

        Args:
            control: The control to edit.
            value: The starting state.
            parent: The owning widget.
        """
        super().__init__(parent)
        self._check_box = QCheckBox(self)
        self._check_box.setChecked(value)
        self._check_box.toggled.connect(self._on_toggled)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._check_box)
        layout.addStretch(1)
        self.setFocusProxy(self._check_box)

    def value(self) -> bool:
        """Return whether the check box is checked."""
        return self._check_box.isChecked()

    def _on_toggled(self, checked: bool) -> None:  # noqa: FBT001 (connected directly to the check box's toggled signal)
        self.valueChanged.emit(checked)


__all__ = ["BoolEditor"]
