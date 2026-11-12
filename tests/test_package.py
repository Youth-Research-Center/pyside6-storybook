from importlib.metadata import version
from pathlib import Path

import pyside6_storybook


def test_version_comes_from_package_metadata() -> None:
    assert pyside6_storybook.__version__ == version("pyside6-storybook")


def test_public_api_is_exported() -> None:
    expected = {
        "BoolControl",
        "ChoiceControl",
        "Control",
        "FloatControl",
        "IntControl",
        "Story",
        "StoryContext",
        "StoryRegistry",
        "TextControl",
        "__version__",
        "default_registry",
        "story",
    }
    assert set(pyside6_storybook.__all__) == expected
    for name in expected:
        assert hasattr(pyside6_storybook, name)


def test_package_ships_a_py_typed_marker() -> None:
    assert (Path(pyside6_storybook.__file__).parent / "py.typed").is_file()
