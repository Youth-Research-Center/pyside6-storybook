"""Screenshot snapshots: capturing a rendered story, comparing it with a baseline and writing the diff image (internal).

The comparison works on ``QImage`` bytes, so it needs no dependency beyond Qt. Equal images are detected with one byte comparison,
unequal ones are compared row by row as bytes, and only the rows that differ are looked at pixel by pixel.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtWidgets import QApplication, QWidget

SNAPSHOT_FORMAT = QImage.Format.Format_ARGB32
"""The pixel format every compared image is converted to: four bytes per pixel and no padding at the end of a row."""

DIFF_COLOR = 0xFFFF0000
"""The colour of a differing pixel in the diff image."""

FADE_OPACITY = 0.7
"""How strongly the white veil covers the actual image under the red pixels of the diff image."""

BYTES_PER_PIXEL = 4


@dataclass(frozen=True, slots=True)
class SnapshotDiff:
    """The result of comparing an actual image with its baseline.

    Attributes:
        baseline_size: The baseline's width and height.
        actual_size: The actual image's width and height.
        differing_pixels: How many pixels differ by more than ``tolerance`` in some channel; 0 when the sizes differ.
        tolerance: The largest difference of one channel (0 to 255) that still counts as equal.
        max_diff: The largest share of differing pixels (0 to 1) that still passes.
    """

    baseline_size: tuple[int, int]
    actual_size: tuple[int, int]
    differing_pixels: int
    tolerance: int
    max_diff: float

    @property
    def size_matches(self) -> bool:
        """Whether both images have the same width and height."""
        return self.baseline_size == self.actual_size

    @property
    def total_pixels(self) -> int:
        """The number of pixels of the actual image."""
        return self.actual_size[0] * self.actual_size[1]

    @property
    def share(self) -> float:
        """The share of differing pixels, from 0 to 1; 1 when the sizes differ."""
        if not self.size_matches:
            return 1.0
        return self.differing_pixels / self.total_pixels if self.total_pixels else 0.0

    @property
    def matches(self) -> bool:
        """Whether the actual image passes: the same size and a share of differing pixels of at most ``max_diff``."""
        return self.size_matches and self.share <= self.max_diff


def platform_name() -> str:
    """Return the name of the baselines' platform folder, ``sys.platform`` (``linux``, ``win32`` or ``darwin``)."""
    return sys.platform


def snapshot_name(story_id: str, theme: str) -> str:
    """Return the file stem of a story's snapshot in a theme: the id with ``/`` replaced by ``__``, then ``[<theme>]``.

    Args:
        story_id: The story's id.
        theme: The theme's name.

    Returns:
        A name such as ``Inputs__Button__Default[Dark]``. A path separator in the theme's name is replaced like the id's.
    """
    safe_theme = theme.replace("/", "__").replace("\\", "__")
    return f"{story_id.replace('/', '__')}[{safe_theme}]"


def capture(widget: QWidget) -> QImage:
    """Render a shown widget into an image of its size at device pixel ratio 1.

    The events are processed, then the focus is cleared (a focused line edit blinks its caret, which makes two captures differ; activating a
    window gives focus to a child, so the clearing comes last) and the widget is rendered at once.

    Args:
        widget: The shown widget to render, normally a story's host.

    Returns:
        An ``ARGB32`` image of the widget's size.
    """
    QApplication.processEvents()
    focus = widget.focusWidget()
    if focus is not None:
        focus.clearFocus()
    image = QImage(widget.size(), SNAPSHOT_FORMAT)
    image.setDevicePixelRatio(1.0)
    image.fill(Qt.GlobalColor.transparent)
    widget.render(image)
    return image


def load(path: Path) -> QImage | None:
    """Read a baseline.

    Args:
        path: The PNG file.

    Returns:
        The image converted to ``ARGB32``, or ``None`` if the file cannot be read as an image.
    """
    image = QImage(str(path))
    if image.isNull():
        return None
    return image.convertToFormat(SNAPSHOT_FORMAT)


