import dataclasses

import pytest
from PySide6.QtWidgets import QLabel, QPushButton, QWidget

from pyside6_storybook import BoolControl, IntControl, Story, StoryContext, StoryRegistry, TextControl, default_registry, story
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
        widget = QPushButton(ctx.args["text"])
        widget.setEnabled(ctx.args["enabled"])
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
        Story("S", _widget, controls=["text"])  # type: ignore[list-item]


def test_story_context_args_are_read_only_and_copied() -> None:
    source = {"a": 1}
    ctx = StoryContext(args=source)
    source["a"] = 2
    assert ctx.args["a"] == 1
    with pytest.raises(TypeError):
        ctx.args["a"] = 3  # type: ignore[index]
    with pytest.raises(dataclasses.FrozenInstanceError):
        ctx.theme = "Dark"  # type: ignore[misc]


def test_story_context_is_keyword_only_with_a_default_theme() -> None:
    assert StoryContext(args={}).theme == "Light"
    assert StoryContext(args={}, theme="Dark").theme == "Dark"
    with pytest.raises(TypeError):
        StoryContext({})  # type: ignore[misc]


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
