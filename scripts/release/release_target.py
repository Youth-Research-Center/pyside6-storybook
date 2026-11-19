"""Decide where release.yml publishes and check that the ref may be released.

A tag push publishes to PyPI and a manual run publishes to TestPyPI. For a tag the script checks that the tag is ``v`` plus the version
in ``pyproject.toml`` and that the tagged commit is on ``main`` or a ``release/*`` branch. It writes the outputs the later jobs read to
the file named by ``GITHUB_OUTPUT``. Standard library only.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

_PRERELEASE = re.compile(r"(a|b|rc)\d+|\.dev\d+")
_RELEASE_BRANCH_REFS = ("refs/remotes/origin/main", "refs/remotes/origin/release/*")


class ReleaseTargetError(Exception):
    """The ref cannot be released; the message names both values that disagree."""


@dataclass(frozen=True)
class Target:
    """Where a release is published."""

    repository: str
    version: str
    prerelease: bool
    index_url: str
    upload_url: str

    def outputs(self) -> dict[str, str]:
        """Returns the job outputs, with the keys release.yml reads."""
        return {
            "repository": self.repository,
            "version": self.version,
            "prerelease": "true" if self.prerelease else "false",
            "index-url": self.index_url,
            "upload-url": self.upload_url,
        }


INDEXES = {
    "pypi": ("https://pypi.org/simple/", "https://upload.pypi.org/legacy/"),
    "testpypi": ("https://test.pypi.org/simple/", "https://test.pypi.org/legacy/"),
}


def read_version(pyproject: Path) -> str:
    """Returns the project version in a ``pyproject.toml``."""
    with pyproject.open("rb") as handle:
        return str(tomllib.load(handle)["project"]["version"])


def is_prerelease(version: str) -> bool:
    """Returns whether a version has an ``aN``, ``bN``, ``rcN`` or ``.devN`` segment."""
    return _PRERELEASE.search(version) is not None


def release_branches(repo: Path) -> list[str]:
    """Returns the remote ``main`` and ``release/*`` branches as full ref names."""
    result = subprocess.run(
        ["git", "for-each-ref", "--format=%(refname)", *_RELEASE_BRANCH_REFS],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
        timeout=60,
    )
    return result.stdout.split()


def is_ancestor(repo: Path, commit: str, branch: str) -> bool:
    """Returns whether ``commit`` is reachable from ``branch``."""
    result = subprocess.run(["git", "merge-base", "--is-ancestor", commit, branch], cwd=repo, check=False, timeout=60)
    return result.returncode == 0


def decide(env: Mapping[str, str], repo: Path) -> Target:
    """Works out the target of this run and checks a tag push.

    Args:
        env: The environment: ``GITHUB_EVENT_NAME``, ``GITHUB_REF_TYPE``, ``GITHUB_REF_NAME`` and ``GITHUB_SHA``.
        repo: The checkout, with ``pyproject.toml`` and the full history.

    Returns:
        The target.

    Raises:
        ReleaseTargetError: The tag is not ``v`` plus the version, or its commit is on no ``main`` or ``release/*`` branch.
    """
    version = read_version(repo / "pyproject.toml")
    if env.get("GITHUB_EVENT_NAME") == "push" and env.get("GITHUB_REF_TYPE") == "tag":
        repository = "pypi"
        tag = env["GITHUB_REF_NAME"]
        if tag != f"v{version}":
            raise ReleaseTargetError(f"The tag {tag} is not v{version}, the version in pyproject.toml.")
        sha = env["GITHUB_SHA"]
        branches = release_branches(repo)
        if not any(is_ancestor(repo, sha, branch) for branch in branches):
            found = ", ".join(branches) or "none"
            raise ReleaseTargetError(f"The commit {sha} of the tag {tag} is on no main or release/* branch (branches found: {found}).")
    else:
        repository = "testpypi"
    index_url, upload_url = INDEXES[repository]
    return Target(repository, version, is_prerelease(version), index_url, upload_url)


def write_outputs(target: Target, output_file: Path) -> None:
    """Appends the target's outputs to the ``GITHUB_OUTPUT`` file."""
    with output_file.open("a", encoding="utf-8") as handle:
        for key, value in target.outputs().items():
            handle.write(f"{key}={value}\n")


def main(env: Mapping[str, str] | None = None, repo: Path | None = None) -> int:
    """Runs the script. Returns the exit code."""
    env = os.environ if env is None else env
    repo = Path.cwd() if repo is None else repo
    try:
        target = decide(env, repo)
    except ReleaseTargetError as error:
        print(f"::error::{error}")
        return 1
    for key, value in target.outputs().items():
        print(f"{key}={value}")
    output_file = env.get("GITHUB_OUTPUT")
    if output_file:
        write_outputs(target, Path(output_file))
    return 0


if __name__ == "__main__":
    sys.exit(main())
