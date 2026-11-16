import dataclasses
import functools
import importlib
import sys

import pytest
from PySide6.QtWidgets import QLabel, QPushButton, QWidget
from story_files import write

from pyside6_storybook import (
    BoolControl,
    FloatControl,
    IntControl,
    Layout,
    Story,
    StoryContext,
    StoryRegistry,
    TextControl,
    default_registry,
    load_stories,
    story,
)
from pyside6_storybook import registry as registry_module
from pyside6_storybook.registry import StoryOrigin


def _widget(ctx: StoryContext) -> QWidget:
    return QLabel("x")


def test_the_documented_example_registers_and_builds(qtbot) -> None:
    stories = StoryRegistry()

    @stories.story(
        "Inputs/Button",
        controls=[TextControl("text", "Click me"), BoolControl("enabled", default=True)],
    )
    def button(ctx: StoryContext) -> QWidget:
        """A push button."""
        widget = QPushButton(str(ctx.args["text"]))
        widget.setEnabled(bool(ctx.args["enabled"]))
        return widget

    assert isinstance(button, Story)
    widget = button(StoryContext(args=button.default_args()))
    qtbot.addWidget(widget)
    assert isinstance(widget, QPushButton)
    assert widget.text() == "Click me"
    assert widget.isEnabled()
    assert stories.get("Inputs/Button") is button


def test_story_records_its_identity_and_origin() -> None:
    stories = StoryRegistry()

    @stories.story("Forms/Inputs/Text field", controls=[IntControl("n", 1, 0, 2)])
    def text_field(ctx: StoryContext) -> QWidget:
        """Doc line.

        More text.
        """
        return _widget(ctx)

    assert text_field.id == "Forms/Inputs/Text field"
    assert text_field.name == "Text field"
    assert text_field.groups == ("Forms", "Inputs")
    assert text_field.controls == (IntControl("n", 1, 0, 2),)
    assert text_field.doc == "Doc line.\n\nMore text."
    assert text_field.module == __name__
    assert text_field.qualname.endswith("test_story_records_its_identity_and_origin.<locals>.text_field")
    assert text_field.origin == StoryOrigin(text_field.module, text_field.qualname)


def test_story_without_groups_or_docstring() -> None:
    story_object = Story("Button", _widget)
    assert story_object.name == "Button"
    assert story_object.groups == ()
    assert story_object.doc == ""
    assert story_object.controls == ()
    assert story_object.default_args() == {}


def test_default_args_returns_a_fresh_dict_of_control_defaults() -> None:
    story_object = Story("S", _widget, controls=[TextControl("text", "hi"), BoolControl("on", default=False)])
    args = story_object.default_args()
    assert args == {"text": "hi", "on": False}
    args["text"] = "changed"
    assert story_object.default_args()["text"] == "hi"


@pytest.mark.parametrize("bad_id", ["", "/", "A/", "/A", "A//B", " ", "A/ /B"])
def test_invalid_story_ids_are_rejected(bad_id: str) -> None:
    with pytest.raises(ValueError, match="Invalid story id"):
        Story(bad_id, _widget)


def test_duplicate_control_names_are_rejected() -> None:
    with pytest.raises(ValueError, match="more than one control named 'text'"):
        Story("S", _widget, controls=[TextControl("text", "a"), BoolControl("text", default=True)])


def test_a_non_control_is_rejected() -> None:
    with pytest.raises(TypeError, match="not a control"):
        Story("S", _widget, controls=["text"])  # ty: ignore[invalid-argument-type]


def test_story_context_args_are_read_only_and_copied() -> None:
    source = {"a": 1}
    ctx = StoryContext(args=source)
    source["a"] = 2
    assert ctx.args["a"] == 1
    with pytest.raises(TypeError):
        ctx.args["a"] = 3  # ty: ignore[invalid-assignment]
    with pytest.raises(dataclasses.FrozenInstanceError):
        ctx.theme = "Dark"  # ty: ignore[invalid-assignment]


def test_story_context_is_keyword_only_with_a_default_theme() -> None:
    assert StoryContext(args={}).theme == "Light"
    assert StoryContext(args={}, theme="Dark").theme == "Dark"
    with pytest.raises(TypeError):
        StoryContext({})  # ty: ignore[missing-argument, too-many-positional-arguments]


def test_registry_keeps_registration_order_and_supports_lookup() -> None:
    stories = StoryRegistry()
    first = stories.register(Story("B/First", _widget))
    second = stories.register(Story("A/Second", _widget))

    assert stories.ids() == ["B/First", "A/Second"]
    assert list(stories) == [first, second]
    assert len(stories) == 2
    assert "B/First" in stories
    assert "Missing" not in stories
    assert stories.get("A/Second") is second
    with pytest.raises(KeyError):
        stories.get("Missing")


