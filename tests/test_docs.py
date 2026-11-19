"""Keep the documentation site honest: the API reference lists every public name and no page links outside docs/ relatively."""

import re
from pathlib import Path

import pytest
import yaml

import pyside6_storybook
import pyside6_storybook.checks

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
