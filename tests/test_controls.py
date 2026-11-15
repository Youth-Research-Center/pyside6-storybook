import dataclasses
import enum
from collections.abc import Callable
from functools import partial
from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor

from pyside6_storybook import BoolControl, ChoiceControl, ColorControl, Control, EnumControl, FileControl, FloatControl, IntControl, TextControl
from pyside6_storybook.controls._options import derive_label


@pytest.mark.parametrize(
    "control",
    [TextControl("a", "x"), BoolControl("a", default=True), ChoiceControl("a", "x", ("x",)), IntControl("a", 1, 0, 2), FloatControl("a", 1.0, 0.0, 2.0)],
)
def test_controls_are_frozen_and_slotted(control: object) -> None:
    assert not hasattr(control, "__dict__")
    with pytest.raises(dataclasses.FrozenInstanceError):
        control.name = "b"  # ty: ignore[invalid-assignment]


def test_choice_control_stores_any_sequence_as_a_tuple() -> None:
    from_list = ChoiceControl("role", "a", ["a", "b"])
    from_generator = ChoiceControl("role", "a", (option for option in "ab"))  # ty: ignore[invalid-argument-type]
    assert from_list.options == ("a", "b")
    assert from_generator.options == ("a", "b")
    assert hash(from_list) == hash(ChoiceControl("role", "a", ("a", "b")))


def test_choice_control_rejects_a_default_that_is_not_an_option() -> None:
    with pytest.raises(ValueError, match="not one of its options"):
        ChoiceControl("role", "c", ("a", "b"))


def test_choice_control_rejects_a_bare_string_as_options() -> None:
    with pytest.raises(TypeError, match="sequence of strings"):
        ChoiceControl("role", "a", "abc")


@pytest.mark.parametrize("control_type", [IntControl, FloatControl])
def test_range_controls_accept_the_range_bounds(control_type: type) -> None:
    assert control_type("n", 0, 0, 10).default == 0
    assert control_type("n", 10, 0, 10).default == 10


@pytest.mark.parametrize("control_type", [IntControl, FloatControl])
@pytest.mark.parametrize("default", [-1, 11])
def test_range_controls_reject_a_default_outside_the_range(control_type: type, default: int) -> None:
    with pytest.raises(ValueError, match="outside"):
        control_type("n", default, 0, 10)


@pytest.mark.parametrize("control_type", [IntControl, FloatControl])
def test_range_controls_reject_a_minimum_above_the_maximum(control_type: type) -> None:
    with pytest.raises(ValueError, match="greater than its maximum"):
        control_type("n", 5, 10, 0)


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
def test_float_control_rejects_non_finite_values(bad: float) -> None:
    with pytest.raises(ValueError, match="finite"):
        FloatControl("n", bad, 0.0, 1.0)
    with pytest.raises(ValueError, match="finite"):
        FloatControl("n", 0.5, 0.0, bad)


def test_int_control_accepts_the_qspinbox_limits() -> None:
    control = IntControl("n", 0, -(2**31), 2**31 - 1)
    assert (control.minimum, control.maximum) == (-(2**31), 2**31 - 1)


@pytest.mark.parametrize(("minimum", "maximum"), [(0, 2**31), (-(2**31) - 1, 0)])
def test_int_control_rejects_bounds_outside_the_qspinbox_range(minimum: int, maximum: int) -> None:
    with pytest.raises(ValueError, match="32-bit"):
        IntControl("n", 0, minimum, maximum)


_ALL_CONTROLS = [
    TextControl("a", "x"),
    BoolControl("a", default=True),
    ChoiceControl("a", "x", ("x", "y")),
    IntControl("a", 1, 0, 2),
    FloatControl("a", 1.0, 0.0, 2.0),
]


@pytest.mark.parametrize("control", _ALL_CONTROLS)
def test_label_and_description_default_to_derived_and_empty(control: Control) -> None:
    assert control.label is None
    assert control.description == ""
    assert control.display_label == "A"