def save(image: QImage, path: Path) -> bool:
    """Write an image as a PNG file, creating its folder.

    Args:
        image: The image.
        path: The file to write.

    Returns:
        Whether the file was written.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    return image.save(str(path))


def _rows(image: QImage) -> bytes:
    """Return a copy of the image's bytes with exactly ``width * 4`` bytes per row (the copy outlives the converted image)."""
    if image.format() != SNAPSHOT_FORMAT:
        image = image.convertToFormat(SNAPSHOT_FORMAT)
    data = bytes(image.constBits())
    stride = image.bytesPerLine()
    row_bytes = image.width() * BYTES_PER_PIXEL
    if stride == row_bytes:
        return data[: row_bytes * image.height()]
    return b"".join(data[y * stride : y * stride + row_bytes] for y in range(image.height()))


def _differing_columns(baseline_row: bytes, actual_row: bytes, tolerance: int) -> list[int]:
    """Return the x of every pixel of one row where a channel differs by more than ``tolerance``."""
    columns: list[int] = []
    last = -1
    for index, (before, after) in enumerate(zip(baseline_row, actual_row, strict=True)):
        if before == after:
            continue
        x = index // BYTES_PER_PIXEL
        if x == last:
            continue
        if abs(before - after) > tolerance:
            columns.append(x)
            last = x
    return columns


def _differing_pixels(baseline: QImage, actual: QImage, tolerance: int) -> dict[int, list[int]]:
    """Return, by row, the columns that differ; images of one size. Equal rows cost one bytes comparison."""
    before = _rows(baseline)
    after = _rows(actual)
    result: dict[int, list[int]] = {}
    if before == after:
        return result
    row_bytes = actual.width() * BYTES_PER_PIXEL
    for y in range(actual.height()):
        start = y * row_bytes
        old_row = before[start : start + row_bytes]
        new_row = after[start : start + row_bytes]
        if old_row == new_row:
            continue
        columns = _differing_columns(old_row, new_row, tolerance)
        if columns:
            result[y] = columns
    return result


def compare(baseline: QImage, actual: QImage, *, tolerance: int = 0, max_diff: float = 0.0) -> SnapshotDiff:
    """Compare an image with its baseline.

    A pixel differs when any channel differs by more than ``tolerance``. Images of different sizes do not match.

    Args:
        baseline: The stored image.
        actual: The image just captured.
        tolerance: The largest difference of one channel, from 0 to 255, that still counts as equal.
        max_diff: The largest share of differing pixels, from 0 to 1, that still passes.

    Returns:
        The comparison. ``matches`` says whether the image passes.
    """
    sizes = ((baseline.width(), baseline.height()), (actual.width(), actual.height()))
    if sizes[0] != sizes[1]:
        return SnapshotDiff(sizes[0], sizes[1], 0, tolerance, max_diff)
    differing = sum(len(columns) for columns in _differing_pixels(baseline, actual, tolerance).values())
    return SnapshotDiff(sizes[0], sizes[1], differing, tolerance, max_diff)


def diff_image(baseline: QImage, actual: QImage, *, tolerance: int = 0) -> QImage:
    """Draw the differences: the actual image under a white veil, with every differing pixel in red.

    Images of different sizes are drawn on a canvas that holds both, and everything outside their common area is red.

    Args:
        baseline: The stored image.
        actual: The image just captured.
        tolerance: The largest difference of one channel that still counts as equal.

    Returns:
        An ``ARGB32`` image.
    """
    width = max(baseline.width(), actual.width())
    height = max(baseline.height(), actual.height())
    result = QImage(width, height, SNAPSHOT_FORMAT)
    result.fill(Qt.GlobalColor.white)
    painter = QPainter(result)
    painter.drawImage(0, 0, actual)
    painter.setOpacity(FADE_OPACITY)
    painter.fillRect(QRect(0, 0, width, height), QColor(Qt.GlobalColor.white))
    painter.setOpacity(1.0)
    painter.end()
    red = QColor.fromRgba(DIFF_COLOR)
    if (baseline.width(), baseline.height()) == (actual.width(), actual.height()):
        for y, columns in _differing_pixels(baseline, actual, tolerance).items():
            for x in columns:
                result.setPixelColor(x, y, red)
        return result
    common_width = min(baseline.width(), actual.width())
    common_height = min(baseline.height(), actual.height())
    painter = QPainter(result)
    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
    painter.fillRect(QRect(common_width, 0, width - common_width, height), red)
    painter.fillRect(QRect(0, common_height, common_width, height - common_height), red)
    painter.end()
    return result


__all__ = [
    "SnapshotDiff",
    "capture",
    "compare",
    "diff_image",
    "load",
    "platform_name",
    "save",
    "snapshot_name",
]
