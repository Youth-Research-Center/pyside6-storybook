"""Print the release notes of one version from CHANGELOG.md, for ``gh release create --notes-file``.

The notes are the body of ``## [X.Y.Z] - YYYY-MM-DD`` without its heading, up to the next ``## `` heading or the link references. A
pre-release such as ``0.1.0rc1`` uses ``## [0.1.0rc1]`` when it exists and ``## [Unreleased]`` otherwise, because candidates are tagged
while the changelog still says Unreleased. Standard library only.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

_PRERELEASE = re.compile(r"(a|b|rc)\d+|\.dev\d+")
_LINK_REFERENCE = re.compile(r"^\[[^\]]+\]:\s")
_DEFAULT_CHANGELOG = Path(__file__).resolve().parents[2] / "CHANGELOG.md"


def _section(lines: list[str], name: str) -> list[str] | None:
    """Returns the lines of the section ``## [name]``, or None when there is no such heading."""
    heading = re.compile(rf"^##\s+\[{re.escape(name)}\](\s|$)")
    for start, line in enumerate(lines):
        if heading.match(line):
            body: list[str] = []
            for following in lines[start + 1 :]:
                if following.startswith("## ") or _LINK_REFERENCE.match(following):
                    break
                body.append(following)
            return body
    return None


def extract_section(text: str, version: str) -> str:
    """Returns the notes of a version.

    Args:
        text: The content of the changelog.
        version: The version, without the ``v`` of the tag.

    Returns:
        The body of the section, stripped of blank lines at both ends.

    Raises:
        LookupError: The section is missing or empty.
    """
    lines = text.splitlines()
    body = _section(lines, version)
    name = version
    if body is None and _PRERELEASE.search(version):
        body = _section(lines, "Unreleased")
        name = "Unreleased"
    if body is None:
        raise LookupError(f"CHANGELOG.md has no section for {version}.")
    notes = "\n".join(body).strip()
    if not notes:
        raise LookupError(f"The section [{name}] of CHANGELOG.md is empty.")
    return notes


def main(argv: list[str], *, changelog: Path = _DEFAULT_CHANGELOG) -> int:
    """Prints the notes of ``argv[0]``. Returns the exit code."""
    if len(argv) != 1:
        print("usage: changelog_section.py VERSION", file=sys.stderr)
        return 2
    try:
        notes = extract_section(changelog.read_text(encoding="utf-8"), argv[0])
    except (LookupError, OSError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    print(notes)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
