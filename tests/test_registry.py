import dataclasses
import functools
import gc
import importlib
import logging
import subprocess
import sys
import textwrap
import typing
import weakref
from pathlib import Path

import pytest
from PySide6.QtCore import QEvent, QItemSelectionModel, QMetaMethod, QModelIndex, QObject, QStringListModel, Qt, Signal
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QLabel,
    QLineEdit,
    QListWidget,
    QPlainTextEdit,
    QPushButton,
    QSlider,
    QSpinBox,
    QTabWidget,
    QWidget,
)
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
from pyside6_storybook.registry import story_context as story_context_module


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


def _identity(widget: QWidget, ctx: StoryContext) -> QWidget:
    return widget


def _other(widget: QWidget, ctx: StoryContext) -> QWidget:
    return widget


def test_a_story_keeps_its_decorators_as_a_tuple_in_order() -> None:
    registry = StoryRegistry()
    decorators = [_identity, _other]

    declared = registry.story("A/B", decorators=decorators)(_plain)
    undeclared = registry.story("A/C")(_plain)
    decorators.append(_identity)

    assert declared.decorators == (_identity, _other)
    assert undeclared.decorators == ()


def test_the_registry_has_a_plain_list_of_decorators_that_starts_empty() -> None:
    registry = StoryRegistry()

    assert registry.decorators == []
    registry.decorators.append(_identity)
    assert registry.decorators == [_identity]
    assert StoryRegistry().decorators == []


@pytest.mark.parametrize("invalid", [[_identity, "padding"], [None], [42]])
def test_a_decorator_that_is_not_callable_raises_a_type_error_naming_the_story(invalid: list[object]) -> None:
    registry = StoryRegistry()

    with pytest.raises(TypeError, match=r"Story 'A/B'.*is not callable"):
        registry.story("A/B", decorators=invalid)(_plain)  # ty: ignore[invalid-argument-type]
    assert "A/B" not in registry


def test_a_single_decorator_instead_of_a_list_raises_a_type_error_asking_for_a_list() -> None:
    registry = StoryRegistry()

    with pytest.raises(TypeError, match="list of decorators"):
        registry.story("A/B", decorators=_identity)(_plain)  # ty: ignore[invalid-argument-type]


def test_the_module_level_story_decorator_takes_decorators(monkeypatch: pytest.MonkeyPatch) -> None:
    isolated = StoryRegistry()
    monkeypatch.setattr(registry_module, "default_registry", isolated)

    declared = story("A/B", decorators=[_identity])(_plain)

    assert declared.decorators == (_identity,)
    assert isolated.get("A/B") is declared


def test_a_variant_inherits_the_base_decorators_and_a_list_replaces_them() -> None:
    registry = StoryRegistry()
    base = registry.story("A/B/Default", decorators=[_identity])(_plain)

    inherited = base.variant("Same")
    replaced = base.variant("Other", decorators=[_other])
    cleared = base.variant("None", decorators=[])

    assert inherited.decorators == (_identity,)
    assert replaced.decorators == (_other,)
    assert cleared.decorators == ()
    assert base.decorators == (_identity,)
    with pytest.raises(TypeError, match="is not callable"):
        base.variant("Bad", decorators=[3])  # ty: ignore[invalid-argument-type]
    assert "A/B/Bad" not in registry


class _Sink:
    def __init__(self) -> None:
        self.entries: list[tuple[str, tuple[object, ...]]] = []

    def record(self, name: str, args: tuple[object, ...]) -> None:
        self.entries.append((name, args))


def test_log_records_the_name_and_arguments_in_the_sink() -> None:
    sink = _Sink()
    ctx = StoryContext(args={}, actions=sink)

    ctx.log("saved", "a.txt", 3)
    ctx.log("closed")

    assert sink.entries == [("saved", ("a.txt", 3)), ("closed", ())]


def test_log_signal_records_each_emission_under_the_signals_name_or_the_given_name(qtbot) -> None:
    sink = _Sink()
    ctx = StoryContext(args={}, actions=sink)
    box = QSpinBox()
    qtbot.addWidget(box)

    assert ctx.log_signal(box.valueChanged) is None
    ctx.log_signal(box.textChanged, name="text")
    box.setValue(5)

    assert sorted(sink.entries) == [("text", ("5",)), ("valueChanged", (5,))]


def test_log_signal_of_a_button_click_delivers_no_arguments(qtbot) -> None:
    sink = _Sink()
    button = QPushButton()
    qtbot.addWidget(button)
    StoryContext(args={}, actions=sink).log_signal(button.clicked)

    qtbot.mouseClick(button, Qt.MouseButton.LeftButton)

    assert sink.entries == [("clicked", ())]


