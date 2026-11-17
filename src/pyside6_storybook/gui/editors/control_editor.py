"""``ControlEditor``: the base class of the editors the controls panel builds."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QWidget

from pyside6_storybook.gui.chrome import mark_chrome


class ControlEditor(QWidget):
    """A widget that edits the value of one control.

    The editor's parts are its children. A composite editor sets its primary input as the focus proxy, so the form label's buddy
    mnemonic and Tab reach the input.

    Signals:
        valueChanged: Emitted once per user edit that changes the value, with the new value in the control's value type.
    """

    valueChanged = Signal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        """Create the editor and mark it as chrome; ``create_editor`` marks its parts, which a subclass creates after this runs.

        Args:
            parent: The owning widget.
        """
        super().__init__(parent)
        mark_chrome(self)

    def value(self) -> object:
        """Return the current value, in the control's value type."""
        raise NotImplementedError

    def set_accessible_texts(self, label: str, description: str) -> None:
        """Name the editor's inputs for assistive technology.

        The primary input (the focus proxy) gets the label as its name and the description as its description. A composite editor
        overrides this to name its other parts as well.

        Args:
            label: The form label's text.
            description: The control's description, possibly empty.
        """
        primary = self.focusProxy()
        if primary is not None:
            primary.setAccessibleName(label)
            primary.setAccessibleDescription(description)


__all__ = ["ControlEditor"]
