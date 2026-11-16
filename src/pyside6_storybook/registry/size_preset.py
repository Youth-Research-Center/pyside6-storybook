"""``SizePreset``: a named canvas size in the gallery's Size menu."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SizePreset:
    """A named size for the gallery's canvas, listed in its Size menu after the built-in sizes.

    With a preset selected, the area a story is placed in is exactly ``width`` by ``height`` pixels.

    Attributes:
        name: The name shown in the Size menu; not blank.
        width: The width in pixels; positive.
        height: The height in pixels; positive.

    Raises:
        TypeError: If ``name`` is not a string, or ``width`` or ``height`` is not an ``int`` (a ``bool`` is not accepted).
        ValueError: If ``name`` is blank, or ``width`` or ``height`` is not positive.
    """

    name: str
    width: int
    height: int

    def __post_init__(self) -> None:
        if not isinstance(self.name, str):
            raise TypeError(f"SizePreset name must be a string, not {type(self.name).__name__}")
        if not self.name.strip():
            raise ValueError("SizePreset name must not be blank")
        for label, value in (("width", self.width), ("height", self.height)):
            if isinstance(value, bool) or not isinstance(value, int):
                raise TypeError(f"SizePreset {label} must be an int, not {type(value).__name__}")
            if value <= 0:
                raise ValueError(f"SizePreset {label} must be positive, not {value}")


__all__ = ["SizePreset"]
