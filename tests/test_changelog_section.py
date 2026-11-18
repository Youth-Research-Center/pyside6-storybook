from pathlib import Path

import changelog_section
import pytest

_CHANGELOG = """# Changelog

## [Unreleased]

### Added
- Something new.

## [0.2.0] - 2026-02-01

### Fixed
- A fix.

## [0.1.0] - 2026-01-01

### Added
- The first release.

## [0.0.9] - 2025-12-01

## [0.0.8] - 2025-11-01
- Last.

[Unreleased]: https://example.invalid/compare/v0.2.0...HEAD
[0.2.0]: https://example.invalid/compare/v0.1.0...v0.2.0
"""


def test_a_normal_section_is_printed_without_its_heading() -> None:
    assert changelog_section.extract_section(_CHANGELOG, "0.2.0") == "### Fixed\n- A fix."


def test_the_last_section_ends_at_the_link_references() -> None:
    assert changelog_section.extract_section(_CHANGELOG, "0.0.8") == "- Last."


def test_a_missing_version_is_an_error() -> None:
    with pytest.raises(LookupError, match=r"0\.3\.0"):
        changelog_section.extract_section(_CHANGELOG, "0.3.0")


def test_an_empty_section_is_an_error() -> None:
    with pytest.raises(LookupError, match="empty"):
        changelog_section.extract_section(_CHANGELOG, "0.0.9")


@pytest.mark.parametrize("version", ["0.3.0rc1", "0.3.0a2", "0.3.0b1", "0.3.0.dev0"])
def test_a_pre_release_without_a_section_uses_unreleased(version: str) -> None:
    assert changelog_section.extract_section(_CHANGELOG, version) == "### Added\n- Something new."


def test_a_pre_release_with_its_own_section_uses_it() -> None:
    text = _CHANGELOG.replace("## [0.2.0] - 2026-02-01", "## [0.2.0rc1] - 2026-02-01")
    assert changelog_section.extract_section(text, "0.2.0rc1") == "### Fixed\n- A fix."


def test_a_final_version_never_falls_back_to_unreleased() -> None:
    with pytest.raises(LookupError):
        changelog_section.extract_section(_CHANGELOG, "0.3.0")


def test_main_prints_the_notes(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    changelog = tmp_path / "CHANGELOG.md"
    changelog.write_text(_CHANGELOG, encoding="utf-8")

    assert changelog_section.main(["0.1.0"], changelog=changelog) == 0

    assert capsys.readouterr().out == "### Added\n- The first release.\n"


def test_main_exits_1_with_a_message_for_a_missing_version(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    changelog = tmp_path / "CHANGELOG.md"
    changelog.write_text(_CHANGELOG, encoding="utf-8")

    assert changelog_section.main(["9.9.9"], changelog=changelog) == 1

    captured = capsys.readouterr()
    assert captured.out == ""
    assert "9.9.9" in captured.err


def test_the_real_changelog_gives_the_unreleased_body_for_a_pre_release(capsys: pytest.CaptureFixture[str]) -> None:
    real = Path(changelog_section.__file__).resolve().parents[2] / "CHANGELOG.md"
    if not real.is_file():
        pytest.skip("CHANGELOG.md is not part of this source tree")
    unreleased = changelog_section.extract_section(real.read_text(encoding="utf-8"), "Unreleased")

    assert changelog_section.main(["99.0.0rc1"]) == 0

    assert capsys.readouterr().out.strip() == unreleased
    assert unreleased.startswith("### ")
