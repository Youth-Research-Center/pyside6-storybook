"""``check_text_contrast`` on hand-built widgets: each case names the measured ratio in its assertion message."""

import os
import re
import subprocess
import sys
from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor, QFont, QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

import pyside6_storybook
from pyside6_storybook.checks import CheckIssue, check_text_contrast


def _shown(qtbot, widget: QWidget) -> QWidget:
    qtbot.addWidget(widget)
    widget.show()
    qtbot.waitUntil(widget.isVisible, timeout=5000)
    return widget


def _label(qtbot, foreground: str, background: str, *, points: float = 10.0, bold: bool = False, text: str = "Sample text") -> QLabel:
    label = QLabel(text)
    font = QFont(label.font())
    font.setPointSizeF(points)
    font.setBold(bold)
    label.setFont(font)
    label.setMargin(8)
    label.setStyleSheet(f"background-color: {background}; color: {foreground};")
    return _shown(qtbot, label)  # ty: ignore[invalid-return-type]


def _messages(widget: QWidget, **kwargs: object) -> list[str]:
    return [issue.message for issue in check_text_contrast(widget, **kwargs)]  # ty: ignore[invalid-argument-type]


def test_gray_text_on_a_slightly_lighter_gray_fails_and_the_message_has_the_ratio_and_colours(qtbot) -> None:
    label = _label(qtbot, "#777777", "#888888")

    issues = check_text_contrast(label)

    assert [issue.rule for issue in issues] == ["contrast"]
    assert issues[0].widget_class == "QLabel"
    message = issues[0].message
    assert "#777777 on #888888" in message
    assert "1.26:1" in message
    assert "4.5:1" in message
    assert "normal text" in message


def test_black_on_white_passes(qtbot) -> None:
    assert check_text_contrast(_label(qtbot, "#000000", "#ffffff")) == []


@pytest.mark.parametrize(("foreground", "ratio", "passes"), [("#595959", 7.0, True), ("#b7b7b7", 2.0, False)])
def test_seven_to_one_passes_and_two_to_one_fails(qtbot, foreground: str, ratio: float, *, passes: bool) -> None:
    issues = check_text_contrast(_label(qtbot, foreground, "#ffffff"))

    assert (issues == []) is passes, f"{foreground} on #ffffff is about {ratio}:1; got {[str(issue) for issue in issues]}"


@pytest.mark.parametrize(
    ("points", "bold", "passes"),
    [(18.0, False, True), (14.0, True, True), (14.0, False, False), (10.0, False, False)],
    ids=["18pt", "14pt-bold", "14pt-regular", "10pt"],
)
def test_large_text_needs_three_to_one_and_normal_text_four_and_a_half(qtbot, points: float, *, bold: bool, passes: bool) -> None:
    issues = check_text_contrast(_label(qtbot, "#909090", "#ffffff", points=points, bold=bold))  # 3.19:1

    assert (issues == []) is passes, f"3.19:1 at {points} pt, bold={bold}: {[str(issue) for issue in issues]}"
    if issues:
        assert "3.19:1" in issues[0].message


def test_small_text_is_measured_although_thin_strokes_never_reach_the_full_colour(qtbot) -> None:
    # 5.4:1; an 8 pt font's strokes are anti-aliased, so the measured colour is a little lighter than #6a6a6a, and a colour at 4.6:1
    # would measure just under 4.5 in some fonts. The check is an estimate for thin text.
    issues = check_text_contrast(_label(qtbot, "#6a6a6a", "#ffffff", points=8.0))

    assert issues == [], [str(issue) for issue in issues]


def test_a_pixel_sized_font_is_converted_to_points_with_the_logical_dpi(qtbot) -> None:
    label = _label(qtbot, "#909090", "#ffffff")
    font = QFont(label.font())
    font.setPixelSize(round(18 * label.logicalDpiY() / 72) + 1)
    label.setFont(font)
    label.adjustSize()
    qtbot.wait(10)

    assert check_text_contrast(label) == []


def test_the_thresholds_are_parameters(qtbot) -> None:
    label = _label(qtbot, "#909090", "#ffffff")  # 3.19:1, normal text

    assert check_text_contrast(label) != []
    assert check_text_contrast(label, normal=3.0) == []
    assert "5:1" in _messages(_label(qtbot, "#595959", "#ffffff"), normal=7.5)[0]


def test_a_box_of_one_colour_fails_because_the_text_is_not_visible(qtbot) -> None:
    label = _label(qtbot, "#336699", "#336699")

    messages = _messages(label)

    assert len(messages) == 1
    assert "background colour #336699" in messages[0]
    assert "1.00:1" in messages[0]


