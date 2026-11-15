import pytest
import shiboken6
from PySide6.QtCore import QEvent, QMargins, QRect
from PySide6.QtWidgets import QApplication, QGroupBox, QLabel, QVBoxLayout, QWidget

from pyside6_storybook import Decorator, StoryContext, StoryRegistry
from pyside6_storybook.decorators import fixed_size, padding
from pyside6_storybook.registry.rendering import RenderedStory, StoryRenderError, render_story

_CTX = StoryContext(args={})


def _label(ctx: StoryContext) -> QWidget:
    return QLabel("story")


def _wrapper(name: str, calls: list[str]) -> Decorator:
    """A decorator that records its name and wraps the widget in a ``QWidget`` named ``name``."""

    def decorate(widget: QWidget, ctx: StoryContext) -> QWidget:
        calls.append(name)
        wrapper = QWidget()
        wrapper.setObjectName(name)
        QVBoxLayout(wrapper).addWidget(widget)
        return wrapper

    return decorate


def _margins(widget: QWidget) -> QMargins:
    layout = widget.layout()
    assert layout is not None
    return layout.contentsMargins()


def _alive(*widgets: QWidget) -> list[bool]:
    QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    return [shiboken6.isValid(widget) for widget in widgets]


def _registry_with(story_decorators: list[Decorator], registry_decorators: list[Decorator] | None = None):
    registry = StoryRegistry()
    registry.decorators.extend(registry_decorators or [])
    return registry, registry.story("Group/Story", decorators=story_decorators)(_label)


def test_without_decorators_the_root_is_the_story_widget(qtbot) -> None:
    registry, story = _registry_with([])

    rendered = render_story(story, _CTX, registry=registry)
    qtbot.addWidget(rendered.root)

    assert isinstance(rendered, RenderedStory)
    assert rendered.root is rendered.widget
    assert isinstance(rendered.widget, QLabel)


def test_the_first_decorator_of_a_story_is_the_outermost_and_the_last_is_applied_first(qtbot) -> None:
    calls: list[str] = []
    registry, story = _registry_with([_wrapper("first", calls), _wrapper("second", calls), _wrapper("third", calls)])

    rendered = render_story(story, _CTX, registry=registry)
    qtbot.addWidget(rendered.root)

    assert calls == ["third", "second", "first"]
    assert rendered.root.objectName() == "first"
    second = rendered.widget.parentWidget()
    assert second is not None
    assert second.objectName() == "third"
    third_parent = second.parentWidget()
    assert third_parent is not None
    assert third_parent.objectName() == "second"
    assert third_parent.parentWidget() is rendered.root
    assert rendered.root.parentWidget() is None


def test_registry_decorators_wrap_the_story_decorators_first_outermost(qtbot) -> None:
    calls: list[str] = []
    registry, story = _registry_with(
        [_wrapper("story-outer", calls), _wrapper("story-inner", calls)],
        [_wrapper("registry-outer", calls), _wrapper("registry-inner", calls)],
    )

    rendered = render_story(story, _CTX, registry=registry)
    qtbot.addWidget(rendered.root)

    assert calls == ["story-inner", "story-outer", "registry-inner", "registry-outer"]
    chain = []
    widget: QWidget | None = rendered.widget.parentWidget()
    while widget is not None:
        chain.append(widget.objectName())
        widget = widget.parentWidget()
    assert chain == ["story-inner", "story-outer", "registry-inner", "registry-outer"]
    assert rendered.root.objectName() == "registry-outer"


def test_registry_decorators_are_read_at_render_time(qtbot) -> None:
    calls: list[str] = []
    registry, story = _registry_with([])
    registry.decorators.append(_wrapper("late", calls))

    rendered = render_story(story, _CTX, registry=registry)
    qtbot.addWidget(rendered.root)

    assert calls == ["late"]
    assert rendered.root.objectName() == "late"


def test_a_decorator_receives_the_context() -> None:
    received: list[StoryContext] = []

    def record(widget: QWidget, ctx: StoryContext) -> QWidget:
        received.append(ctx)
        return widget

    registry, story = _registry_with([record], [record])
    ctx = StoryContext(args={"n": 1}, theme="Dark")

    rendered = render_story(story, ctx, registry=registry)

    assert received == [ctx, ctx]
    assert received[0] is ctx
    rendered.root.deleteLater()