def test_log_and_log_signal_do_nothing_without_a_sink(qtbot) -> None:
    ctx = StoryContext(args={})
    button = QPushButton()
    qtbot.addWidget(button)

    ctx.log("saved", 1)
    ctx.log_signal(button.clicked)
    ctx.log_signal(button.clicked, name="again")
    qtbot.mouseClick(button, Qt.MouseButton.LeftButton)

    assert ctx.actions is None


def test_log_signal_asks_for_a_name_when_the_signals_repr_has_none() -> None:
    class _Signal:
        def __repr__(self) -> str:
            return "<something else>"

        def connect(self, slot: object) -> None:
            raise AssertionError("must not connect")

    ctx = StoryContext(args={}, actions=_Sink())

    with pytest.raises(TypeError, match=r"name="):
        ctx.log_signal(_Signal())  # ty: ignore[invalid-argument-type]


_STORY_CONTEXT_LOGGER = "pyside6_storybook.registry.story_context"


def _signal_entries(obj: QObject) -> dict[str, list[QMetaMethod]]:
    """Every signal entry of an object by name, including the ones QObject and QWidget declare."""
    meta = obj.metaObject()
    entries: dict[str, list[QMetaMethod]] = {}
    for index in range(meta.methodCount()):
        method = meta.method(index)
        if method.methodType() == QMetaMethod.MethodType.Signal:
            entries.setdefault(bytes(method.name().data()).decode(), []).append(method)
    return entries


def _connected_names(obj: QObject) -> list[str]:
    """The names of the signals that have a receiver, except ``destroyed``, with every entry of a name connected or none of them."""
    names: list[str] = []
    for name, methods in _signal_entries(obj).items():
        if name == "destroyed":
            continue  # PySide6 connects it itself to track the object's lifetime
        connected = [obj.isSignalConnected(method) for method in methods]
        assert all(connected) or not any(connected), name
        if any(connected):
            names.append(name)
    return names


def _logged(obj: QObject, **kwargs: object) -> tuple[_Sink, StoryContext]:
    sink = _Sink()
    ctx = StoryContext(args={}, actions=sink)
    ctx.log_signals(obj, **kwargs)  # ty: ignore[invalid-argument-type]
    return sink, ctx


def test_log_signals_connects_the_signals_of_a_push_button_below_qwidget(qtbot) -> None:
    button = QPushButton()
    qtbot.addWidget(button)

    _logged(button)

    assert _connected_names(button) == ["pressed", "released", "clicked", "toggled"]


def test_log_signals_records_a_click_and_ignores_object_name_changes(qtbot) -> None:
    button = QPushButton()
    qtbot.addWidget(button)
    sink, _ = _logged(button)

    button.setObjectName("renamed")
    button.setWindowTitle("title")
    assert sink.entries == []
    qtbot.mouseClick(button, Qt.MouseButton.LeftButton)

    assert sink.entries == [("pressed", ()), ("released", ()), ("clicked", ())]


class _Emitter(QObject):
    picked = Signal(str, int)


def test_log_signals_logs_a_python_signal_with_both_arguments() -> None:
    emitter = _Emitter()
    sink, _ = _logged(emitter)

    emitter.picked.emit("a", 2)

    assert _connected_names(emitter) == ["picked"]
    assert sink.entries == [("picked", ("a", 2))]


def test_log_signals_on_a_widget_subclass_includes_its_own_signal_and_the_base_signals(qtbot) -> None:
    class Pick(QPushButton):
        picked = Signal(str, int)

    widget = Pick()
    qtbot.addWidget(widget)
    sink, _ = _logged(widget)

    widget.picked.emit("b", 3)

    assert _connected_names(widget) == ["pressed", "released", "clicked", "toggled", "picked"]
    assert sink.entries == [("picked", ("b", 3))]


def test_log_signals_leaves_out_update_request_of_a_text_edit_and_keeps_text_changed(qtbot) -> None:
    edit = QPlainTextEdit()
    qtbot.addWidget(edit)
    sink, _ = _logged(edit)

    names = _connected_names(edit)
    edit.setPlainText("abc")

    assert "updateRequest" not in names
    assert "textChanged" in names
    assert ("textChanged", ()) in sink.entries


def test_log_signals_exclude_removes_the_named_signals(qtbot) -> None:
    button = QPushButton()
    qtbot.addWidget(button)
    sink, _ = _logged(button, exclude=("pressed", "released"))

    qtbot.mouseClick(button, Qt.MouseButton.LeftButton)

    assert sink.entries == [("clicked", ())]


