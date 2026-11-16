import pytest
from PySide6.QtCore import QMargins, QRect, QSize
from PySide6.QtWidgets import QApplication, QFrame, QLabel, QPushButton, QWidget

from pyside6_storybook import Decorator, StoryContext
from pyside6_storybook import decorators as decorators_module
from pyside6_storybook.decorators import fixed_size, frame, padding

_CTX = StoryContext(args={})


class _Box(QWidget):
    def sizeHint(self) -> QSize:
        return QSize(100, 60)


def _margins(widget: QWidget) -> QMargins:
    layout = widget.layout()
    assert layout is not None
    return layout.contentsMargins()


def _show(qtbot, widget: QWidget) -> None:
    qtbot.addWidget(widget)
    widget.resize(widget.sizeHint())
    widget.show()
    qtbot.waitExposed(widget)
    QApplication.processEvents()


def test_the_module_exports_the_decorators_and_the_type() -> None:
    assert set(decorators_module.__all__) == {"Decorator", "fixed_size", "frame", "padding"}
    assert decorators_module.Decorator is Decorator


def test_padding_wraps_the_widget_in_a_transparent_widget_with_margins(qtbot) -> None:
    widget = _Box()

    wrapper = padding(24, 8)(widget, _CTX)
    _show(qtbot, wrapper)

    assert type(wrapper) is QWidget
    assert widget.parentWidget() is wrapper
    assert not wrapper.autoFillBackground()
    assert wrapper.size() == widget.size().grownBy(_margins(wrapper))
    assert widget.geometry() == QRect(24, 8, 100, 60)
    assert wrapper.width() == 148
    assert wrapper.height() == 76


def test_padding_vertical_defaults_to_horizontal(qtbot) -> None:
    widget = _Box()

    wrapper = padding(12)(widget, _CTX)
    _show(qtbot, wrapper)

    margins = _margins(wrapper)
    assert (margins.left(), margins.top(), margins.right(), margins.bottom()) == (12, 12, 12, 12)
    assert widget.geometry() == QRect(12, 12, 100, 60)


def test_padding_of_zero_adds_no_space(qtbot) -> None:
    widget = _Box()

    wrapper = padding(0)(widget, _CTX)
    _show(qtbot, wrapper)

    assert widget.geometry() == QRect(0, 0, 100, 60)


@pytest.mark.parametrize(("args", "message"), [((-1,), "horizontal"), ((4, -2), "vertical")])
def test_padding_rejects_negative_values(args: tuple[int, ...], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        padding(*args)


@pytest.mark.parametrize("args", [(1.5,), ("4",), (True,), (4, 2.5)])
def test_padding_rejects_values_that_are_not_ints(args: tuple[object, ...]) -> None:
    with pytest.raises(TypeError, match="must be an int"):
        padding(*args)  # ty: ignore[invalid-argument-type]


def test_padding_repr() -> None:
    assert repr(padding(24)) == "padding(24)"
    assert repr(padding(24, 8)) == "padding(24, 8)"
    assert repr(padding(0, 0)) == "padding(0, 0)"


def test_frame_wraps_the_widget_in_a_styled_panel_with_no_margins(qtbot) -> None:
    widget = _Box()

    wrapper = frame()(widget, _CTX)
    _show(qtbot, wrapper)

    assert isinstance(wrapper, QFrame)
    assert wrapper.frameShape() is QFrame.Shape.StyledPanel
    assert widget.parentWidget() is wrapper
    margins = _margins(wrapper)
    assert (margins.left(), margins.top(), margins.right(), margins.bottom()) == (0, 0, 0, 0)
    assert wrapper.contentsRect().size() == widget.size()
    assert widget.geometry() == wrapper.contentsRect()


def test_frame_repr() -> None:
    assert repr(frame()) == "frame()"


def test_fixed_size_sets_the_size_on_the_received_widget_and_returns_it(qtbot) -> None:
    widget = QPushButton("x")
    qtbot.addWidget(widget)

    result = fixed_size(320, 200)(widget, _CTX)

    assert result is widget
    assert widget.minimumSize() == widget.maximumSize() == QSize(320, 200)
    widget.show()
    qtbot.waitExposed(widget)
    assert widget.size().width() == 320
    assert widget.size().height() == 200
    assert widget.parentWidget() is None


@pytest.mark.parametrize("args", [(0, 10), (10, 0), (-1, 10), (10, -5)])
def test_fixed_size_rejects_non_positive_sizes(args: tuple[int, int]) -> None:
    with pytest.raises(ValueError, match="must be positive"):
        fixed_size(*args)


def test_fixed_size_rejects_values_that_are_not_ints() -> None:
    with pytest.raises(TypeError, match="must be an int"):
        fixed_size(1.5, 10)  # ty: ignore[invalid-argument-type]


def test_fixed_size_repr() -> None:
    assert repr(fixed_size(320, 200)) == "fixed_size(320, 200)"


def test_the_built_ins_are_callable_decorators(qtbot) -> None:
    label = QLabel("x")
    qtbot.addWidget(label)
    for decorator in (padding(2), frame(), fixed_size(10, 10)):
        assert callable(decorator)
