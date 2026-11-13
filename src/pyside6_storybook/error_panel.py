"""``ErrorPanel``: shows a failure in the preview, a one-line title over selectable details such as a traceback."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import QLabel, QPlainTextEdit, QVBoxLayout, QWidget

_SPACING = 6


class ErrorPanel(QWidget):
    """A bold, selectable title over read-only monospace details. Colours come from the palette, so it follows the theme."""

    def __init__(self, title: str, details: str, parent: QWidget | None = None) -> None:
        """Create the panel.

        Args:
            title: One line saying what failed.
            details: Longer text such as a traceback; the details box is hidden when this is empty.
            parent: The owning widget.
        """
        super().__init__(parent)
        self.setObjectName("previewError")
        self.setAccessibleName(f"Error: {title}")

        self._title = QLabel(title, self)
        self._title.setObjectName("errorTitle")
        self._title.setWordWrap(True)
        self._title.setTextFormat(Qt.TextFormat.PlainText)
        self._title.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse | Qt.TextInteractionFlag.TextSelectableByKeyboard)
        title_font = self._title.font()
        title_font.setBold(True)
        self._title.setFont(title_font)

        self._details = QPlainTextEdit(details, self)
        self._details.setObjectName("errorDetails")
        self._details.setAccessibleName("Error details")
        self._details.setReadOnly(True)
        self._details.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self._details.setFont(QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont))
        self._details.setVisible(bool(details))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(_SPACING)
        layout.addWidget(self._title)
        layout.addWidget(self._details, stretch=1)

    def title(self) -> str:
        """Return the one-line title."""
        return self._title.text()

    def details(self) -> str:
        """Return the details text."""
        return self._details.toPlainText()


__all__ = ["ErrorPanel"]