def test_a_320_by_200_widget_sits_inside_24_pixels_of_padding(qtbot) -> None:
    registry, story = _registry_with([padding(24), fixed_size(320, 200)])

    rendered = render_story(story, _CTX, registry=registry)
    qtbot.addWidget(rendered.root)
    rendered.root.resize(rendered.root.sizeHint())
    rendered.root.show()
    qtbot.waitExposed(rendered.root)
    QApplication.processEvents()

    assert rendered.root.size() == rendered.widget.size().grownBy(_margins(rendered.root))
    assert rendered.widget.geometry() == QRect(24, 24, 320, 200)
    assert rendered.root.width() == 368
    assert rendered.root.height() == 248


def test_a_five_line_decorator_can_put_the_widget_in_a_group_box(qtbot) -> None:
    def in_group_box(widget: QWidget, ctx: StoryContext) -> QWidget:
        box = QGroupBox("Preview")
        QVBoxLayout(box).addWidget(widget)
        return box

    registry, story = _registry_with([in_group_box])

    rendered = render_story(story, _CTX, registry=registry)
    qtbot.addWidget(rendered.root)

    assert isinstance(rendered.root, QGroupBox)
    assert rendered.root.title() == "Preview"
    assert rendered.widget.parentWidget() is rendered.root
    assert rendered.root.isAncestorOf(rendered.widget)


def test_the_story_raising_gives_the_story_title_and_chains_the_error() -> None:
    def raising(ctx: StoryContext) -> QWidget:
        raise RuntimeError("boom")

    registry = StoryRegistry()
    story = registry.story("Broken/Raises")(raising)

    with pytest.raises(StoryRenderError) as caught:
        render_story(story, _CTX, registry=registry)

    assert caught.value.title == "Broken/Raises raised RuntimeError: boom"
    assert isinstance(caught.value.__cause__, RuntimeError)
    assert "Traceback" in caught.value.details
    assert "raising" in caught.value.details
    assert "pyside6_storybook" not in caught.value.details


def test_a_story_returning_a_non_widget_gives_the_story_title() -> None:
    registry = StoryRegistry()
    story = registry.story("Broken/None")(lambda ctx: None)  # ty: ignore[invalid-argument-type]

    with pytest.raises(StoryRenderError) as caught:
        render_story(story, _CTX, registry=registry)

    assert caught.value.title == "Broken/None returned None, expected a QWidget"
    assert caught.value.details == "A story function must return the widget it builds."
    assert caught.value.__cause__ is None


def test_a_decorator_raising_gives_a_title_with_its_repr_and_chains_the_error() -> None:
    class Exploding:
        def __call__(self, widget: QWidget, ctx: StoryContext) -> QWidget:
            raise ValueError("no good")

        def __repr__(self) -> str:
            return "exploding()"

    registry, story = _registry_with([Exploding()])

    with pytest.raises(StoryRenderError) as caught:
        render_story(story, _CTX, registry=registry)

    assert caught.value.title == "Group/Story: decorator exploding() raised ValueError: no good"
    assert isinstance(caught.value.__cause__, ValueError)
    assert "ValueError: no good" in caught.value.details
    assert "__call__" in caught.value.details
    assert "pyside6_storybook" not in caught.value.details


def test_a_decorator_returning_a_non_widget_gives_a_title_with_both_reprs() -> None:
    class Wrong:
        def __call__(self, widget: QWidget, ctx: StoryContext) -> QWidget:
            return 42  # ty: ignore[invalid-return-type]

        def __repr__(self) -> str:
            return "wrong()"

    registry, story = _registry_with([Wrong()])

    with pytest.raises(StoryRenderError) as caught:
        render_story(story, _CTX, registry=registry)

    assert caught.value.title == "Group/Story: decorator wrong() returned 42, expected a QWidget"
    assert caught.value.__cause__ is None


def test_a_decorator_dropping_the_widget_gives_a_title_naming_the_decorator() -> None:
    class Dropping:
        def __call__(self, widget: QWidget, ctx: StoryContext) -> QWidget:
            return QLabel("replacement")

        def __repr__(self) -> str:
            return "dropping()"

    registry, story = _registry_with([Dropping()])

    with pytest.raises(StoryRenderError) as caught:
        render_story(story, _CTX, registry=registry)

    assert caught.value.title == "Group/Story: decorator dropping() returned a widget that does not contain the story's widget"


def test_a_registry_decorator_failure_is_reported_like_a_story_decorator_failure() -> None:
    def failing(widget: QWidget, ctx: StoryContext) -> QWidget:
        raise KeyError("x")

    registry, story = _registry_with([], [failing])

    with pytest.raises(StoryRenderError) as caught:
        render_story(story, _CTX, registry=registry)

    assert caught.value.title.startswith("Group/Story: decorator <function ")
    assert caught.value.title.endswith(" raised KeyError: 'x'")