@pytest.mark.parametrize(
    "control",
    [
        TextControl("tile_type", "x", label="Kind", description="d"),
        BoolControl("tile_type", default=True, label="Kind", description="d"),
        ChoiceControl("tile_type", "x", ("x",), label="Kind", description="d"),
        IntControl("tile_type", 1, 0, 2, label="Kind", description="d"),
        FloatControl("tile_type", 1.0, 0.0, 2.0, label="Kind", description="d"),
    ],
)
def test_an_explicit_label_replaces_the_derived_one(control: Control) -> None:
    assert (control.label, control.display_label, control.description) == ("Kind", "Kind", "d")


def test_the_label_is_derived_from_the_name() -> None:
    assert TextControl("tile_type", "x").display_label == "Tile Type"
    assert IntControl("max_count", 1, 0, 5).display_label == "Max Count"
    assert derive_label("a_b_c") == "A B C"


@pytest.mark.parametrize("control_type", [TextControl, BoolControl])
def test_label_and_description_are_validated(control_type: type) -> None:
    default = "x" if control_type is TextControl else True
    with pytest.raises(ValueError, match="blank"):
        control_type("a", default, label="  ")
    with pytest.raises(TypeError, match="label"):
        control_type("a", default, label=3)
    with pytest.raises(TypeError, match="description"):
        control_type("a", default, description=None)


@pytest.mark.parametrize("control", _ALL_CONTROLS)
def test_the_new_fields_are_keyword_only(control: Control) -> None:
    fields = {f.name: f for f in dataclasses.fields(control) if f.kw_only}
    assert {"label", "description"} <= set(fields)
    positional = [f.name for f in dataclasses.fields(control) if not f.kw_only]
    assert positional == {
        "TextControl": ["name", "default"],
        "BoolControl": ["name", "default"],
        "ChoiceControl": ["name", "default", "options"],
        "IntControl": ["name", "default", "minimum", "maximum"],
        "FloatControl": ["name", "default", "minimum", "maximum"],
    }[type(control).__name__]


@pytest.mark.parametrize("control", _ALL_CONTROLS)
def test_a_default_of_the_wrong_type_is_rejected(control: Control) -> None:
    wrong = {"TextControl": 3, "BoolControl": 1, "ChoiceControl": 3, "IntControl": "1", "FloatControl": "1.0"}[type(control).__name__]
    with pytest.raises(TypeError, match="'a'"):
        dataclasses.replace(control, default=wrong)


def test_text_control_coerce_accepts_only_strings() -> None:
    control = TextControl("text", "x")
    assert control.coerce("") == ""
    assert control.coerce("a\nb") == "a\nb"
    for bad in (1, None, b"x", ["x"]):
        with pytest.raises(TypeError, match="'text'"):
            control.coerce(bad)


def test_text_control_multiline_must_be_a_bool() -> None:
    assert TextControl("a", "x", multiline=True).multiline is True
    with pytest.raises(TypeError, match="multiline"):
        TextControl("a", "x", multiline=1)  # ty: ignore[invalid-argument-type]


def test_bool_control_coerce_accepts_only_bools() -> None:
    control = BoolControl("flag", default=False)
    for accepted in (True, False):
        assert control.coerce(accepted) is accepted
    for bad in (0, 1, "True", None):
        with pytest.raises(TypeError, match="'flag'"):
            control.coerce(bad)


def test_choice_control_coerce_accepts_only_its_options() -> None:
    control = ChoiceControl("role", "a", ("a", "b"))
    assert control.coerce("b") == "b"
    with pytest.raises(ValueError, match="'role'.*not one of its options"):
        control.coerce("c")
    for bad in (1, None, ("a",)):
        with pytest.raises(TypeError, match="'role'"):
            control.coerce(bad)


def test_int_control_coerce_accepts_ints_in_range_but_not_bools() -> None:
    control = IntControl("n", 5, 0, 10)
    assert (control.coerce(0), control.coerce(10)) == (0, 10)
    for bad in (-1, 11):
        with pytest.raises(ValueError, match="'n'.*outside 0..10"):
            control.coerce(bad)
    for bad in (True, False, 1.0, "1", None):
        with pytest.raises(TypeError, match="'n'"):
            control.coerce(bad)


def test_int_control_rejects_a_bool_default_and_non_integer_bounds() -> None:
    with pytest.raises(TypeError):
        IntControl("n", default=True, minimum=0, maximum=10)
    with pytest.raises(TypeError, match="minimum"):
        IntControl("n", 1, 0.5, 10)  # ty: ignore[invalid-argument-type]