def _define(stories: StoryRegistry, story_id: str, qualname_suffix: str) -> Story:
    """Register a story whose function claims a given module and qualified name, as a reload would produce."""

    def function(ctx: StoryContext) -> QWidget:
        return _widget(ctx)

    function.__qualname__ = f"stories.{qualname_suffix}"
    function.__module__ = "my_app.stories"
    return stories.register(Story(story_id, function))


def test_re_registering_from_the_same_origin_replaces_in_place() -> None:
    stories = StoryRegistry()
    _define(stories, "First", "first")
    original = _define(stories, "Second", "second")
    _define(stories, "Third", "third")

    replacement = _define(stories, "Second", "second")

    assert replacement is not original
    assert stories.get("Second") is replacement
    assert stories.ids() == ["First", "Second", "Third"]
    assert len(stories) == 3


def test_registering_an_id_from_a_different_origin_raises_naming_both() -> None:
    stories = StoryRegistry()
    original = _define(stories, "Button", "button")

    with pytest.raises(ValueError, match=r"my_app\.stories\.stories\.button.*my_app\.stories\.stories\.other_button"):
        _define(stories, "Button", "other_button")
    assert stories.get("Button") is original


def test_registries_are_independent() -> None:
    first, second = StoryRegistry(), StoryRegistry()
    first.register(Story("Only", _widget))
    assert "Only" not in second
    assert len(second) == 0


def test_module_level_story_registers_in_the_default_registry(monkeypatch: pytest.MonkeyPatch) -> None:
    isolated = StoryRegistry()
    monkeypatch.setattr(registry_module, "default_registry", isolated)

    registered = story("Tests/default registry story")(_widget)

    assert isolated.get("Tests/default registry story") is registered
    assert "Tests/default registry story" not in default_registry


def test_a_callable_without_a_qualified_name_can_be_a_story() -> None:
    def labelled(ctx: StoryContext, *, text: str) -> QWidget:
        return QLabel(text)

    stories = StoryRegistry()
    partial_story = stories.story("Display/Partial")(functools.partial(labelled, text="hi"))

    assert partial_story.origin == StoryOrigin("functools", "partial")
    widget = partial_story(StoryContext(args={}))
    assert isinstance(widget, QLabel)
    assert widget.text() == "hi"
    widget.deleteLater()


def test_default_args_are_the_coerced_defaults() -> None:
    registry = StoryRegistry()

    @registry.story("Numbers", controls=[FloatControl("ratio", 1, 0, 2), IntControl("count", 3, 0, 9)])
    def numbers(ctx: StoryContext) -> QWidget:
        return QWidget()

    args = numbers.default_args()

    assert args == {"ratio": 1.0, "count": 3}
    assert isinstance(args["ratio"], float)


def _variant_registry() -> tuple[StoryRegistry, Story]:
    registry = StoryRegistry()

    @registry.story(
        "Inputs/Button/Default",
        controls=[TextControl("text", "Click"), BoolControl("enabled", default=True), FloatControl("ratio", 1, 0, 2)],
    )
    def button(ctx: StoryContext) -> QWidget:
        """A button."""
        return QLabel(str(ctx.args["text"]))

    return registry, button


def test_a_variant_has_the_components_id_and_shares_the_base_function_controls_and_origin() -> None:
    registry, button = _variant_registry()

    disabled = button.variant("Disabled", args={"enabled": False})

    assert button.component == "Inputs/Button"
    assert disabled.id == "Inputs/Button/Disabled"
    assert disabled.name == "Disabled"
    assert disabled.component == "Inputs/Button"
    assert disabled.variant_of is button
    assert button.variant_of is None
    assert disabled.controls == button.controls
    assert disabled.doc == "A button."
    assert disabled.origin == button.origin
    assert registry.get("Inputs/Button/Disabled") is disabled
    assert Story("Solo", _widget).component is None


def test_variant_args_are_the_starting_values_and_reach_the_render_function(qtbot) -> None:
    _registry, button = _variant_registry()

    variant = button.variant("Quiet", args={"enabled": False, "ratio": 2})

    assert dict(variant.args) == {"enabled": False, "ratio": 2.0}
    assert variant.default_args() == {"text": "Click", "enabled": False, "ratio": 2.0}
    assert button.default_args() == {"text": "Click", "enabled": True, "ratio": 1.0}
    assert dict(button.args) == {}
    label = variant(StoryContext(args=variant.default_args()))
    assert isinstance(label, QLabel)
    assert label.text() == "Click"
    label.deleteLater()


