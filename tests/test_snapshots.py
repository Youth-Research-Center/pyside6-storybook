"""``compare``, ``diff_image``, ``capture`` and the file helpers of the snapshot support."""

from pathlib import Path

import pytest
from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import QLabel, QLineEdit, QWidget

from pyside6_storybook.testing import snapshots

_WHITE = QColor(255, 255, 255)


def _image(width: int = 20, height: int = 10, color: QColor = _WHITE) -> QImage:
    image = QImage(width, height, snapshots.SNAPSHOT_FORMAT)
    image.fill(color)
    return image


def test_equal_images_match() -> None:
    diff = snapshots.compare(_image(), _image())

    assert diff.matches
    assert (diff.differing_pixels, diff.share, diff.total_pixels) == (0, 0.0, 200)


def test_one_different_pixel_fails_without_tolerance() -> None:
    actual = _image()
    actual.setPixelColor(3, 4, QColor(250, 255, 255))

    diff = snapshots.compare(_image(), actual)

    assert not diff.matches
    assert diff.differing_pixels == 1
    assert diff.share == pytest.approx(1 / 200)


def test_a_difference_within_the_tolerance_is_equal_and_beyond_it_is_not() -> None:
    actual = _image()
    actual.setPixelColor(3, 4, QColor(250, 255, 255))  # a difference of 5 in one channel

    assert snapshots.compare(_image(), actual, tolerance=5).matches
    assert snapshots.compare(_image(), actual, tolerance=5).differing_pixels == 0
    assert snapshots.compare(_image(), actual, tolerance=4).differing_pixels == 1


def test_the_tolerance_applies_to_every_channel() -> None:
    actual = _image()
    actual.setPixelColor(0, 0, QColor(255, 255, 240))

    assert snapshots.compare(_image(), actual, tolerance=14).differing_pixels == 1
    assert snapshots.compare(_image(), actual, tolerance=15).differing_pixels == 0


def test_the_share_limit() -> None:
    actual = _image()
    for x in range(2):
        actual.setPixelColor(x, 0, QColor(0, 0, 0))  # 2 of 200 pixels: 1 %

    assert not snapshots.compare(_image(), actual, max_diff=0.009).matches
    assert snapshots.compare(_image(), actual, max_diff=0.01).matches


def test_a_size_mismatch_does_not_match_whatever_the_limits() -> None:
    diff = snapshots.compare(_image(20, 10), _image(20, 11), tolerance=255, max_diff=1.0)

    assert not diff.matches
    assert not diff.size_matches
    assert (diff.baseline_size, diff.actual_size) == ((20, 10), (20, 11))


def test_the_diff_image_shows_differing_pixels_in_red_over_a_faded_actual_image() -> None:
    actual = _image(color=QColor(0, 0, 0))
    actual.setPixelColor(5, 6, QColor(0, 0, 255))
    baseline = _image(color=QColor(0, 0, 0))

    diff = snapshots.diff_image(baseline, actual)

    assert diff.pixelColor(5, 6) == QColor(255, 0, 0)
    faded = diff.pixelColor(0, 0)
    assert faded != QColor(0, 0, 0)
    assert faded.red() == faded.green() == faded.blue() > 100
    assert (diff.width(), diff.height()) == (20, 10)


def test_the_diff_image_of_another_size_covers_both_and_marks_the_extra_area() -> None:
    diff = snapshots.diff_image(_image(20, 10), _image(25, 12))

    assert (diff.width(), diff.height()) == (25, 12)
    assert diff.pixelColor(22, 3) == QColor(255, 0, 0)
    assert diff.pixelColor(3, 11) == QColor(255, 0, 0)
    assert diff.pixelColor(3, 3) != QColor(255, 0, 0)


def test_a_row_that_equals_is_not_looked_at_per_pixel(monkeypatch: pytest.MonkeyPatch) -> None:
    actual = _image(50, 40)
    actual.setPixelColor(7, 12, QColor(0, 0, 0))
    seen: list[int] = []
    original = snapshots._differing_columns

    def spy(baseline_row: bytes, actual_row: bytes, tolerance: int) -> list[int]:
        seen.append(len(baseline_row))
        return original(baseline_row, actual_row, tolerance)

    monkeypatch.setattr(snapshots, "_differing_columns", spy)

    assert snapshots.compare(_image(50, 40), actual).differing_pixels == 1
    assert seen == [50 * 4]


def test_equal_images_skip_the_row_comparison(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(snapshots, "_differing_columns", lambda *args: pytest.fail("compared per pixel"))

    assert snapshots.compare(_image(50, 40), _image(50, 40)).matches


def test_the_snapshot_name_replaces_slashes_in_the_id_and_theme() -> None:
    assert snapshots.snapshot_name("Inputs/Button/Default", "Dark") == "Inputs__Button__Default[Dark]"
    assert snapshots.snapshot_name("A/b", "x/y") == "A__b[x__y]"


def test_a_saved_image_is_loaded_back_equal(tmp_path: Path) -> None:
    image = _image(color=QColor(10, 20, 30))
    image.setPixelColor(1, 1, QColor(200, 100, 50))
    path = tmp_path / "nested" / "image.png"

    assert snapshots.save(image, path)
    loaded = snapshots.load(path)

    assert loaded is not None
    assert snapshots.compare(image, loaded).matches
    assert bytes(image.constBits()) == bytes(loaded.constBits())


def test_an_unreadable_file_loads_as_none(tmp_path: Path) -> None:
    path = tmp_path / "broken.png"
    path.write_bytes(b"not a png")

    assert snapshots.load(path) is None
    assert snapshots.load(tmp_path / "missing.png") is None


def test_capture_renders_the_widget_at_its_size_and_pixel_ratio_one(qtbot) -> None:
    widget = QWidget()
    qtbot.addWidget(widget)
    widget.resize(40, 30)
    widget.setStyleSheet("background-color: #102030;")
    widget.setAutoFillBackground(True)
    widget.show()

    image = snapshots.capture(widget)

    assert (image.width(), image.height()) == (40, 30)
    assert image.devicePixelRatio() == 1.0
    assert image.format() == snapshots.SNAPSHOT_FORMAT


def test_capture_clears_the_focus_so_a_caret_does_not_make_two_captures_differ(qtbot) -> None:
    host = QWidget()
    qtbot.addWidget(host)
    edit = QLineEdit("text", host)
    label = QLabel("x", host)
    label.move(0, 40)
    host.resize(200, 80)
    host.show()
    qtbot.waitUntil(host.isVisible, timeout=5000)
    edit.setFocus()

    first = snapshots.capture(host)

    assert not edit.hasFocus()
    assert bytes(first.constBits()) == bytes(snapshots.capture(host).constBits())
