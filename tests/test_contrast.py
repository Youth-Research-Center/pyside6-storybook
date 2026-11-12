import pytest

from pyside6_storybook.contrast import contrast_ratio, pick_contrasting_text


def test_white_vs_black_is_max_contrast() -> None:
    assert contrast_ratio("#FFFFFF", "#000000") == pytest.approx(21.0, abs=0.01)


def test_contrast_is_symmetric() -> None:
    assert contrast_ratio("#000000", "#FFFFFF") == pytest.approx(21.0, abs=0.01)
    assert contrast_ratio("#4A56C6", "#F0F0F0") == pytest.approx(contrast_ratio("#F0F0F0", "#4A56C6"))


def test_same_color_is_no_contrast() -> None:
    assert contrast_ratio("#4A56C6", "#4A56C6") == pytest.approx(1.0, abs=0.001)


def test_known_w3c_example_gray_on_white() -> None:
    assert contrast_ratio("#767676", "#FFFFFF") == pytest.approx(4.54, abs=0.05)


def test_hex_without_hash_is_accepted() -> None:
    assert contrast_ratio("FFFFFF", "000000") == pytest.approx(21.0, abs=0.01)


@pytest.mark.parametrize("bad", ["#FFF", "#GGGGGG", ""])
def test_malformed_colors_raise_value_error(bad: str) -> None:
    with pytest.raises(ValueError):
        contrast_ratio(bad, "#000000")


@pytest.mark.parametrize("background", ["#FFFFFF", "#F0F0F0", "#FFD700", "#2F6FD0", "#2B2B2B", "#000000", "#4A56C6"])
def test_pick_contrasting_text_meets_aa_and_beats_the_alternative(background: str) -> None:
    chosen = pick_contrasting_text(background)
    other = "#000000" if chosen == "#FFFFFF" else "#FFFFFF"
    assert contrast_ratio(chosen, background) >= 4.5
    assert contrast_ratio(chosen, background) >= contrast_ratio(other, background)


def test_pick_contrasting_text_picks_white_on_dark_and_black_on_light() -> None:
    assert pick_contrasting_text("#101010") == "#FFFFFF"
    assert pick_contrasting_text("#F5F5F5") == "#000000"