def test_a_failing_outer_decorator_deletes_every_widget_built_so_far(qtbot) -> None:
    built: list[QWidget] = []
    calls: list[str] = []

    def story_function(ctx: StoryContext) -> QWidget:
        widget = QLabel("story")
        built.append(widget)
        return widget

    def failing(widget: QWidget, ctx: StoryContext) -> QWidget:
        raise RuntimeError("late failure")

    inner = _wrapper("inner", calls)

    def recording_inner(widget: QWidget, ctx: StoryContext) -> QWidget:
        wrapper = inner(widget, ctx)
        built.append(wrapper)
        return wrapper

    registry = StoryRegistry()
    story = registry.story("Group/Story", decorators=[failing, recording_inner])(story_function)

    with pytest.raises(StoryRenderError):
        render_story(story, _CTX, registry=registry)

    assert len(built) == 2
    assert _alive(*built) == [False, False]


def test_a_decorator_that_wraps_the_widget_and_then_raises_leaves_no_wrapper_alive() -> None:
    wrappers: list[QWidget] = []

    def wrap_then_raise(widget: QWidget, ctx: StoryContext) -> QWidget:
        wrapper = QWidget()
        QVBoxLayout(wrapper).addWidget(widget)
        wrappers.append(wrapper)
        raise RuntimeError("after wrapping")

    registry, story = _registry_with([wrap_then_raise])

    with pytest.raises(StoryRenderError):
        render_story(story, _CTX, registry=registry)

    assert _alive(*wrappers) == [False]


def test_a_decorator_returning_a_non_widget_leaves_no_widget_alive() -> None:
    built: list[QWidget] = []

    def story_function(ctx: StoryContext) -> QWidget:
        widget = QLabel("story")
        built.append(widget)
        return widget

    registry = StoryRegistry()
    story = registry.story("Group/Story", decorators=[lambda widget, ctx: None])(story_function)  # ty: ignore[invalid-argument-type]

    with pytest.raises(StoryRenderError):
        render_story(story, _CTX, registry=registry)

    assert _alive(*built) == [False]


def test_a_decorator_dropping_the_widget_leaves_neither_the_widget_nor_the_replacement_alive() -> None:
    built: list[QWidget] = []

    def story_function(ctx: StoryContext) -> QWidget:
        widget = QLabel("story")
        built.append(widget)
        return widget

    def drop(widget: QWidget, ctx: StoryContext) -> QWidget:
        replacement = QLabel("replacement")
        built.append(replacement)
        return replacement

    registry = StoryRegistry()
    story = registry.story("Group/Story", decorators=[drop])(story_function)

    with pytest.raises(StoryRenderError):
        render_story(story, _CTX, registry=registry)

    assert _alive(*built) == [False, False]


def test_a_decorator_dropping_the_widget_after_a_wrapper_leaves_the_wrapper_chain_deleted() -> None:
    calls: list[str] = []
    built: list[QWidget] = []

    def story_function(ctx: StoryContext) -> QWidget:
        widget = QLabel("story")
        built.append(widget)
        return widget

    inner = _wrapper("inner", calls)

    def recording_inner(widget: QWidget, ctx: StoryContext) -> QWidget:
        wrapper = inner(widget, ctx)
        built.append(wrapper)
        return wrapper

    def drop(widget: QWidget, ctx: StoryContext) -> QWidget:
        replacement = QLabel("replacement")
        built.append(replacement)
        return replacement

    registry = StoryRegistry()
    story = registry.story("Group/Story", decorators=[drop, recording_inner])(story_function)

    with pytest.raises(StoryRenderError):
        render_story(story, _CTX, registry=registry)

    assert _alive(*built) == [False, False, False]


def test_a_failure_deletes_a_widget_the_story_parented_elsewhere_but_not_its_owner(qtbot) -> None:
    owner = QWidget()
    qtbot.addWidget(owner)
    child = QLabel("owned", owner)

    def story_function(ctx: StoryContext) -> QWidget:
        return child

    def failing(widget: QWidget, ctx: StoryContext) -> QWidget:
        raise RuntimeError("fail")

    registry = StoryRegistry()
    story = registry.story("Group/Story", decorators=[failing])(story_function)

    with pytest.raises(StoryRenderError):
        render_story(story, _CTX, registry=registry)

    assert _alive(owner, child) == [True, False]
