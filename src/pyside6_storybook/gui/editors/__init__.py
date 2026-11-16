"""The editors the controls panel builds, one module per control type."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtWidgets import QWidget

from pyside6_storybook.controls import BoolControl, ChoiceControl, Control, FloatControl, IntControl, TextControl
from pyside6_storybook.gui.editors.bool_editor import BoolEditor
from pyside6_storybook.gui.editors.choice_editor import ChoiceEditor
from pyside6_storybook.gui.editors.control_editor import ControlEditor
from pyside6_storybook.gui.editors.float_editor import FloatEditor
from pyside6_storybook.gui.editors.int_editor import IntEditor
from pyside6_storybook.gui.editors.text_editor import TextEditor

EDITORS: dict[type, Callable[..., ControlEditor]] = {
    TextControl: TextEditor,
    BoolControl: BoolEditor,
    ChoiceControl: ChoiceEditor,
    IntControl: IntEditor,
    FloatControl: FloatEditor,
}
"""The editor class of each control type, called as ``editor(control, value, parent)``."""


def create_editor(control: Control, value: object, parent: QWidget | None = None) -> ControlEditor:
    """Create the editor for ``control``.

    Args:
        control: The control to edit.
        value: The starting value, already coerced by ``control``.
        parent: The owning widget.

    Returns:
        The editor.

    The editor is looked up by the control's type and then its base classes, so a subclass of a built-in control gets that
    control's editor unless ``EDITORS`` has its own entry.

    Raises:
        TypeError: If there is no editor for the type of ``control`` or any of its base classes.
    """
    for control_type in type(control).__mro__:
        editor_type = EDITORS.get(control_type)
        if editor_type is not None:
            return editor_type(control, value, parent)
    raise TypeError(f"Unsupported control type: {type(control)!r}")


__all__ = ["EDITORS", "ControlEditor", "create_editor"]