def test_int_control_step_and_slider_are_validated() -> None:
    control = IntControl("n", 0, 0, 100, step=5, slider=True)
    assert (control.step, control.slider) == (5, True)
    assert (IntControl("n", 0, 0, 1).step, IntControl("n", 0, 0, 1).slider) == (1, False)
    for bad in (0, -1):
        with pytest.raises(ValueError, match="step"):
            IntControl("n", 0, 0, 10, step=bad)
    for bad in (1.5, True):
        with pytest.raises(TypeError, match="step"):
            IntControl("n", 0, 0, 10, step=bad)  # ty: ignore[invalid-argument-type]
    with pytest.raises(TypeError, match="slider"):
        IntControl("n", 0, 0, 10, slider=1)  # ty: ignore[invalid-argument-type]


def test_float_control_coerce_accepts_ints_and_floats_in_range() -> None:
    control = FloatControl("x", 0.5, 0.0, 1.0)
    assert control.coerce(0.25) == 0.25
    result = control.coerce(1)
    assert result == 1.0
    assert isinstance(result, float)
    assert control.coerce(0) == 0.0


@pytest.mark.parametrize("bad", [True, False, "0.5", None])
def test_float_control_coerce_rejects_non_numbers(bad: object) -> None:
    with pytest.raises(TypeError, match="'x'"):
        FloatControl("x", 0.5, 0.0, 1.0).coerce(bad)


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), -1.0, 1.5])
def test_float_control_coerce_rejects_non_finite_and_out_of_range_values(bad: float) -> None:
    with pytest.raises(ValueError, match="'x'"):
        FloatControl("x", 0.5, 0.0, 1.0).coerce(bad)


def test_float_control_coerce_rejects_values_finer_than_the_editor_shows() -> None:
    control = FloatControl("x", 0.5, 0.0, 1.0)
    assert control.effective_decimals == 2
    assert control.coerce(0.12) == 0.12
    for bad in (0.123, 1e-12):
        with pytest.raises(ValueError, match="decimals="):
            control.coerce(bad)
    assert FloatControl("x", 0.5, 0.0, 1.0, decimals=3).coerce(0.123) == 0.123


@pytest.mark.parametrize(
    ("default", "minimum", "maximum", "step", "decimals"),
    [
        (0.5, 0.0, 1.0, 0.01, 2),
        (0.0, 0.0, 100.0, 1.0, 2),
        (0.0, 0.0, 0.01, 0.0001, 4),
        (5.0, 5.0, 5.0, 1.0, 2),
        (0.1234, 0.001, 1.001, 0.01, 4),
        (1e-6, 0.0, 0.001, 0.00001, 6),
    ],
)
def test_float_step_and_decimals_are_derived_from_the_range(default: float, minimum: float, maximum: float, step: float, decimals: int) -> None:
    control = FloatControl("x", default, minimum, maximum)
    assert control.effective_step == pytest.approx(step)
    assert control.effective_decimals == decimals


def test_float_decimals_cover_an_explicit_step() -> None:
    control = FloatControl("x", 0.0, 0.0, 1.0, step=0.125)
    assert (control.effective_step, control.effective_decimals) == (0.125, 3)


def test_float_control_rejects_a_default_or_bound_that_needs_more_than_ten_decimals() -> None:
    with pytest.raises(ValueError, match="default"):
        FloatControl("x", 1e-12, 0.0, 1.0)
    with pytest.raises(ValueError, match="maximum"):
        FloatControl("x", 0.5, 0.0, 1.000000000001)


def test_explicit_decimals_are_validated() -> None:
    assert FloatControl("x", 1.0, 0.0, 1.0, decimals=0, step=1.0).effective_decimals == 0
    assert FloatControl("x", 0.5, 0.0, 1.0, decimals=10).effective_decimals == 10
    for bad in (-1, 11):
        with pytest.raises(ValueError, match="between 0 and 10"):
            FloatControl("x", 0.5, 0.0, 1.0, decimals=bad)
    with pytest.raises(TypeError, match="decimals"):
        FloatControl("x", 0.5, 0.0, 1.0, decimals=2.0)  # ty: ignore[invalid-argument-type]


