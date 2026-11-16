"""Shared helpers for tests that check bundled, palette-tinted icons."""

from PySide6.QtCore import QSize
from PySide6.QtGui import QColor, QIcon, QImage, QPixmap


def strongest_pixel(source: QImage | QPixmap | QIcon, size: int = 32, *, mode: QIcon.Mode = QIcon.Mode.Normal) -> QColor:
    """Return the most opaque pixel of an image, pixmap or icon, which is the icon's tint.

    Args:
        source: What to inspect.
        size: The logical size an icon is rendered at.
        mode: The icon mode an icon is rendered in.

    Returns:
        The pixel with the highest alpha.
    """
    if isinstance(source, QIcon):
        source = source.pixmap(QSize(size, size), mode)
    image = source.toImage() if isinstance(source, QPixmap) else source
    pixels = (image.pixelColor(x, y) for x in range(image.width()) for y in range(image.height()))
    return max(pixels, key=lambda pixel: pixel.alpha())


def assert_tinted(actual: QColor, expected_hex: str, *, tolerance: int = 12) -> None:
    """Assert that ``actual`` is within ``tolerance`` of ``expected_hex`` on every colour channel."""
    wanted = QColor(expected_hex)
    assert abs(actual.red() - wanted.red()) < tolerance, f"{actual.name()} is not {wanted.name()}"
    assert abs(actual.green() - wanted.green()) < tolerance, f"{actual.name()} is not {wanted.name()}"
    assert abs(actual.blue() - wanted.blue()) < tolerance, f"{actual.name()} is not {wanted.name()}"