@pytest.mark.parametrize("attribute", ["component", "args", "variant_of"])
def test_variant_attributes_cannot_be_reassigned(attribute: str) -> None:
    _registry, button = _variant_registry()
    variant = button.variant("Quiet", args={"enabled": False})

    with pytest.raises(AttributeError):
        setattr(variant, attribute, None)
    assert variant.variant_of is button
    assert dict(variant.args) == {"enabled": False}
    assert variant.component == "Inputs/Button"


def test_variant_args_are_read_only_and_default_args_are_fresh_each_call() -> None:
    _registry, button = _variant_registry()
    variant = button.variant("Quiet", args={"enabled": False})

    with pytest.raises(TypeError):
        variant.args["enabled"] = True  # ty: ignore[invalid-assignment]
    with pytest.raises(TypeError):
        button.args["enabled"] = True  # ty: ignore[invalid-assignment]
    first = variant.default_args()
    first["enabled"] = True
    assert variant.default_args()["enabled"] is False


def test_variant_args_are_copied_from_the_callers_mapping() -> None:
    _registry, button = _variant_registry()
    given = {"enabled": False}

    variant = button.variant("Quiet", args=given)
    given["enabled"] = True

    assert variant.default_args()["enabled"] is False


def test_variants_register_after_their_base_in_order() -> None:
    registry, button = _variant_registry()
    button.variant("B")
    button.variant("A")

    assert registry.ids() == ["Inputs/Button/Default", "Inputs/Button/B", "Inputs/Button/A"]


@pytest.mark.parametrize(
    ("args", "message"),
    [
        ({"missing": 1}, r"Inputs/Button/Bad.*'missing' is not a control"),
        ({"enabled": 1}, r"Inputs/Button/Bad.*invalid value for 'enabled'.*'enabled'"),
        ({"ratio": 5}, r"Inputs/Button/Bad.*invalid value for 'ratio'"),
        ({"text": 3}, r"Inputs/Button/Bad.*invalid value for 'text'"),
        ({"ratio": 10**400}, r"Inputs/Button/Bad.*invalid value for 'ratio'.*too large for a float"),
    ],
)
def test_invalid_variant_args_raise_a_value_error_naming_the_variant_and_key(args: dict[str, object], message: str) -> None:
    registry, button = _variant_registry()

    with pytest.raises(ValueError, match=message):
        button.variant("Bad", args=args)
    assert registry.ids() == ["Inputs/Button/Default"]


@pytest.mark.parametrize("name", ["", "  ", "A/B"])
def test_a_blank_variant_name_or_one_with_a_slash_is_rejected(name: str) -> None:
    _registry, button = _variant_registry()
    with pytest.raises(ValueError, match="Invalid variant name"):
        button.variant(name)


def test_a_variant_named_like_its_base_is_rejected() -> None:
    _registry, button = _variant_registry()
    with pytest.raises(ValueError, match="name of its base story"):
        button.variant("Default")


def test_a_base_without_a_component_cannot_have_variants() -> None:
    registry = StoryRegistry()
    solo = registry.register(Story("Button", _widget))
    with pytest.raises(ValueError, match="needs|no component"):
        solo.variant("Disabled")


def test_a_variant_of_a_variant_is_a_type_error_pointing_at_the_base() -> None:
    _registry, button = _variant_registry()
    disabled = button.variant("Disabled")
    with pytest.raises(TypeError, match=r"call \.variant\(\) on the base"):
        disabled.variant("Other")


def test_variant_on_an_unregistered_story_is_a_runtime_error() -> None:
    with pytest.raises(RuntimeError, match="not registered"):
        Story("Inputs/Button/Default", _widget).variant("Disabled")


def test_a_variant_id_colliding_with_another_functions_story_raises() -> None:
    registry, button = _variant_registry()
    other = Story("Inputs/Button/Disabled", _widget)
    registry.register(other)

    with pytest.raises(ValueError, match="already registered"):
        button.variant("Disabled")
    assert registry.get("Inputs/Button/Disabled") is other


def test_defining_the_same_variant_twice_replaces_it() -> None:
    registry, button = _variant_registry()
    first = button.variant("Quiet", args={"enabled": False})
    second = button.variant("Quiet", args={"text": "Again"})

    assert registry.get("Inputs/Button/Quiet") is second
    assert second is not first
    assert registry.ids() == ["Inputs/Button/Default", "Inputs/Button/Quiet"]


def test_variants_are_not_public_constructor_parameters() -> None:
    with pytest.raises(TypeError):
        Story("A/B", _widget, args={})  # ty: ignore[unknown-argument]
    with pytest.raises(TypeError):
        Story("A/B", _widget, variant_of=None)  # ty: ignore[unknown-argument]