@pytest.mark.parametrize(
    ("kwargs", "match"),
    [
        ({"default": 0.5, "decimals": 0, "step": 1.0}, "default"),
        ({"default": 0.0, "decimals": 1, "step": 0.25}, "step"),
        ({"default": 0.0, "decimals": 1, "step": 0.5, "maximum": 1.25}, "maximum"),
        ({"default": 0.0, "decimals": 1, "step": 0.5, "minimum": -0.25}, "minimum"),
    ],
)
def test_explicit_decimals_too_small_for_the_step_default_or_a_bound_are_rejected(kwargs: dict, match: str) -> None:
    arguments = {"minimum": 0.0, "maximum": 1.0} | kwargs
    with pytest.raises(ValueError, match=f"{match}.*decimals="):
        FloatControl("x", **arguments)  # ty: ignore[invalid-argument-type]


def test_explicit_step_is_validated() -> None:
    assert FloatControl("x", 0.0, 0.0, 1.0, step=1.0).effective_step == 1.0
    for bad in (0.0, -0.1, 1.5):
        with pytest.raises(ValueError, match="step"):
            FloatControl("x", 0.0, 0.0, 1.0, step=bad)
    with pytest.raises(TypeError, match="step"):
        FloatControl("x", 0.0, 0.0, 1.0, step=True)


def test_an_explicit_step_on_a_zero_width_range_is_rejected() -> None:
    assert FloatControl("x", 5.0, 5.0, 5.0).effective_step == 1.0
    with pytest.raises(ValueError, match="zero-width"):
        FloatControl("x", 5.0, 5.0, 5.0, step=1.0)


@pytest.mark.parametrize(
    ("maximum", "step", "steps"),
    [(0.07, 0.01, 7), (2.1, 0.7, 3), (1.0, 0.3, 4), (1.0, 1.0, 1), (1.0, 0.01, 100)],
)
def test_float_slider_steps_absorb_floating_point_error(maximum: float, step: float, steps: int) -> None:
    control = FloatControl("x", 0.0, 0.0, maximum, step=step, slider=True)
    assert control.slider_steps == steps


def test_float_slider_steps_for_a_zero_width_range_is_zero() -> None:
    assert FloatControl("x", 5.0, 5.0, 5.0, slider=True).slider_steps == 0


def test_float_slider_is_limited_to_ten_thousand_steps() -> None:
    assert FloatControl("x", 0.0, 0.0, 100.0, step=0.01, slider=True).slider_steps == 10_000
    with pytest.raises(ValueError, match="larger step"):
        FloatControl("x", 0.0, 0.0, 100.0, step=0.001, slider=True)
    assert FloatControl("x", 0.0, 0.0, 100.0, step=0.001).slider_steps == 100_000


def test_float_control_rejects_non_numbers_and_a_non_bool_slider() -> None:
    with pytest.raises(TypeError, match="default"):
        FloatControl("x", "1", 0.0, 2.0)  # ty: ignore[invalid-argument-type]
    with pytest.raises(TypeError, match="maximum"):
        FloatControl("x", 1.0, 0.0, None)  # ty: ignore[invalid-argument-type]
    with pytest.raises(TypeError, match="slider"):
        FloatControl("x", 1.0, 0.0, 2.0, slider=1)  # ty: ignore[invalid-argument-type]


def test_controls_are_hashable_and_comparable_with_the_new_fields() -> None:
    first = IntControl("n", 1, 0, 2, label="N", slider=True)
    assert first == IntControl("n", 1, 0, 2, label="N", slider=True)
    assert first != IntControl("n", 1, 0, 2, label="N")
    assert hash(first) == hash(IntControl("n", 1, 0, 2, label="N", slider=True))


class _Mode(enum.Enum):
    FIRST = 1
    SECOND = 2
    ALIAS_OF_SECOND = 2  # noqa: PIE796 (an alias on purpose)
    THIRD = 3


class _Other(enum.Enum):
    FIRST = 1