def test_log_signals_warns_about_an_unknown_excluded_name_and_logs_everything_else(qtbot, caplog: pytest.LogCaptureFixture) -> None:
    button = QPushButton()
    qtbot.addWidget(button)
    caplog.set_level(logging.WARNING, logger=_STORY_CONTEXT_LOGGER)

    sink, _ = _logged(button, exclude=("presed",))
    qtbot.mouseClick(button, Qt.MouseButton.LeftButton)

    warnings = [record for record in caplog.records if record.name == _STORY_CONTEXT_LOGGER]
    assert len(warnings) == 1
    message = warnings[0].getMessage()
    assert warnings[0].levelno == logging.WARNING
    assert "presed" in message
    assert "QPushButton" in message
    assert "clicked" in message
    assert sink.entries == [("pressed", ()), ("released", ()), ("clicked", ())]


def test_log_signals_rejects_a_string_for_exclude(qtbot) -> None:
    button = QPushButton()
    qtbot.addWidget(button)
    ctx = StoryContext(args={}, actions=_Sink())

    with pytest.raises(TypeError, match="tuple of names"):
        ctx.log_signals(button, exclude="clicked")

    assert _connected_names(button) == []


def test_log_signals_points_a_signal_to_log_signal_and_rejects_other_objects(qtbot) -> None:
    button = QPushButton()
    qtbot.addWidget(button)
    ctx = StoryContext(args={}, actions=_Sink())

    with pytest.raises(TypeError, match="log_signal"):
        ctx.log_signals(button.clicked)  # ty: ignore[invalid-argument-type]
    with pytest.raises(TypeError, match="QObject"):
        ctx.log_signals("button")  # ty: ignore[invalid-argument-type]

    assert _connected_names(button) == []


def test_log_signals_does_nothing_without_a_sink_and_does_not_warn(qtbot, caplog: pytest.LogCaptureFixture) -> None:
    ctx = StoryContext(args={})
    button = QPushButton()
    qtbot.addWidget(button)
    caplog.set_level(logging.WARNING, logger=_STORY_CONTEXT_LOGGER)

    ctx.log_signals(button, exclude=("presed",))
    ctx.log_signals(object(), exclude="clicked")  # ty: ignore[invalid-argument-type]
    qtbot.mouseClick(button, Qt.MouseButton.LeftButton)

    assert _connected_names(button) == []
    assert caplog.records == []


def test_log_signals_works_on_a_selection_model(qtbot) -> None:
    model = QStringListModel(["a", "b", "c"])
    selection = QItemSelectionModel(model)
    sink, _ = _logged(selection)

    selection.setCurrentIndex(model.index(1), QItemSelectionModel.SelectionFlag.ClearAndSelect)

    names = [name for name, _args in sink.entries]
    assert "selectionChanged" in names
    assert "currentChanged" in names
    current, previous = typing.cast("tuple[QModelIndex, QModelIndex]", dict(sink.entries)["currentChanged"])
    assert (current.row(), previous.row()) == (1, -1)


def test_log_signals_connects_data_changed_of_a_model_without_a_warning(caplog: pytest.LogCaptureFixture) -> None:
    model = QStringListModel(["a", "b"])
    caplog.set_level(logging.WARNING, logger=_STORY_CONTEXT_LOGGER)
    sink, _ = _logged(model)

    model.setData(model.index(1), "z")

    assert caplog.records == []
    assert "dataChanged" in _connected_names(model)
    arguments = next(args for name, args in sink.entries if name == "dataChanged")
    top_left, bottom_right = typing.cast("tuple[QModelIndex, QModelIndex]", arguments[:2])
    assert (top_left.row(), bottom_right.row()) == (1, 1)