def test_reloading_a_story_module_replaces_the_base_and_its_variants_in_place(stories: StoryRegistry, tmp_path) -> None:
    source = """
        from PySide6.QtWidgets import QLabel

        from pyside6_storybook import BoolControl, story


        @story("Inputs/Label/Default", controls=[BoolControl("loud", default=False)])
        def label(ctx):
            return QLabel("x")


        label.variant("Loud", args={"loud": True})
        label.variant("Quiet")


        @story("Inputs/Other/Default")
        def other(ctx):
            return QLabel("y")
    """
    write(tmp_path, "stories/label_stories.py", source)
    first = load_stories(["stories"], cwd=tmp_path)
    assert first.errors == ()
    ids = stories.ids()
    old = stories.get("Inputs/Label/Loud")
    assert ids == ["Inputs/Label/Default", "Inputs/Label/Loud", "Inputs/Label/Quiet", "Inputs/Other/Default"]

    (module_name,) = [name for name in sys.modules if name.endswith("label_stories")]
    importlib.reload(sys.modules[module_name])

    assert stories.ids() == ids
    assert stories.get("Inputs/Label/Loud") is not old
    assert stories.get("Inputs/Label/Loud").variant_of is stories.get("Inputs/Label/Default")


def test_layout_values() -> None:
    assert [(member.name, member.value) for member in Layout] == [("CENTERED", "centered"), ("PADDED", "padded"), ("FILL", "fill")]
    assert Layout("fill") is Layout.FILL
    assert Layout.FILL == "fill"


def _plain(ctx: StoryContext) -> QWidget:
    return QLabel("x")


@pytest.mark.parametrize(
    ("declared", "expected"),
    [(Layout.FILL, Layout.FILL), ("centered", Layout.CENTERED), ("padded", Layout.PADDED), (None, None)],
)
def test_a_story_keeps_the_layout_it_declared(declared: Layout | str | None, expected: Layout | None) -> None:
    registry = StoryRegistry()

    registered = registry.story("A/B", layout=declared)(_plain)

    assert registered.layout is expected
    assert Story("A/C", _plain, layout=declared).layout is expected


@pytest.mark.parametrize("invalid", ["Fill", "stretch", "", 1, True, Layout])
def test_an_invalid_layout_raises_at_registration_and_lists_the_valid_values(invalid: object) -> None:
    registry = StoryRegistry()

    with pytest.raises(ValueError, match=r"'centered', 'padded', 'fill'"):
        registry.story("A/B", layout=invalid)  # ty: ignore[invalid-argument-type]
    with pytest.raises(ValueError, match=r"'centered', 'padded', 'fill'"):
        Story("A/B", _plain, layout=invalid)  # ty: ignore[invalid-argument-type]
    assert len(registry) == 0


def test_the_module_level_story_decorator_takes_a_layout(monkeypatch: pytest.MonkeyPatch) -> None:
    isolated = StoryRegistry()
    monkeypatch.setattr(registry_module, "default_registry", isolated)

    registered = story("A/B", layout="fill")(_plain)

    assert registered.layout is Layout.FILL
    with pytest.raises(ValueError, match="Invalid layout"):
        story("A/C", layout="nope")


def test_the_default_layout_is_padded_and_the_setter_validates() -> None:
    registry = StoryRegistry()
    assert registry.default_layout is Layout.PADDED

    registry.default_layout = Layout.FILL
    assert registry.default_layout is Layout.FILL
    registry.default_layout = "centered"
    assert registry.default_layout is Layout.CENTERED
    with pytest.raises(ValueError, match="stretch"):
        registry.default_layout = "stretch"
    assert registry.default_layout is Layout.CENTERED


def test_a_variant_inherits_the_base_layout_and_can_override_it() -> None:
    registry = StoryRegistry()
    base = registry.story("A/B/Default", layout=Layout.CENTERED)(_plain)
    plain_base = registry.story("A/C/Default")(_plain)

    inherited = base.variant("Same")
    overridden = base.variant("Other", layout="fill")
    undeclared = plain_base.variant("Same")
    declared = plain_base.variant("Padded", layout=Layout.PADDED)

    assert inherited.layout is Layout.CENTERED
    assert overridden.layout is Layout.FILL
    assert base.layout is Layout.CENTERED
    assert undeclared.layout is None
    assert declared.layout is Layout.PADDED
    with pytest.raises(ValueError, match="Invalid layout"):
        base.variant("Bad", layout="nope")
    assert "A/B/Bad" not in registry
