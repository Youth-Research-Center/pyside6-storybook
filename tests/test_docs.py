"""Keep the documentation site honest.

The API reference lists every public name, no page links outside docs/ relatively, every Python block on a page runs, the command-line
table matches the parser, and the examples that the pages describe do what the text says.
"""

import re
import textwrap
import typing
from pathlib import Path

import pytest
import yaml
from PySide6.QtCore import QSize
from PySide6.QtWidgets import QFrame, QGroupBox, QPlainTextEdit, QPushButton, QWidget
from story_files import write

import pyside6_storybook
import pyside6_storybook.checks
from pyside6_storybook import Control, Layout, SizePreset, StoryContext, StoryRegistry, cli, load_stories
from pyside6_storybook.decorators import padding
from pyside6_storybook.discovery import sources
from pyside6_storybook.discovery.sources import resolve_story_sources
from pyside6_storybook.registry.rendering import render_story

_ROOT = Path(__file__).resolve().parents[1]
_MKDOCS = _ROOT / "mkdocs.yml"
_DOCS = _ROOT / "docs"

pytestmark = pytest.mark.skipif(not _MKDOCS.is_file(), reason="mkdocs.yml is not part of this source tree")

_LINK = re.compile(r"!?\[[^\]]*\]\(\s*<?([^)\s>]+)")
_TARGET = re.compile(r"^:::\s+(\S+)\s*$", re.MULTILINE)


def _nav_pages(nav: list) -> list[str]:
    pages: list[str] = []
    for entry in nav:
        if isinstance(entry, str):
            pages.append(entry)
        elif isinstance(entry, dict):
            for value in entry.values():
                pages.extend(_nav_pages(value) if isinstance(value, list) else [value])
    return pages


def test_reference_lists_every_public_name_once() -> None:
    expected = {f"pyside6_storybook.{name}" for name in pyside6_storybook.__all__}
    expected |= {f"pyside6_storybook.checks.{name}" for name in pyside6_storybook.checks.__all__}

    targets = _TARGET.findall((_DOCS / "reference.md").read_text(encoding="utf-8"))

    assert sorted(targets) == sorted(expected)


def test_the_nav_lists_existing_pages() -> None:
    config = yaml.safe_load(_MKDOCS.read_text(encoding="utf-8"))
    pages = _nav_pages(config["nav"])

    assert pages
    for page in pages:
        assert (_DOCS / page).is_file(), page


def test_no_page_in_the_nav_links_outside_docs_relatively() -> None:
    config = yaml.safe_load(_MKDOCS.read_text(encoding="utf-8"))
    problems: list[str] = []
    for page in _nav_pages(config["nav"]):
        text = (_DOCS / page).read_text(encoding="utf-8")
        for target in _LINK.findall(text):
            if target.startswith(("http://", "https://", "mailto:", "#")):
                continue
            path = (_DOCS / page).parent / target.split("#", 1)[0]
            if not path.resolve().is_relative_to(_DOCS.resolve()):
                problems.append(f"{page}: {target}")

    assert not problems


# Reading the pages


def _page_text(page: str) -> str:
    return (_DOCS / page).read_text(encoding="utf-8")


def _headings(text: str) -> list[tuple[int, int, str]]:
    """Return the ATX headings outside fenced code blocks as (line index, level, title)."""
    found: list[tuple[int, int, str]] = []
    fenced = False
    for index, line in enumerate(text.split("\n")):
        if line.lstrip().startswith("```"):
            fenced = not fenced
        elif not fenced and (match := re.match(r"^(#{1,6}) (.+?)\s*$", line)):
            found.append((index, len(match.group(1)), match.group(2)))
    return found


def _section(page: str, heading: str) -> str:
    """Return a section of a page: from its heading to the next heading of the same or a higher level, or the end of the file."""
    text = _page_text(page)
    lines = text.split("\n")
    headings = _headings(text)
    position = next(i for i, (_, _, title) in enumerate(headings) if title == heading)
    start, level, _ = headings[position]
    end = next((line for line, other, _ in headings[position + 1 :] if other <= level), len(lines))
    return "\n".join(lines[start:end])


def _left_margin(widget: QWidget) -> int:
    layout = widget.layout()
    assert layout is not None
    return layout.contentsMargins().left()


def _code_blocks(section: str, language: str) -> list[str]:
    return [textwrap.dedent(block) for block in re.findall(rf"```{language}\n(.*?)```", section, flags=re.DOTALL)]


