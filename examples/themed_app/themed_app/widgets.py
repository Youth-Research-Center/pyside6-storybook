"""The application's custom widgets: a pill button styled by the application style sheet and a gauge painted from design tokens."""

from __future__ import annotations

from collections.abc import Mapping

from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import QColor, QPainter, QPaintEvent, QPalette
from PySide6.QtWidgets import QPushButton, QWidget

_MAXIMUM = 100


class PillButton(QPushButton):
    """A rounded button. Its look comes from the application style sheet, which selects it by the object name ``pillButton``."""

    def __init__(self, text: str, parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self.setObjectName("pillButton")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAccessibleName(text)


class Gauge(QWidget):
    """A horizontal gauge with a percentage. The bar is painted from the tokens ``accent`` (the filled part), ``track`` and ``text``.

    A token that is missing falls back to a palette role, so the gauge also works before any theme provider has given it tokens.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._value = 0
        self._tokens: dict[str, object] = {}
        self.setAccessibleName("Gauge")
        self._update_description()

    @property
    def value(self) -> int:
        """The gauge's value, from 0 to 100."""
        return self._value

    @value.setter
    def value(self, value: int) -> None:
        self._value = max(0, min(_MAXIMUM, value))
        self._update_description()
        self.update()

    def set_tokens(self, tokens: Mapping[str, object]) -> None:
        """Paint from these design tokens, such as ``ctx.tokens``, and repaint."""
        self._tokens = dict(tokens)
        self.update()

    def sizeHint(self) -> QSize:
        """Return a size derived from the font, so the gauge follows the application font."""
        height = self.fontMetrics().height()
        return QSize(12 * height, 2 * height)

    def paintEvent(self, event: QPaintEvent) -> None:
        """Paint the track, the filled part and the percentage."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        label = f"{self._value}%"
        label_width = self.fontMetrics().horizontalAdvance(f"{_MAXIMUM}%")
        bar_height = self.fontMetrics().height() * 0.8
        bar = QRectF(0, (self.height() - bar_height) / 2, max(self.width() - label_width - 8, 1), bar_height)
        radius = bar.height() / 2
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(self._color("track", QPalette.ColorRole.Mid))
        painter.drawRoundedRect(bar, radius, radius)
        if self._value:
            painter.setBrush(self._color("accent", QPalette.ColorRole.Highlight))
            painter.drawRoundedRect(QRectF(bar.x(), bar.y(), max(bar.width() * self._value / _MAXIMUM, bar.height()), bar.height()), radius, radius)
        painter.setPen(self._color("text", QPalette.ColorRole.WindowText))
        painter.drawText(QRectF(bar.right() + 8, 0, label_width, self.height()), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight, label)
        painter.end()

    def _color(self, token: str, role: QPalette.ColorRole) -> QColor:
        value = self._tokens.get(token)
        if isinstance(value, str) and QColor.isValidColorName(value):
            return QColor(value)
        return self.palette().color(QPalette.ColorGroup.Active, role)

    def _update_description(self) -> None:
        self.setAccessibleDescription(f"{self._value} percent")
