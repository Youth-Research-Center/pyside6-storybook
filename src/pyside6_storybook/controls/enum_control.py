"""``EnumControl``: an argument that is a member of an enum class."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from pyside6_storybook.controls._options import derive_label, validate_label_and_description


@dataclass(frozen=True, slots=True)
class EnumControl:
    """An argument that is one of the named members of an enum class, which is the class of ``default``.

    Works for Python enums and PySide6's Qt enums. The options are the class's named members in definition order; an alias
    (a second name for the same value) is left out and the first name is kept. For a ``Flag`` the named combinations are options
    too, for example ``Qt.AlignmentFlag.AlignCenter``, but an unnamed combination such as ``AlignLeft | AlignTop`` is not.

    Attributes:
        name: Argument name, the key in ``StoryContext.args``.
        default: Initial value; a member of the enum class that is one of ``options``. It also fixes the enum class.
        label: Text of the form label; ``None`` derives it from ``name``.
        description: Tooltip and accessible description of the editor.

    Raises:
        TypeError: If ``default`` is not an enum member, or ``label`` or ``description`` has the wrong type.
        ValueError: If ``default`` is not one of ``options`` (an unnamed flag combination), or ``label`` is blank.
    """

    name: str
    default: Enum
    label: str | None = field(default=None, kw_only=True)
    description: str = field(default="", kw_only=True)

    def __post_init__(self) -> None:
        validate_label_and_description(self.name, self.label, self.description)
        if not isinstance(self.default, Enum):
            raise TypeError(f"default of control {self.name!r} must be an enum member, not {self.default!r}")
        self.coerce(self.default)

    @property
    def options(self) -> tuple[Enum, ...]:
        """The members the editor offers, in definition order, without aliases."""
        result: list[Enum] = []
        for member in type(self.default).__members__.values():
            if not any(member == option for option in result):
                result.append(member)
        return tuple(result)

    @property
    def display_label(self) -> str:
        """The form label: ``label``, or the label derived from ``name``."""
        return self.label if self.label is not None else derive_label(self.name)

    def coerce(self, value: object) -> Enum:
        """Return ``value`` as this control's value type.

        Args:
            value: A candidate value.

        Returns:
            The option equal to ``value``.

        Raises:
            TypeError: If ``value`` is not an instance of the default's enum class; an ``int`` or ``bool`` is not accepted, even for
                an ``IntEnum`` or ``IntFlag`` class.
            ValueError: If ``value`` is not one of ``options``.
        """
        enum_class = type(self.default)
        if not isinstance(value, enum_class):
            raise TypeError(f"value {value!r} of control {self.name!r} must be a member of {enum_class.__qualname__}")
        for option in self.options:
            if option == value:
                return option
        raise ValueError(f"value {value!r} of control {self.name!r} is not one of its options {self.options!r}")


__all__ = ["EnumControl"]