def test_log_signals_does_not_connect_a_signal_whose_types_cannot_be_resolved(
    qtbot, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    button = QPushButton()
    qtbot.addWidget(button)
    caplog.set_level(logging.WARNING, logger=_STORY_CONTEXT_LOGGER)
    monkeypatch.setattr(story_context_module, "_resolve_parameter_types", lambda method, modules: bytes(method.name().data()) != b"clicked")

    sink, _ = _logged(button)
    qtbot.mouseClick(button, Qt.MouseButton.LeftButton)

    assert _connected_names(button) == ["pressed", "released", "toggled"]
    assert sink.entries == [("pressed", ()), ("released", ())]
    warnings = [record.getMessage() for record in caplog.records if record.name == _STORY_CONTEXT_LOGGER]
    assert len(warnings) == 1
    assert "clicked" in warnings[0]


_QMOVIE_SCRIPT = """
import sys
from pathlib import Path

from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QApplication

from pyside6_storybook import StoryContext

app = QApplication([])


class Sink:
    def __init__(self):
        self.entries = []

    def record(self, name, args):
        self.entries.append((name, args))


from PySide6.QtGui import QMovie

sink = Sink()
movie = QMovie(sys.argv[1])
StoryContext(args={}, actions=sink).log_signals(movie)
movie.start()
QCoreApplication.processEvents()

from PySide6.QtGui import QImageReader

errors = [args for name, args in sink.entries if name == "error"]
print("errors", len(errors))
print("member", all(isinstance(args[0], QImageReader.ImageReaderError) for args in errors))
"""


@pytest.mark.full
def test_log_signals_converts_an_enum_owned_by_another_class_in_a_fresh_process(tmp_path: Path) -> None:
    script = tmp_path / "movie_script.py"
    script.write_text(textwrap.dedent(_QMOVIE_SCRIPT), encoding="utf-8")
    environment = {**__import__("os").environ, "QT_QPA_PLATFORM": "offscreen"}

    completed = subprocess.run(
        [sys.executable, str(script), str(tmp_path / "missing.gif")],
        capture_output=True,
        text=True,
        timeout=60,
        env=environment,
        check=False,
    )

    assert "cannot be converted" not in completed.stderr
    assert completed.returncode == 0, completed.stderr
    lines = completed.stdout.splitlines()
    assert "errors 1" in lines
    assert "member True" in lines


@pytest.mark.parametrize("factory", [QListWidget, QComboBox], ids=["list widget", "combo box"])
def test_the_sink_is_freed_with_a_widget_whose_signals_are_all_logged(qtbot, qapp: QApplication, factory: type[QWidget]) -> None:
    class Sink:
        def record(self, name: str, args: tuple[object, ...]) -> None:
            pass

    sink = Sink()
    ref = weakref.ref(sink)
    widget = factory()
    StoryContext(args={}, actions=sink).log_signals(widget)
    del sink
    gc.collect()
    assert ref() is not None

    widget.deleteLater()
    del widget
    qapp.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    gc.collect()

    assert ref() is None


def _list_widget() -> QListWidget:
    widget = QListWidget()
    widget.addItems(["a", "b"])
    return widget


def _combo_box() -> QComboBox:
    widget = QComboBox()
    widget.addItems(["a", "b"])
    return widget


def _tab_widget() -> QTabWidget:
    widget = QTabWidget()
    widget.addTab(QWidget(), "one")
    widget.addTab(QWidget(), "two")
    return widget


@pytest.mark.parametrize(
    ("factory", "interact", "expected"),
    [
        (QCheckBox, lambda widget: widget.click(), ("checkStateChanged", (Qt.CheckState.Checked,))),
        (QSlider, lambda widget: widget.setValue(5), ("valueChanged", (5,))),
        (_combo_box, lambda widget: widget.setCurrentIndex(1), ("currentIndexChanged", (1,))),
        (QLineEdit, lambda widget: widget.setText("hi"), ("textChanged", ("hi",))),
        (QSpinBox, lambda widget: widget.setValue(3), ("valueChanged", (3,))),
        (_tab_widget, lambda widget: widget.setCurrentIndex(1), ("currentChanged", (1,))),
        (_list_widget, lambda widget: widget.setCurrentRow(0), ("currentRowChanged", (0,))),
    ],
    ids=["check box", "slider", "combo box", "line edit", "spin box", "tab widget", "list widget"],
)
def test_log_signals_connects_a_stock_widget_without_a_warning_and_records_a_real_argument(
    qtbot, caplog: pytest.LogCaptureFixture, factory, interact, expected: tuple[str, tuple[object, ...]]
) -> None:
    widget = factory()
    qtbot.addWidget(widget)
    caplog.set_level(logging.WARNING)
    sink, _ = _logged(widget)

    interact(widget)

    names = _connected_names(widget)
    declared_below_qwidget = {name for name in _signal_entries(widget) if name not in _signal_entries(QWidget())}
    assert set(names) == declared_below_qwidget - {"updateRequest"}
    assert caplog.records == []
    assert expected in sink.entries


def test_the_actions_field_is_keyword_only_and_not_part_of_equality_or_repr() -> None:
    sink = _Sink()

    assert StoryContext(args={"a": 1}, actions=sink) == StoryContext(args={"a": 1})
    assert "actions" not in repr(StoryContext(args={}, actions=sink))
    assert [field.name for field in dataclasses.fields(StoryContext)] == ["args", "theme", "actions", "tokens", "color_scheme"]
    assert dataclasses.fields(StoryContext)[2].kw_only
