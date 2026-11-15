"""Keep the README's code honest: the first story loads and renders, and the controls table matches the library."""

import re
import textwrap
import typing
from pathlib import Path

import pytest
from PySide6.QtWidgets import QPushButton
from story_files import write

from pyside6_storybook import Control, StoryContext, StoryRegistry, load_stories
from pyside6_storybook.discovery import sources
from pyside6_storybook.discovery.sources import resolve_story_sources

_README = Path(__file__).resolve().parents[1] / "README.md"


def _section(heading: str) -> str:
    text = _README.read_text(encoding="utf-8")
    start = text.index(f"## {heading}\n")
    end = text.find("\n## ", start + 1)
    return text[start : end if end != -1 else len(text)]


def _code_blocks(section: str, language: str) -> list[str]:
    return [textwrap.dedent(block) for block in re.findall(rf"```{language}\n(.*?)```", section, flags=re.DOTALL)]


def test_the_first_story_loads_and_renders(qtbot, tmp_path: Path, stories: StoryRegistry) -> None:
    (source,) = _code_blocks(_section("Your first story"), "python")
    write(tmp_path, "stories/greeting_story.py", source)

    result = load_stories(["stories"], cwd=tmp_path)

    assert result.errors == ()
    greeting = stories.get("Buttons/Greeting")
    widget = greeting(StoryContext(args=greeting.default_args()))
    qtbot.addWidget(widget)
    assert isinstance(widget, QPushButton)
    assert widget.text() == "Hello!"
    assert widget.isEnabled()


def test_the_controls_table_lists_every_control_type() -> None:
    documented = set(re.findall(r"^\| `(\w+Control)\(", _section("Controls"), flags=re.MULTILINE))
    assert documented == {control.__name__ for control in typing.get_args(Control)}


def test_the_pyproject_example_is_a_valid_configuration(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pyproject_example = _code_blocks(_section("Where your stories come from"), "toml")[0]
    write(tmp_path, "pyproject.toml", pyproject_example)
    (tmp_path / "src").mkdir()
    monkeypatch.setattr(sources, "entry_points", lambda group: [])

    resolved = resolve_story_sources([], examples=False, cwd=tmp_path)

    assert resolved.targets == ("stories",)
    assert resolved.pythonpath == ((tmp_path / "src").resolve(),)


def test_the_variants_example_registers_its_variants(qtbot, tmp_path: Path, stories: StoryRegistry) -> None:
    (source,) = _code_blocks(_section("Variants"), "python")
    write(tmp_path, "stories/button_stories.py", source)

    result = load_stories(["stories"], cwd=tmp_path)

    assert result.errors == ()
    assert stories.ids() == ["Inputs/Push Button/Default", "Inputs/Push Button/Disabled", "Inputs/Push Button/Long label"]
    disabled = stories.get("Inputs/Push Button/Disabled")
    assert dict(disabled.args) == {"enabled": False}
    assert disabled.default_args() == {"text": "Click me", "enabled": False}
    long_label = stories.get("Inputs/Push Button/Long label")
    assert long_label.variant_of is stories.get("Inputs/Push Button/Default")
    widget = disabled(StoryContext(args=disabled.default_args()))
    qtbot.addWidget(widget)
    assert isinstance(widget, QPushButton)
    assert not widget.isEnabled()
