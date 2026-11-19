"""Keep the README's code honest: the first story loads and renders, and PyPI can show the page (absolute links, no alerts)."""

import re
import textwrap
from pathlib import Path

import pytest
import yaml
from PySide6.QtWidgets import QPushButton
from story_files import write

from pyside6_storybook import StoryContext, StoryRegistry, load_stories

_ROOT = Path(__file__).resolve().parents[1]
_README = _ROOT / "README.md"
_SITE = "https://youth-research-center.github.io/pyside6-storybook/"


def _section(heading: str) -> str:
    text = _README.read_text(encoding="utf-8")
    match = re.search(rf"^## {re.escape(heading)}\n", text, re.MULTILINE)
    assert match is not None, heading
    start = match.start()
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


def _prose() -> str:
    """The README without fenced code blocks and inline code, which may contain text that only looks like a link."""
    text = re.sub(r"^```.*?^```", "", _README.read_text(encoding="utf-8"), flags=re.DOTALL | re.MULTILINE)
    return re.sub(r"`[^`\n]*`", "", text)


def test_the_readme_has_no_relative_links_or_images_because_pypi_shows_it_away_from_the_repository() -> None:
    prose = _prose()

    inline = re.findall(r"\]\(\s*<?([^)\s>]*)", prose)
    references = re.findall(r"^\s*\[[^\]]+\]:\s*(\S+)", prose, flags=re.MULTILINE)
    html = re.findall(r"""\b(?:href|src)=["']([^"']*)["']""", prose)
    targets = inline + references + html

    assert targets
    relative = [target for target in targets if not target.startswith(("https://", "http://", "#", "mailto:"))]
    assert not relative


def test_the_readme_uses_no_github_alert_syntax_because_pypi_does_not_render_it() -> None:
    assert not re.search(r"^\s*>\s*\[![A-Za-z]+\]", _prose(), flags=re.MULTILINE)


def _flatten(nav: list) -> list[str]:
    pages: list[str] = []
    for entry in nav:
        if isinstance(entry, str):
            pages.append(entry)
        elif isinstance(entry, dict):
            for value in entry.values():
                pages.extend(_flatten(value) if isinstance(value, list) else [value])
    return pages


@pytest.mark.skipif(not (_ROOT / "mkdocs.yml").is_file(), reason="mkdocs.yml is not part of this source tree")
def test_every_link_to_the_docs_site_points_to_a_page_in_the_nav() -> None:
    text = _README.read_text(encoding="utf-8")
    nav = _flatten(yaml.safe_load((_ROOT / "mkdocs.yml").read_text(encoding="utf-8"))["nav"])
    paths = re.findall(rf"{re.escape(_SITE)}([^\s)#>\"']*)", text)

    assert paths
    for path in paths:
        page = (path.rstrip("/") or "index") + ".md"
        assert page in nav, f"{_SITE}{path} is not a page in the nav"
