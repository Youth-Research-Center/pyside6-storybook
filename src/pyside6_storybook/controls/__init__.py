"""Control definitions: the editable arguments of a story, one module per control type."""

from pyside6_storybook.controls.bool_control import BoolControl
from pyside6_storybook.controls.choice_control import ChoiceControl
from pyside6_storybook.controls.color_control import ColorControl
from pyside6_storybook.controls.enum_control import EnumControl
from pyside6_storybook.controls.file_control import FileControl
from pyside6_storybook.controls.float_control import FloatControl
from pyside6_storybook.controls.int_control import IntControl
from pyside6_storybook.controls.text_control import TextControl

Control = TextControl | BoolControl | ChoiceControl | IntControl | FloatControl | ColorControl | EnumControl | FileControl
"""Any control type."""

__all__ = [
    "BoolControl",
    "ChoiceControl",
    "ColorControl",
    "Control",
    "EnumControl",
    "FileControl",
    "FloatControl",
    "IntControl",
    "TextControl",
]
