"""CHANGELOG.md keeps one format, so the release workflow can extract the notes of a version."""

import re
from pathlib import Path

import changelog_section
import pytest

_CHANGELOG = Path(__file__).resolve().parents[1] / "CHANGELOG.md"

pytestmark = pytest.mark.skipif(not _CHANGELOG.is_file(), reason="CHANGELOG.md is not part of this source tree")

_HEADINGS = ["Breaking", "Added", "Changed", "Fixed", "Removed", "Deprecated", "Security"]
_RELEASE_HEADING = re.compile(r"^## \[(\d+\.\d+\.\d+)\] - \d{4}-\d{2}-\d{2}$")


def _text() -> str:
    return _CHANGELOG.read_text(encoding="utf-8")


def _sections() -> dict[str, list[str]]:
    """Returns the lines of each `## [` section by its name, without the link references."""
    sections: dict[str, list[str]] = {}
    current: list[str] | None = None
    for line in _text().splitlines():
        match = re.match(r"^## \[([^\]]+)\]", line)
        if match:
            current = sections.setdefault(match.group(1), [])
        elif line.startswith("## ") or re.match(r"^\[[^\]]+\]:\s", line):
            current = None
        elif current is not None:
            current.append(line)
    return sections


def _header() -> str:
    return _text().split("\n## ", 1)[0]


def test_the_header_links_the_format_and_the_versioning_and_states_the_rule() -> None:
    header = " ".join(_header().split())

    assert "https://keepachangelog.com/en/1.1.0/" in header
    assert "https://semver.org/" in header
    assert "Every user-facing pull request adds one entry under `[Unreleased]`" in header
    assert "`### Breaking` comes first" in header


def test_every_section_heading_is_unreleased_or_a_version_with_a_date() -> None:
    headings = [line for line in _text().splitlines() if line.startswith("## ")]

    assert headings
    assert headings[0] == "## [Unreleased]"
    for heading in headings:
        assert heading == "## [Unreleased]" or _RELEASE_HEADING.match(heading), heading


def test_the_subheadings_of_each_section_are_known_and_breaking_comes_first() -> None:
    in_code = False
    for name, body in _sections().items():
        found: list[str] = []
        for line in body:
            if line.startswith("```"):
                in_code = not in_code
            elif not in_code and line.startswith("#"):
                match = re.match(r"^### (.+)$", line)
                assert match, f"[{name}]: {line}"
                found.append(match.group(1))
        assert set(found) <= set(_HEADINGS), (name, found)
        assert len(found) == len(set(found)), (name, found)
        assert found == sorted(found, key=_HEADINGS.index), f"[{name}] headings are not in the order {_HEADINGS}: {found}"


def test_every_version_heading_has_a_link_reference_and_unreleased_links_to_main_until_a_tag_exists() -> None:
    text = _text()
    versions = [match.group(1) for line in text.splitlines() if (match := _RELEASE_HEADING.match(line))]

    for name in ["Unreleased", *versions]:
        assert re.search(rf"^\[{re.escape(name)}\]: https://\S+$", text, flags=re.MULTILINE), f"no link reference for [{name}]"
    if not versions:
        assert "[Unreleased]: https://github.com/Youth-Research-Center/pyside6-storybook/commits/main" in text


def test_the_notes_of_a_pre_release_are_the_unreleased_section() -> None:
    notes = changelog_section.extract_section(_text(), "0.1.0rc1")

    assert notes
    assert notes == changelog_section.extract_section(_text(), "Unreleased")
    assert "### Added" in notes