def test_disabled_widgets_are_skipped_unless_include_disabled(qtbot) -> None:
    label = _label(qtbot, "#777777", "#888888")
    label.setEnabled(False)
    qtbot.wait(10)

    assert check_text_contrast(label) == []
    assert [issue.rule for issue in check_text_contrast(label, include_disabled=True)] == ["contrast"]


def test_hidden_widgets_and_labels_with_pictures_or_no_text_are_not_checked(qtbot) -> None:
    root = QWidget()
    layout = QVBoxLayout(root)
    for index, text in enumerate(["hidden text", "", "   "]):
        label = QLabel(text)
        label.setStyleSheet("background-color: #888888; color: #777777;")
        label.setVisible(index != 0)
        layout.addWidget(label)
    picture = QLabel("with a pixmap")
    picture.setPixmap(QPixmap(10, 10))
    layout.addWidget(picture)

    assert check_text_contrast(_shown(qtbot, root)) == []


def test_rich_text_is_measured_by_its_visible_text(qtbot) -> None:
    label = _label(qtbot, "#777777", "#888888", text="<b>Bold</b> words")

    messages = _messages(label)

    assert len(messages) == 1
    assert "Bold words" in messages[0]


def test_the_issue_names_the_widget_and_its_path_below_the_root(qtbot) -> None:
    root = QWidget()
    layout = QVBoxLayout(root)
    fine = QLabel("Fine")
    faint = QLabel("Faint")
    faint.setObjectName("faint_label")
    faint.setStyleSheet("background-color: #888888; color: #777777;")
    layout.addWidget(fine)
    layout.addWidget(faint)

    issues = check_text_contrast(_shown(qtbot, root))

    assert len(issues) == 1
    assert (issues[0].widget_class, issues[0].object_name, issues[0].path) == ("QLabel", "faint_label", "QWidget/QLabel[1]")
    assert isinstance(issues[0], CheckIssue)


def test_text_that_a_scroll_area_cuts_off_is_not_measured(qtbot) -> None:
    content = QWidget()
    layout = QVBoxLayout(content)
    for index in range(30):
        label = QLabel(f"Line {index}")
        label.setStyleSheet("background-color: #888888; color: #777777;")
        layout.addWidget(label)
    area = QScrollArea()
    area.setWidget(content)
    area.setWidgetResizable(True)
    area.resize(240, 90)

    issues = check_text_contrast(_shown(qtbot, area))

    shown = [issue.message for issue in issues]
    assert 0 < len(shown) < 30
    assert not any("background colour" in message for message in shown), shown


@pytest.mark.parametrize(
    ("make", "class_name"),
    [
        (lambda: QPushButton("Press"), "QPushButton"),
        (lambda: QLineEdit("Typed text"), "QLineEdit"),
        (lambda: _combo(), "QComboBox"),
        (lambda: _spin_box(), "QDoubleSpinBox"),
    ],
    ids=["push-button", "line-edit", "combo-box", "spin-box"],
)
def test_the_text_of_buttons_inputs_combo_boxes_and_spin_boxes_is_checked(qtbot, make, class_name: str) -> None:
    widget = make()
    widget.setStyleSheet("* { background-color: #888888; color: #777777; }")

    issues = check_text_contrast(_shown(qtbot, widget))

    assert [issue.widget_class for issue in issues] == [class_name], [str(issue) for issue in issues]
    # The style paints its own frame and gradient around the text, so only the verdict is exact.
    assert "normal text needs 4.5:1" in issues[0].message


def test_the_internals_of_a_spin_box_and_a_combo_box_are_not_measured_twice(qtbot) -> None:
    root = QWidget()
    layout = QVBoxLayout(root)
    layout.addWidget(_combo(editable=True))
    layout.addWidget(_spin_box())
    root.setStyleSheet("* { background-color: #888888; color: #777777; }")

    issues = check_text_contrast(_shown(qtbot, root))

    assert sorted(issue.widget_class for issue in issues) == ["QComboBox", "QDoubleSpinBox"], [str(issue) for issue in issues]


def test_table_items_are_checked_each_with_its_row_and_column(qtbot) -> None:
    table = QTableWidget(3, 2)
    table.setStyleSheet("QTableWidget { background-color: #ffffff; }")
    for row in range(3):
        for column in range(2):
            item = QTableWidgetItem(f"R{row}C{column}")
            if (row, column) == (1, 1):
                item.setForeground(QBrush(QColor("#cccccc")))
            table.setItem(row, column, item)
    table.resize(300, 200)

    issues = check_text_contrast(_shown(qtbot, table))

    assert len(issues) == 1, [str(issue) for issue in issues]
    assert "item (row 1, column 1)" in issues[0].message
    assert "'R1C1'" in issues[0].message
    assert "#cccccc on #ffffff" in issues[0].message


