"""``Layout``: how the gallery places a story's widget in the preview."""

from __future__ import annotations

from enum import StrEnum


class Layout(StrEnum):
    """How the preview places a story's widget.

    Members:
        CENTERED: The widget keeps its natural size and is centred in the preview, horizontally and vertically.
        PADDED: The widget sits at the top of the preview inside a margin. Its width follows its horizontal size policy, so a
            button stretches to the full width, and its height is its natural height.
        FILL: The widget fills the preview inside the margin, in each direction its size policy lets it grow. In a direction it
            cannot grow, it keeps its natural size and is centred.

    A widget larger than the preview scrolls in ``CENTERED`` and ``PADDED``; ``FILL`` never shows scroll bars.
    """

    CENTERED = "centered"
    PADDED = "padded"
    FILL = "fill"


def coerce_layout(value: object) -> Layout | None:
    """Return ``value`` as a ``Layout``, or ``None`` when it is ``None``.

    Args:
        value: A ``Layout``, one of its string values, or ``None``.

    Returns:
        The layout, or ``None``.

    Raises:
        ValueError: If ``value`` is anything else; the message lists the valid values.
    """
    if value is None:
        return None
    if isinstance(value, Layout):
        return value
    if isinstance(value, str):
        try:
            return Layout(value)
        except ValueError:
            pass
    valid = ", ".join(repr(member.value) for member in Layout)
    raise ValueError(f"Invalid layout {value!r}: expected a Layout, one of {valid}, or None")


__all__ = ["Layout", "coerce_layout"]