@pytest.mark.parametrize("control", [ColorControl("a", "#336699"), EnumControl("a", _Mode.FIRST), FileControl("a")])
def test_new_controls_are_frozen_slotted_and_have_a_display_label(control: Control) -> None:
    assert not hasattr(control, "__dict__")
    with pytest.raises(dataclasses.FrozenInstanceError):
        control.name = "b"  # ty: ignore[invalid-assignment]
    assert control.display_label == "A"
    assert dataclasses.replace(control, label="Shown", description="Help").display_label == "Shown"


@pytest.mark.parametrize("make", [partial(ColorControl, "a", "#336699"), partial(EnumControl, "a", _Mode.FIRST), partial(FileControl, "a")])
def test_new_controls_validate_label_and_description(make: Callable[..., Control]) -> None:
    with pytest.raises(ValueError, match="blank"):
        make(label=" ")
    with pytest.raises(TypeError, match="description"):
        make(description=1)


@pytest.mark.parametrize("text", ["#336699", "#ABCDEF", "#abcdef", "#AbCdEf", "#000000"])
def test_color_control_accepts_six_digit_hex_in_any_case(text: str) -> None:
    color = ColorControl("c", "#000000").coerce(text)
    assert color == QColor(text)
    assert color.alpha() == 255


@pytest.mark.parametrize("text", ["", "red", "#abc", "336699", "#33669", "#3366990", "#gggggg", " #336699", "#336699 "])
def test_color_control_rejects_everything_but_six_digit_hex(text: str) -> None:
    with pytest.raises(ValueError, match="hex colour"):
        ColorControl("c", "#000000", alpha=False).coerce(text)


def test_color_control_rejects_eight_digits_without_alpha() -> None:
    with pytest.raises(ValueError, match="alpha=True"):
        ColorControl("c", "#000000").coerce("#11223344")


def test_color_control_eight_digits_need_alpha_and_use_css_byte_order() -> None:
    with pytest.raises(ValueError, match="alpha=True"):
        ColorControl("c", "#000000").coerce("#11223344")
    control = ColorControl("c", "#00000000", alpha=True)
    color = control.coerce("#11223344")
    assert (color.red(), color.green(), color.blue(), color.alpha()) == (0x11, 0x22, 0x33, 0x44)
    assert control.coerce("#112233").alpha() == 255
    for text in ("#abc", "#1122334", "#112233445"):
        with pytest.raises(ValueError, match="#RRGGBBAA"):
            control.coerce(text)


def test_color_control_accepts_a_qcolor_and_rejects_invalid_or_translucent_ones() -> None:
    control = ColorControl("c", "#336699")
    assert control.coerce(QColor(1, 2, 3)) == QColor(1, 2, 3)
    with pytest.raises(ValueError, match="invalid"):
        control.coerce(QColor())
    with pytest.raises(ValueError, match="alpha=True"):
        control.coerce(QColor(1, 2, 3, 100))
    assert ColorControl("c", "#336699", alpha=True).coerce(QColor(1, 2, 3, 100)).alpha() == 100


def test_color_control_returns_a_new_qcolor_every_time() -> None:
    control = ColorControl("c", "#336699")
    given = QColor(1, 2, 3)
    from_string = control.coerce("#336699")
    from_color = control.coerce(given)
    assert control.coerce("#336699") is not from_string
    assert from_color is not given
    from_color.setRed(200)
    assert given.red() == 1
    assert control.coerce(given).red() == 1


def test_color_control_rejects_a_default_that_is_not_a_hex_string_and_other_types() -> None:
    with pytest.raises(TypeError, match="hex colour string"):
        ColorControl("c", QColor("#336699"))  # ty: ignore[invalid-argument-type]
    with pytest.raises(ValueError, match="hex colour"):
        ColorControl("c", "blue")
    with pytest.raises(ValueError, match="alpha=True"):
        ColorControl("c", "#33669980")
    with pytest.raises(TypeError, match="alpha"):
        ColorControl("c", "#336699", alpha=1)  # ty: ignore[invalid-argument-type]
    with pytest.raises(TypeError, match="hex colour string or a QColor"):
        ColorControl("c", "#336699").coerce(0x336699)


def test_enum_control_options_follow_definition_order_without_aliases() -> None:
    control = EnumControl("mode", _Mode.THIRD)
    assert control.options == (_Mode.FIRST, _Mode.SECOND, _Mode.THIRD)
    assert isinstance(control.options, tuple)


