import sys
from importlib.metadata import EntryPoint
from pathlib import Path

import pytest
from story_files import write

from pyside6_storybook.discovery import sources
from pyside6_storybook.discovery.constants import ENTRY_POINT_GROUP
from pyside6_storybook.discovery.sources import EXAMPLES_FOLDER, StorySources, StorySourcesError, put_on_sys_path, resolve_story_sources


@pytest.fixture
def no_entry_points(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sources, "entry_points", lambda group: [])


def _fake_entry_points(monkeypatch: pytest.MonkeyPatch, *pairs: tuple[str, str]) -> list[str]:
    requested: list[str] = []

    def fake(group: str) -> list[EntryPoint]:
        requested.append(group)
        return [EntryPoint(name=name, value=value, group=group) for name, value in pairs]

    monkeypatch.setattr(sources, "entry_points", fake)
    return requested


def test_command_line_targets_come_first(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    write(tmp_path, "pyproject.toml", '[tool.pyside6-storybook]\nstories = ["configured"]\n')
    _fake_entry_points(monkeypatch, ("demo", "demo.stories"))

    resolved = resolve_story_sources(["given"], examples=False, cwd=tmp_path)

    assert resolved.targets == ("given",)
    assert resolved.origin == "the command line"


def test_examples_flag_adds_the_bundled_folder_to_the_command_line(tmp_path: Path, no_entry_points: None) -> None:
    resolved = resolve_story_sources(["given"], examples=True, cwd=tmp_path)
    assert resolved.targets == ("given", str(EXAMPLES_FOLDER))

    only_examples = resolve_story_sources([], examples=True, cwd=tmp_path)
    assert only_examples.targets == (str(EXAMPLES_FOLDER),)
    assert only_examples.origin == "the command line"


def test_pyproject_stories_and_pythonpath(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    write(tmp_path, "pyproject.toml", '[tool.pyside6-storybook]\nstories = ["stories", "app.more_stories"]\npythonpath = ["src", "lib"]\n')
    (tmp_path / "src").mkdir()
    (tmp_path / "lib").mkdir()
    requested = _fake_entry_points(monkeypatch, ("demo", "demo.stories"))

    resolved = resolve_story_sources([], examples=False, cwd=tmp_path)

    assert resolved.targets == ("stories", "app.more_stories")
    assert resolved.pythonpath == ((tmp_path / "src").resolve(), (tmp_path / "lib").resolve())
    assert resolved.origin == f"[tool.pyside6-storybook] in {tmp_path / 'pyproject.toml'}"
    assert requested == []


def test_a_pyproject_without_the_table_falls_through_to_entry_points(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    write(tmp_path, "pyproject.toml", '[project]\nname = "app"\n')
    requested = _fake_entry_points(monkeypatch, ("demo", "demo.stories"), ("other", "other_pkg.gallery:unused"))

    resolved = resolve_story_sources([], examples=False, cwd=tmp_path)

    assert requested == [ENTRY_POINT_GROUP]
    assert resolved.targets == ("demo.stories", "other_pkg.gallery")
    assert resolved.origin == f"the {ENTRY_POINT_GROUP} entry points: demo, other"


def test_pythonpath_alone_still_applies_to_entry_points(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    write(tmp_path, "pyproject.toml", '[tool.pyside6-storybook]\npythonpath = ["src"]\n')
    (tmp_path / "src").mkdir()
    _fake_entry_points(monkeypatch, ("demo", "demo.stories"))

    resolved = resolve_story_sources([], examples=False, cwd=tmp_path)

    assert resolved.targets == ("demo.stories",)
    assert resolved.pythonpath == ((tmp_path / "src").resolve(),)


def test_nothing_configured_falls_back_to_the_examples(tmp_path: Path, no_entry_points: None) -> None:
    resolved = resolve_story_sources([], examples=False, cwd=tmp_path)

    assert resolved.targets == (str(EXAMPLES_FOLDER),)
    assert resolved.origin == "the built-in examples (nothing is configured)"


def test_only_the_examples_fallback_is_marked_as_a_fallback(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fresh = tmp_path / "fresh"
    fresh.mkdir()
    write(tmp_path, "configured/pyproject.toml", '[tool.pyside6-storybook]\nstories = ["stories"]\n')
    _fake_entry_points(monkeypatch)
    nothing = resolve_story_sources([], examples=False, cwd=fresh)
    _fake_entry_points(monkeypatch, ("demo", "demo.stories"))

    assert nothing.fallback is True
    assert resolve_story_sources([], examples=False, cwd=fresh).fallback is False  # entry points
    assert resolve_story_sources([], examples=False, cwd=tmp_path / "configured").fallback is False  # the pyproject table
    assert resolve_story_sources(["given"], examples=False, cwd=fresh).fallback is False  # the command line
    assert resolve_story_sources([], examples=True, cwd=fresh).fallback is False  # --examples names them explicitly


def test_fallback_is_keyword_only_and_false_by_default() -> None:
    assert StorySources(("stories",), "test").fallback is False
    with pytest.raises(TypeError):
        StorySources(("stories",), "test", (), None, None, True)  # noqa: FBT003 - the call must fail  # ty: ignore[too-many-positional-arguments]


@pytest.mark.parametrize(
    ("toml", "expected"),
    [
        ('[tool.pyside6-storybook]\nstory = ["stories"]\n', "unknown key 'story'"),
        ('[tool.pyside6-storybook]\nstories = "stories"\n', "'stories' must be a list of strings"),
        ('[tool.pyside6-storybook]\nstories = ["stories", 3]\n', "'stories' must be a list of strings"),
        ("[tool.pyside6-storybook]\nstories = []\n", "'stories' is empty"),
        ('[tool.pyside6-storybook]\nstories = [""]\n', "'stories' must be a list of strings"),
        ('[tool.pyside6-storybook]\npythonpath = "src"\n', "'pythonpath' must be a list of strings"),
        ('[tool.pyside6-storybook]\npythonpath = ["missing"]\n', "'pythonpath' folder 'missing' does not exist"),
        ('[tool]\npyside6-storybook = "stories"\n', "must be a table"),
        ("[tool.pyside6-storybook\n", "is not valid TOML"),
    ],
)
def test_configuration_errors_name_the_key_and_the_file(tmp_path: Path, no_entry_points: None, toml: str, expected: str) -> None:
    write(tmp_path, "pyproject.toml", toml)

    with pytest.raises(StorySourcesError, match="pyproject.toml") as error_info:
        resolve_story_sources([], examples=False, cwd=tmp_path)

    assert expected in str(error_info.value)


def test_a_broken_pyproject_is_an_error_even_with_command_line_targets(tmp_path: Path, no_entry_points: None) -> None:
    write(tmp_path, "pyproject.toml", "[tool.pyside6-storybook\n")

    with pytest.raises(StorySourcesError, match="not valid TOML"):
        resolve_story_sources(["given"], examples=False, cwd=tmp_path)


def test_theme_keys_are_read(tmp_path: Path, no_entry_points: None) -> None:
    write(tmp_path, "pyproject.toml", '[tool.pyside6-storybook]\nstories = ["s"]\ntheme_provider = "app.theming:provider"\ntheme = "Ink"\n')

    resolved = resolve_story_sources([], examples=False, cwd=tmp_path)

    assert (resolved.theme_provider, resolved.theme) == ("app.theming:provider", "Ink")


def test_theme_keys_default_to_none(tmp_path: Path, no_entry_points: None) -> None:
    resolved = resolve_story_sources([], examples=False, cwd=tmp_path)

    assert (resolved.theme_provider, resolved.theme) == (None, None)


def test_theme_keys_and_pythonpath_are_read_with_command_line_targets(tmp_path: Path, no_entry_points: None) -> None:
    (tmp_path / "src").mkdir()
    write(
        tmp_path,
        "pyproject.toml",
        '[tool.pyside6-storybook]\nstories = ["ignored"]\npythonpath = ["src"]\ntheme_provider = "a:b"\ntheme = "Ink"\n',
    )

    resolved = resolve_story_sources(["given"], examples=False, cwd=tmp_path)

    assert resolved.targets == ("given",)
    assert resolved.origin == "the command line"
    assert resolved.pythonpath == ((tmp_path / "src").resolve(),)
    assert (resolved.theme_provider, resolved.theme) == ("a:b", "Ink")


def test_theme_keys_are_read_with_examples(tmp_path: Path, no_entry_points: None) -> None:
    write(tmp_path, "pyproject.toml", '[tool.pyside6-storybook]\ntheme = "Dark"\n')

    assert resolve_story_sources([], examples=True, cwd=tmp_path).theme == "Dark"


def test_a_theme_only_table_still_falls_back_to_the_examples(tmp_path: Path, no_entry_points: None) -> None:
    write(tmp_path, "pyproject.toml", '[tool.pyside6-storybook]\ntheme = "Dark"\n')

    resolved = resolve_story_sources([], examples=False, cwd=tmp_path)

    assert resolved.theme == "Dark"
    assert "built-in examples" in resolved.origin


@pytest.mark.parametrize("key", ["theme_provider", "theme"])
@pytest.mark.parametrize("value", ['""', "3", "[]"])
def test_a_theme_key_must_be_a_non_empty_string(tmp_path: Path, no_entry_points: None, key: str, value: str) -> None:
    write(tmp_path, "pyproject.toml", f'[tool.pyside6-storybook]\nstories = ["s"]\n{key} = {value}\n')

    with pytest.raises(StorySourcesError, match=f"'{key}' must be a non-empty string"):
        resolve_story_sources(["given"], examples=False, cwd=tmp_path)


def test_an_empty_pythonpath_is_the_same_as_none(tmp_path: Path, no_entry_points: None) -> None:
    write(tmp_path, "pyproject.toml", '[tool.pyside6-storybook]\nstories = ["stories"]\npythonpath = []\n')

    resolved = resolve_story_sources([], examples=False, cwd=tmp_path)

    assert resolved.targets == ("stories",)
    assert resolved.pythonpath == ()


def test_a_pyproject_that_is_not_utf8_is_a_configuration_error(tmp_path: Path, no_entry_points: None) -> None:
    (tmp_path / "pyproject.toml").write_bytes(b'[tool.pyside6-storybook]\nstories = ["\xff\xfe"]\n')

    with pytest.raises(StorySourcesError, match="pyproject.toml"):
        resolve_story_sources([], examples=False, cwd=tmp_path)


def test_an_unreadable_pyproject_is_a_configuration_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, no_entry_points: None) -> None:
    write(tmp_path, "pyproject.toml", '[tool.pyside6-storybook]\nstories = ["stories"]\n')

    def refuse(self: Path, *args: object, **kwargs: object) -> str:
        raise PermissionError(13, "Permission denied", str(self))

    monkeypatch.setattr(Path, "read_text", refuse)

    with pytest.raises(StorySourcesError, match="pyproject.toml") as error_info:
        resolve_story_sources([], examples=False, cwd=tmp_path)
    assert "Permission denied" in str(error_info.value)


def test_put_on_sys_path_keeps_the_configured_order_ahead_of_the_working_directory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    src, lib, cwd = (tmp_path / "src").resolve(), (tmp_path / "lib").resolve(), tmp_path.resolve()
    monkeypatch.setattr(sys, "path", ["/somewhere/else", str(src)])

    put_on_sys_path((src, lib), cwd=cwd)

    assert sys.path == [str(src), str(lib), str(cwd), "/somewhere/else"]
