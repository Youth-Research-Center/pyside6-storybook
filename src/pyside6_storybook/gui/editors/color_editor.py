"""The editor of a ``ColorControl``: a swatch button that opens a colour dialog, and a hex field."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPalette, QPixmap
from PySide6.QtWidgets import QColorDialog, QHBoxLayout, QLineEdit, QPushButton, QWidget

from pyside6_storybook.controls import ColorControl
from pyside6_storybook.gui.editors.control_editor import ControlEditor


def _ask_color(parent: QWidget, initial: QColor, *, alpha: bool, title: str) -> QColor | None:
    """Open the colour dialog and return the chosen colour, or ``None`` when it is cancelled. Tests replace this function."""
    options = QColorDialog.ColorDialogOption.ShowAlphaChannel if alpha else QColorDialog.ColorDialogOption(0)
    color = QColorDialog.getColor(initial, parent, title, options)
    return color if color.isValid() else None


def format_color(color: QColor, *, alpha: bool) -> str:
    """Return ``color`` as the lowercase hex string the control accepts: ``#rrggbb``, or ``#rrggbbaa`` when ``alpha`` is true."""
    text = f"#{color.red():02x}{color.green():02x}{color.blue():02x}"
    return f"{text}{color.alpha():02x}" if alpha else text


class ColorEditor(ControlEditor):
    """Edits a colour; emits the new ``QColor`` once per edit that changes it, from the dialog or from the hex field."""

    def __init__(self, control: ColorControl, value: QColor, parent: QWidget | None = None) -> None:
        """Create the editor.

        Args:
            control: The control to edit.
            value: The starting colour.
            parent: The owning widget.
        """
        super().__init__(parent)
        self._control = control
        self._color = QColor(value)
        self._title = control.display_label
        self._swatch = QPushButton(self)
        self._swatch.setAutoDefault(False)
        self._swatch.clicked.connect(self._on_swatch_clicked)
        self._hex = QLineEdit(self)
        self._hex.editingFinished.connect(self._on_editing_finished)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._swatch)
        layout.addWidget(self._hex, stretch=1)
        self.setFocusProxy(self._hex)
        self._show_color()

    def value(self) -> QColor:
        """Return a copy of the current colour."""
        return QColor(self._color)

    def set_accessible_texts(self, label: str, description: str) -> None:
        """Name the hex field with the label and the swatch button "Choose colour for <label>"."""
        super().set_accessible_texts(label, description)
        self._title = label
        self._swatch.setAccessibleName(f"Choose colour for {label}")
        self._swatch.setAccessibleDescription(description)

    def _hex_text(self) -> str:
        return format_color(self._color, alpha=self._control.alpha)

    def _show_color(self) -> None:
        text = self._hex_text()
        side = self._swatch.fontMetrics().height()
        pixmap = QPixmap(side, side)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.fillRect(0, 0, side, side, self._color)
        painter.setPen(self.palette().color(QPalette.ColorRole.WindowText))
        painter.drawRect(0, 0, side - 1, side - 1)
        painter.end()
        self._swatch.setIcon(QIcon(pixmap))
        self._swatch.setText(text)
        self._hex.setText(text)

    def _commit(self, color: QColor) -> None:
        changed = color != self._color
        self._color = color
        self._show_color()
        if changed:
            self.valueChanged.emit(QColor(color))

    def _on_swatch_clicked(self) -> None:
        chosen = _ask_color(self, QColor(self._color), alpha=self._control.alpha, title=f"Choose colour for {self._title}")
        if chosen is None:
            return
        try:
            color = self._control.coerce(chosen)
        except ValueError:
            self._show_color()
            return
        self._commit(color)

    def _on_editing_finished(self) -> None:
        try:
            color = self._control.coerce(self._hex.text().strip())
        except ValueError:
            self._show_color()
            return
        self._commit(color)


__all__ = ["ColorEditor"]
