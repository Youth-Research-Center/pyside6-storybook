from icon_testing import assert_tinted, strongest_pixel
from PySide6.QtGui import QColor, QFontDatabase, QPalette
from PySide6.QtWidgets import QLabel, QPlainTextEdit

from pyside6_storybook.gui.error_panel import ErrorPanel


def test_shows_the_title_and_the_details(qtbot) -> None:
    panel = ErrorPanel("Story raised ValueError", "Traceback (most recent call last):\n  ...\nValueError: bad")
    qtbot.addWidget(panel)

    assert panel.title() == "Story raised ValueError"
    assert panel.details().endswith("ValueError: bad")
    title = panel.findChild(QLabel, "sbkErrorTitle")
    assert title is not None
    assert title.text() == "Story raised ValueError"


def test_details_are_read_only_selectable_monospace_text(qtbot) -> None:
    panel = ErrorPanel("Title", "line one\nline two")
    qtbot.addWidget(panel)
    details = panel.findChild(QPlainTextEdit, "sbkErrorDetails")
    assert details is not None

    assert details.isReadOnly()
    details.selectAll()
    assert details.textCursor().selectedText().replace(" ", "\n") == "line one\nline two"
    assert details.font().family() == QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont).family()


def test_empty_details_are_hidden(qtbot) -> None:
    panel = ErrorPanel("Only a title", "")
    qtbot.addWidget(panel)
    panel.show()
    details = panel.findChild(QPlainTextEdit, "sbkErrorDetails")
    assert details is not None
    assert not details.isVisible()


def test_accessible_names_describe_the_error(qtbot) -> None:
    panel = ErrorPanel("Story raised ValueError", "trace")
    qtbot.addWidget(panel)
    details = panel.findChild(QPlainTextEdit, "sbkErrorDetails")
    assert details is not None

    assert panel.accessibleName() == "Error: Story raised ValueError"
    assert details.accessibleName() == "Error details"


def test_uses_no_fixed_colours(qtbot) -> None:
    panel = ErrorPanel("Title", "details")
    qtbot.addWidget(panel)
    assert panel.styleSheet() == ""
    for child in panel.findChildren(QLabel) + panel.findChildren(QPlainTextEdit):
        assert child.styleSheet() == ""


def test_a_warning_icon_tinted_with_the_text_colour_sits_beside_the_title(qtbot) -> None:
    panel = ErrorPanel("Story raised ValueError", "trace")
    qtbot.addWidget(panel)
    panel.show()
    icon = panel.findChild(QLabel, "sbkErrorIcon")
    title = panel.findChild(QLabel, "sbkErrorTitle")
    assert icon is not None
    assert title is not None
    pixmap = icon.pixmap()

    assert not pixmap.isNull()
    assert_tinted(strongest_pixel(pixmap), panel.palette().color(QPalette.ColorGroup.Active, QPalette.ColorRole.WindowText).name())
    assert icon.geometry().right() < title.geometry().left()


def test_the_icon_is_rendered_again_when_the_palette_changes(qtbot) -> None:
    panel = ErrorPanel("Title", "details")
    qtbot.addWidget(panel)
    icon = panel.findChild(QLabel, "sbkErrorIcon")
    assert icon is not None
    palette = QPalette(panel.palette())
    palette.setColor(QPalette.ColorGroup.Active, QPalette.ColorRole.WindowText, QColor("#ff0000"))
    palette.setColor(QPalette.ColorGroup.Inactive, QPalette.ColorRole.WindowText, QColor("#ff0000"))

    panel.setPalette(palette)

    assert_tinted(strongest_pixel(icon.pixmap()), "#ff0000")
