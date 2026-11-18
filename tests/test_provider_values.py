from typing import Any

import pytest
from PySide6.QtCore import Qt

from pyside6_storybook.themes import BuiltinThemeProvider
from pyside6_storybook.themes.provider_values import read_color_scheme, read_tokens


class _Bare(BuiltinThemeProvider):
    tokens = None
    color_scheme = None


class _Provider(BuiltinThemeProvider):
    def __init__(self, *, tokens: object = None, scheme: object = None, error: Exception | None = None) -> None:
        super().__init__()
        self._tokens_value, self._scheme_value, self._error = tokens, scheme, error

    def tokens(self) -> Any:
        if self._error is not None:
            raise self._error
        return self._tokens_value

    def color_scheme(self) -> Any:
        if self._error is not None:
            raise self._error
        return self._scheme_value


def test_a_provider_without_the_optional_methods_gives_no_tokens_and_no_scheme() -> None:
    provider = _Bare()

    assert read_tokens(provider) == {}
    assert read_color_scheme(provider) is None


def test_tokens_and_the_scheme_are_returned_as_the_provider_gives_them() -> None:
    provider = _Provider(tokens={"accent": "#123456"}, scheme=Qt.ColorScheme.Dark)

    assert read_tokens(provider) == {"accent": "#123456"}
    assert read_color_scheme(provider) is Qt.ColorScheme.Dark


def test_tokens_that_are_not_a_mapping_raise() -> None:
    with pytest.raises(TypeError, match=r"tokens\(\) returned list, expected a mapping"):
        read_tokens(_Provider(tokens=["accent"]))


def test_a_scheme_that_is_not_a_qt_colour_scheme_raises() -> None:
    with pytest.raises(TypeError, match=r"color_scheme\(\) returned str, expected a Qt.ColorScheme"):
        read_color_scheme(_Provider(scheme="dark"))


def test_an_error_in_the_provider_propagates() -> None:
    provider = _Provider(error=RuntimeError("boom"))

    with pytest.raises(RuntimeError, match="boom"):
        read_tokens(provider)
    with pytest.raises(RuntimeError, match="boom"):
        read_color_scheme(provider)
