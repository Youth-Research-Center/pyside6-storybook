"""``FileControl``: a file path argument."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from pyside6_storybook.controls._options import derive_label, validate_label_and_description


@dataclass(frozen=True, slots=True)
class FileControl:
    """A file path argument. The story receives a ``Path``, or ``None`` while the path is empty.

    The file need not exist. A relative path stays relative to the working directory.

    Attributes:
        name: Argument name, the key in ``StoryContext.args``.
        default: Initial value, a string or a ``Path``; the empty string means no file.
        label: Text of the form label; ``None`` derives it from ``name``.
        description: Tooltip and accessible description of the editor.
        filter: A ``QFileDialog`` name filter for the Browse button, for example ``"Images (*.png *.jpg)"``.

    Raises:
        TypeError: If ``default`` is neither a string nor a ``Path``, ``filter`` is not a string, or ``label`` or ``description`` has
            the wrong type.
        ValueError: If ``label`` is blank.
    """

    name: str
    default: str | Path = ""
    label: str | None = field(default=None, kw_only=True)
    description: str = field(default="", kw_only=True)
    filter: str = field(default="", kw_only=True)

    def __post_init__(self) -> None:
        validate_label_and_description(self.name, self.label, self.description)
        if not isinstance(self.filter, str):
            raise TypeError(f"filter of control {self.name!r} must be a string, not {self.filter!r}")
        if not isinstance(self.default, (str, Path)):
            raise TypeError(f"default of control {self.name!r} must be a string or a Path, not {self.default!r}")
        self.coerce(self.default)

    @property
    def display_label(self) -> str:
        """The form label: ``label``, or the label derived from ``name``."""
        return self.label if self.label is not None else derive_label(self.name)

    def coerce(self, value: object) -> Path | None:
        """Return ``value`` as this control's value type.

        Args:
            value: A candidate value.

        Returns:
            A ``Path``, or ``None`` for ``None`` and the empty string.

        Raises:
            TypeError: If ``value`` is not a string, a ``Path`` or ``None``.
        """
        if value is None:
            return None
        if isinstance(value, str):
            return Path(value) if value else None
        if isinstance(value, Path):
            return value
        raise TypeError(f"value {value!r} of control {self.name!r} must be a string, a Path or None")


__all__ = ["FileControl"]