# Checks that moved from the README: the pages' examples do what the text says


def test_the_controls_table_lists_every_control_type() -> None:
    documented = set(re.findall(r"^\| `(\w+Control)\(", _section("controls.md", "Controls"), flags=re.MULTILINE))
    assert documented == {control.__name__ for control in typing.get_args(Control)}


def test_the_pyproject_example_is_a_valid_configuration(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pyproject_example = _code_blocks(_section("finding-stories.md", "Where your stories come from"), "toml")[0]
    write(tmp_path, "pyproject.toml", pyproject_example)
    (tmp_path / "src").mkdir()
    monkeypatch.setattr(sources, "entry_points", lambda group: [])

    resolved = resolve_story_sources([], examples=False, cwd=tmp_path)

    assert resolved.targets == ("stories",)
    assert resolved.pythonpath == ((tmp_path / "src").resolve(),)


def test_the_variants_example_registers_its_variants(qtbot, tmp_path: Path, stories: StoryRegistry) -> None:
    (source,) = _code_blocks(_section("writing-stories.md", "Variants"), "python")
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


def test_the_layout_example_registers_stories_with_their_layouts(qtbot, tmp_path: Path, stories: StoryRegistry) -> None:
    source = _code_blocks(_section("writing-stories.md", "Layout"), "python")[0]
    write(tmp_path, "stories/layout_stories.py", source)

    result = load_stories(["stories"], cwd=tmp_path)

    assert result.errors == ()
    assert stories.ids() == ["Buttons/Centered/Default", "Buttons/Centered/Padded", "Editors/Notes"]
    assert stories.get("Buttons/Centered/Default").layout is Layout.CENTERED
    assert stories.get("Buttons/Centered/Padded").layout is Layout.PADDED
    assert stories.get("Editors/Notes").layout is Layout.FILL
    for story_id, widget_type in (("Buttons/Centered/Padded", QPushButton), ("Editors/Notes", QPlainTextEdit)):
        example = stories.get(story_id)
        widget = example(StoryContext(args=example.default_args()))
        qtbot.addWidget(widget)
        assert isinstance(widget, widget_type)


def test_the_decorators_example_registers_and_renders_with_the_documented_order(qtbot, tmp_path: Path, stories: StoryRegistry) -> None:
    source = _code_blocks(_section("writing-stories.md", "Decorators"), "python")[0]
    write(tmp_path, "stories/card_stories.py", source)

    result = load_stories(["stories"], cwd=tmp_path)

    assert result.errors == ()
    assert stories.ids() == ["Cards/Card/Default", "Cards/Card/Framed"]
    card = stories.get("Cards/Card/Default")
    framed = stories.get("Cards/Card/Framed")
    assert [repr(decorator) for decorator in card.decorators] == ["padding(24)", "fixed_size(320, 200)"]
    assert [type(decorator).__name__ for decorator in framed.decorators] == ["_Frame", "function"]

    stories.decorators.append(padding(8))
    rendered = render_story(card, StoryContext(args={}), registry=stories)
    qtbot.addWidget(rendered.root)
    assert rendered.widget.size() == QSize(320, 200)
    inner_wrapper = rendered.widget.parentWidget()
    assert inner_wrapper is not None
    assert _left_margin(rendered.root) == 8
    assert _left_margin(inner_wrapper) == 24

    rendered_framed = render_story(framed, StoryContext(args={}, theme="Dark"), registry=stories)
    qtbot.addWidget(rendered_framed.root)
    group_box = rendered_framed.widget.parentWidget()
    assert isinstance(group_box, QGroupBox)
    assert isinstance(group_box.parentWidget(), QFrame)
    assert group_box.title() == "Dark"


def test_the_size_preset_example_adds_presets_to_the_registry(monkeypatch: pytest.MonkeyPatch) -> None:
    (source,) = _code_blocks(_section("gallery.md", "The canvas"), "python")
    isolated = StoryRegistry()
    monkeypatch.setattr(pyside6_storybook, "default_registry", isolated)

    exec(compile(source, "gallery.md", "exec"), {"__name__": "gallery_example"})  # noqa: S102 - runs the repository's own documentation

    assert isolated.size_presets == [SizePreset("Tablet", 768, 1024), SizePreset("Small laptop", 1280, 720)]


def test_the_logging_example_logs_actions_and_does_nothing_without_a_sink(qtbot, tmp_path: Path, stories: StoryRegistry) -> None:
    (source,) = _code_blocks(_section("gallery.md", "Logging actions"), "python")
    write(tmp_path, "stories/counter_stories.py", source)

    result = load_stories(["stories"], cwd=tmp_path)

    assert result.errors == ()
    counter = stories.get("Buttons/Counter")
    plain = render_story(counter, StoryContext(args={}), registry=stories)
    qtbot.addWidget(plain.root)
    assert isinstance(plain.widget, QPushButton)
    plain.widget.click()

    recorded = _RecordingSink()
    logged = render_story(counter, StoryContext(args={}, actions=recorded), registry=stories)
    qtbot.addWidget(logged.root)
    assert isinstance(logged.widget, QPushButton)
    logged.widget.setCheckable(True)
    logged.widget.click()
    assert recorded.entries == [("toggle", (True,)), ("clicked", ()), ("custom", ("any", 1))]


class _RecordingSink:
    def __init__(self) -> None:
        self.entries: list[tuple[str, tuple[object, ...]]] = []

    def record(self, name: str, args: tuple[object, ...]) -> None:
        self.entries.append((name, args))


# Every Python block on a page in the nav runs

_SKIP = re.compile(r"^<!-- docs-test: skip \u2014 (.+?) -->$")
_FENCE = re.compile(r"^(\s*)```(\w*)\s*$")

# A block that cannot run on its own is marked on the line before its fence; every skip is a decision listed here.
_EXPECTED_SKIPS = [
    ("themes.md", "opens the gallery and blocks until the window is closed"),
    ("themes.md", "a fragment that uses ctx outside a story function"),
    ("testing.md", "builds the reader's own widget with build_toolbar and needs the qtbot fixture"),
    ("testing.md", "builds the reader's own widget with build_banner and needs the qtbot fixture"),
]


def _python_blocks(page: str) -> list[tuple[str, str | None]]:
    """Return the Python blocks of a page as (source, skip reason or None)."""
    lines = _page_text(page).split("\n")
    blocks: list[tuple[str, str | None]] = []
    index = 0
    while index < len(lines):
        match = _FENCE.match(lines[index])
        if match is None:
            index += 1
            continue
        end = next(i for i in range(index + 1, len(lines)) if lines[i].strip() == "```")
        if match.group(2) == "python":
            marker = _SKIP.match(lines[index - 1].strip()) if index else None
            blocks.append((textwrap.dedent("\n".join(lines[index + 1 : end])) + "\n", marker.group(1) if marker else None))
        index = end + 1
    return blocks


def _nav() -> list[str]:
    return _nav_pages(yaml.safe_load(_MKDOCS.read_text(encoding="utf-8"))["nav"]) if _MKDOCS.is_file() else []


_BLOCKS = [(page, number) for page in _nav() for number in range(len(_python_blocks(page)))]


@pytest.mark.parametrize(("page", "number"), _BLOCKS, ids=[f"{page}-{number}" for page, number in _BLOCKS])
def test_every_python_block_runs_in_a_fresh_namespace(page: str, number: int, qapp, stories: StoryRegistry) -> None:
    source, skip_reason = _python_blocks(page)[number]
    if skip_reason is not None:
        pytest.skip(skip_reason)
    module_name = f"docs_block_{page.removesuffix('.md').replace('-', '_')}_{number}"

    exec(compile(source, f"{page} block {number}", "exec"), {"__name__": module_name})  # noqa: S102 - runs the repository's own documentation


def test_the_skipped_blocks_are_the_expected_ones() -> None:
    skipped = [(page, reason) for page in _nav() for _, reason in _python_blocks(page) if reason is not None]

    assert skipped == _EXPECTED_SKIPS


# The command-line page


def test_the_command_line_table_lists_every_option_of_the_parser() -> None:
    section = _section("command-line.md", "Options")
    documented = set(re.findall(r"^\| `(-[-\w]+)", section, flags=re.MULTILINE))
    parsed = {option for action in cli._parser()._actions for option in action.option_strings} - {"-h", "--help"}

    assert documented == parsed


def test_the_command_line_page_lists_the_exit_codes_0_1_and_2() -> None:
    codes = re.findall(r"^\| `(\d+)` \|", _section("command-line.md", "Exit codes"), flags=re.MULTILINE)

    assert codes == ["0", "1", "2"]