def test_only_fifty_items_of_a_view_are_checked(qtbot) -> None:
    table = QTableWidget(80, 1)
    table.setStyleSheet("QTableWidget { background-color: #ffffff; }")
    for row in range(80):
        item = QTableWidgetItem(f"Row {row}")
        item.setForeground(QBrush(QColor("#cccccc")))
        table.setItem(row, 0, item)
    table.setRowCount(80)
    for row in range(80):
        table.setRowHeight(row, 20)
    table.resize(200, 2000)

    issues = check_text_contrast(_shown(qtbot, table))

    assert len(issues) == 50


def test_the_check_is_public_in_the_checks_package_only() -> None:
    assert "check_text_contrast" not in pyside6_storybook.__all__


def _combo(*, editable: bool = False) -> QComboBox:
    combo = QComboBox()
    combo.addItems(["Alpha", "Beta"])
    combo.setEditable(editable)
    return combo


def _spin_box() -> QDoubleSpinBox:
    box = QDoubleSpinBox()
    box.setAlignment(Qt.AlignmentFlag.AlignLeft)
    box.setValue(12.5)
    return box


_SUBPIXEL_SCRIPT = """
from PySide6.QtGui import QFont, QImage
from PySide6.QtWidgets import QApplication, QLabel

from pyside6_storybook.checks import check_text_contrast

app = QApplication([])


def fringed(widget):
    image = QImage(widget.size(), QImage.Format.Format_RGB32)
    widget.render(image)
    for y in range(image.height()):
        for x in range(image.width()):
            colour = image.pixelColor(x, y)
            channels = (colour.red(), colour.green(), colour.blue())
            if max(channels) - min(channels) > 16:
                return True
    return False


label = QLabel("Sample text")
label.setMargin(8)
# Small text in the CI font: no stem is wide enough for a subpixel render to reach the text's colour in any pixel.
label.setFont(QFont("DejaVu Sans", 8))
label.setStyleSheet("background-color: #ffffff; color: #b7b7b7;")
label.show()
app.processEvents()
print("fringed" if fringed(label) else "greyscale")
for issue in check_text_contrast(label):
    print(issue.message)
"""

_SUBPIXEL_FONTCONFIG = """<?xml version="1.0"?>
<!DOCTYPE fontconfig SYSTEM "fonts.dtd">
<fontconfig>
  <include ignore_missing="yes">{base}</include>
  <match target="font">
    <edit name="antialias" mode="assign"><bool>true</bool></edit>
    <edit name="rgba" mode="assign"><const>rgb</const></edit>
    <edit name="lcdfilter" mode="assign"><const>lcddefault</const></edit>
  </match>
</fontconfig>
"""


@pytest.mark.skipif(sys.platform != "linux", reason="fontconfig decides the subpixel rendering only on Linux")
def test_subpixel_text_is_measured_in_its_own_colour(tmp_path: Path) -> None:
    # Where fontconfig asks for subpixel (LCD) text, as on GitHub's Ubuntu runners, a widget draws text with coloured fringes and no
    # pixel in the text's own colour, so the check measured #b095a8 for #909090. The check replays the render onto an image, where text
    # is greyscale. Fontconfig is read when the process starts, so the check runs in a subprocess.
    config = tmp_path / "fonts.conf"
    config.write_text(_SUBPIXEL_FONTCONFIG.format(base=os.environ.get("FONTCONFIG_FILE") or "/etc/fonts/fonts.conf"), encoding="utf-8")
    env = {**os.environ, "QT_QPA_PLATFORM": "offscreen", "FONTCONFIG_FILE": str(config)}
    result = subprocess.run([sys.executable, "-c", _SUBPIXEL_SCRIPT], capture_output=True, text=True, timeout=60, env=env, check=False)

    assert result.returncode == 0, result.stderr[-2000:]
    lines = result.stdout.splitlines()
    if lines[0] != "fringed":
        pytest.skip("this system's fontconfig does not render subpixel text")
    assert len(lines) == 2, lines
    # The text is measured in a neutral grey within a few levels of #b7b7b7 (thin greyscale strokes stop just short of it), never in
    # a fringe colour such as #c6bed2.
    match = re.search(r"is #([0-9a-f]{2})([0-9a-f]{2})([0-9a-f]{2}) on #ffffff", lines[1])
    assert match is not None, lines[1]
    channels = [int(channel, 16) for channel in match.groups()]
    assert len(set(channels)) == 1 and abs(channels[0] - 0xB7) <= 4, lines[1]