def test_enum_control_coerce_returns_the_option_and_rejects_other_types() -> None:
    control = EnumControl("mode", _Mode.FIRST)
    assert control.coerce(_Mode.ALIAS_OF_SECOND) is _Mode.SECOND
    for bad in (1, True, "FIRST", None):
        with pytest.raises(TypeError, match="member of _Mode"):
            control.coerce(bad)
    with pytest.raises(TypeError, match="member of _Mode"):
        control.coerce(_Other.FIRST)


def test_enum_control_works_with_qt_flags_and_their_named_combinations() -> None:
    control = EnumControl("alignment", Qt.AlignmentFlag.AlignCenter)
    assert Qt.AlignmentFlag.AlignCenter in control.options
    assert Qt.AlignmentFlag.AlignLeft in control.options
    assert control.coerce(Qt.AlignmentFlag.AlignCenter) == Qt.AlignmentFlag.AlignCenter
    assert control.coerce(Qt.AlignmentFlag.AlignLeft) == Qt.AlignmentFlag.AlignLeft


def test_enum_control_rejects_unnamed_flag_combinations_ints_and_bools() -> None:
    control = EnumControl("alignment", Qt.AlignmentFlag.AlignLeft)
    combination = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop
    assert combination not in control.options
    with pytest.raises(ValueError, match="not one of its options"):
        control.coerce(combination)
    with pytest.raises(ValueError, match="not one of its options"):
        EnumControl("alignment", combination)
    for bad in (1, True):
        with pytest.raises(TypeError, match="member of Qt.AlignmentFlag"):
            control.coerce(bad)


def test_enum_control_works_with_a_qt_plain_enum_and_rejects_a_non_enum_default() -> None:
    control = EnumControl("orientation", Qt.Orientation.Vertical)
    assert control.options == (Qt.Orientation.Horizontal, Qt.Orientation.Vertical)
    assert control.coerce(Qt.Orientation.Horizontal) is Qt.Orientation.Horizontal
    with pytest.raises(TypeError, match="enum member"):
        EnumControl("mode", "FIRST")  # ty: ignore[invalid-argument-type]


@pytest.mark.parametrize(
    ("value", "expected"),
    [("a/b.txt", Path("a/b.txt")), (Path("a/b.txt"), Path("a/b.txt")), ("", None), (None, None), ("/abs/c.png", Path("/abs/c.png"))],
)
def test_file_control_coerces_strings_paths_and_none(value: object, expected: Path | None) -> None:
    result = FileControl("f").coerce(value)
    assert result == expected
    assert result is None or not result.is_absolute() or str(value).startswith("/")


def test_file_control_keeps_a_relative_path_relative_and_does_not_need_the_file() -> None:
    result = FileControl("f").coerce("missing/nowhere.txt")
    assert result is not None
    assert not result.is_absolute()
    assert not result.exists()


def test_file_control_default_is_empty_and_the_filter_is_stored() -> None:
    control = FileControl("f", filter="Images (*.png)")
    assert control.default == ""
    assert control.coerce(control.default) is None
    assert control.filter == "Images (*.png)"
    assert FileControl("f", Path("x.txt")).coerce(Path("x.txt")) == Path("x.txt")


def test_file_control_rejects_other_types() -> None:
    with pytest.raises(TypeError, match="string, a Path or None"):
        FileControl("f").coerce(1)
    with pytest.raises(TypeError, match="default"):
        FileControl("f", 1)  # ty: ignore[invalid-argument-type]
    with pytest.raises(TypeError, match="filter"):
        FileControl("f", filter=1)  # ty: ignore[invalid-argument-type]


def test_new_controls_are_hashable_and_comparable() -> None:
    assert ColorControl("c", "#336699", alpha=True) == ColorControl("c", "#336699", alpha=True)
    assert ColorControl("c", "#336699") != ColorControl("c", "#336699", alpha=True)
    assert hash(EnumControl("e", _Mode.FIRST)) == hash(EnumControl("e", _Mode.FIRST))
    assert FileControl("f", filter="x") != FileControl("f")
    assert hash(FileControl("f")) == hash(FileControl("f"))
