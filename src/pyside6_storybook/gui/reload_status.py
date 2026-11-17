"""``ReloadStatus``: the status bar's reload message with an icon."""

from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import QEvent, QSize
from PySide6.QtWidgets import QHBoxLayout, QLabel, QWidget

from pyside6_storybook.gui.chrome import mark_chrome
from pyside6_storybook.gui.icons import DEFAULT_ICON_SIZE, IconRole, palette_icon

STATUS_NAME = "Reload status"

_SPACING = 6
_SUCCESS_ICON = "arrows-clockwise"
_FAILURE_ICON = "warning"


class ReloadStatus(QWidget):
    """An icon and a line saying when the stories were last reloaded, or why the last reload failed.

    It is empty until ``show_success`` or ``show_failure`` is called. The text label's accessible name is "Reload status" and its
    accessible description is the text, so assistive technology reads both.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        """Create an empty status.

        Args:
            parent: The owning widget.
        """
        super().__init__(parent)
        self._icon_name: str | None = None
        self._icon = QLabel(self)
        mark_chrome(self._icon, "sbkReloadStatusIcon")
        self._text = QLabel("", self)
        mark_chrome(self._text, "sbkReloadStatus")
        self._text.setAccessibleName(STATUS_NAME)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(_SPACING, 0, _SPACING, 0)
        layout.setSpacing(_SPACING)
        layout.addWidget(self._icon)
        layout.addWidget(self._text, stretch=1)

    def text(self) -> str:
        """Return the status text, empty before the first reload."""
        return self._text.text()

    def show_success(self, *, when: datetime | None = None) -> None:
        """Show "Reloaded HH:MM:SS".

        Args:
            when: The time to show; now by default.
        """
        self._show(_SUCCESS_ICON, f"Reloaded {_clock(when)}")

    def show_failure(self, reason: str, *, when: datetime | None = None) -> None:
        """Show "Reload failed HH:MM:SS: reason".

        Args:
            reason: Why the reload was rejected.
            when: The time to show; now by default.
        """
        self._show(_FAILURE_ICON, f"Reload failed {_clock(when)}: {reason}")

    def changeEvent(self, event: QEvent) -> None:
        """Render the icon again when the palette changes."""
        super().changeEvent(event)
        if event.type() == QEvent.Type.PaletteChange:
            self._render_icon()

    def _show(self, icon_name: str, text: str) -> None:
        self._icon_name = icon_name
        self._text.setText(text)
        self._text.setAccessibleDescription(text)
        self._render_icon()

    def _render_icon(self) -> None:
        if self._icon_name is None:
            return
        icon = palette_icon(self._icon_name, role=IconRole.TEXT, palette=self.palette(), size=DEFAULT_ICON_SIZE)
        self._icon.setPixmap(icon.pixmap(QSize(DEFAULT_ICON_SIZE, DEFAULT_ICON_SIZE)))


def _clock(when: datetime | None) -> str:
    return (when if when is not None else datetime.now()).strftime("%H:%M:%S")


__all__ = ["STATUS_NAME", "ReloadStatus"]
