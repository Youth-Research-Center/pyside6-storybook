import dataclasses

import pytest

from pyside6_storybook import BoolControl, ChoiceControl, FloatControl, IntControl, TextControl


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
