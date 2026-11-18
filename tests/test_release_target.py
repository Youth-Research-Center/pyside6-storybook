import subprocess
from pathlib import Path

import pytest
import release_target

_ENV_TAG = {"GITHUB_EVENT_NAME": "push", "GITHUB_REF_TYPE": "tag"}


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
        timeout=60,
    )
    return result.stdout.strip()


def _write_version(repo: Path, version: str) -> None:
    (repo / "pyproject.toml").write_text(f'[project]\nname = "x"\nversion = "{version}"\n', encoding="utf-8")


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """A clone of an origin whose main holds one commit, with version 1.2.0."""
    origin = tmp_path / "origin"
    origin.mkdir()
    _git(origin, "init", "-b", "main")
    _write_version(origin, "1.2.0")
    _git(origin, "add", ".")
    _git(origin, "commit", "-m", "release")
    clone = tmp_path / "clone"
    _git(tmp_path, "clone", str(origin), str(clone))
    return clone


def _env(repo: Path, tag: str) -> dict[str, str]:
    return {**_ENV_TAG, "GITHUB_REF_NAME": tag, "GITHUB_SHA": _git(repo, "rev-parse", "HEAD")}


@pytest.mark.parametrize(
    ("version", "expected"),
    [("1.0.0", False), ("1.0.0a1", True), ("1.0.0b2", True), ("1.0.0rc1", True), ("1.0.0.dev0", True), ("1.0.0.post1", False)],
)
def test_prerelease_detection(version: str, *, expected: bool) -> None:
    assert release_target.is_prerelease(version) is expected


def test_a_tag_on_main_publishes_to_pypi(repo: Path) -> None:
    target = release_target.decide(_env(repo, "v1.2.0"), repo)

    assert target.outputs() == {
        "repository": "pypi",
        "version": "1.2.0",
        "prerelease": "false",
        "index-url": "https://pypi.org/simple/",
        "upload-url": "https://upload.pypi.org/legacy/",
    }


def test_a_tag_that_is_not_v_plus_the_version_is_rejected_with_both_values(repo: Path) -> None:
    with pytest.raises(release_target.ReleaseTargetError) as error:
        release_target.decide(_env(repo, "v1.3.0"), repo)

    assert "v1.3.0" in str(error.value)
    assert "v1.2.0" in str(error.value)


def test_a_tag_on_a_commit_outside_main_and_release_branches_is_rejected(repo: Path) -> None:
    _git(repo, "checkout", "-b", "feature")
    (repo / "file.txt").write_text("x", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "feature")

    with pytest.raises(release_target.ReleaseTargetError, match="no main or release"):
        release_target.decide(_env(repo, "v1.2.0"), repo)


def test_a_tag_on_a_release_branch_is_accepted(repo: Path) -> None:
    _git(repo, "checkout", "-b", "release/1.2")
    (repo / "file.txt").write_text("x", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "on the release branch")
    _git(repo, "push", "origin", "release/1.2")
    _git(repo, "checkout", "main")
    _git(repo, "branch", "-D", "release/1.2")
    _git(repo, "fetch", "origin")
    env = {**_ENV_TAG, "GITHUB_REF_NAME": "v1.2.0", "GITHUB_SHA": _git(repo, "rev-parse", "origin/release/1.2")}

    assert release_target.decide(env, repo).repository == "pypi"


def test_a_manual_run_publishes_to_testpypi_without_checking_a_tag(repo: Path) -> None:
    _write_version(repo, "1.3.0rc1")
    env = {"GITHUB_EVENT_NAME": "workflow_dispatch", "GITHUB_REF_TYPE": "branch", "GITHUB_REF_NAME": "feature", "GITHUB_SHA": "0" * 40}

    target = release_target.decide(env, repo)

    assert target.repository == "testpypi"
    assert target.version == "1.3.0rc1"
    assert target.prerelease is True
    assert target.index_url == "https://test.pypi.org/simple/"
    assert target.upload_url == "https://test.pypi.org/legacy/"


def test_main_writes_the_outputs_to_the_github_output_file(repo: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    output = tmp_path / "github_output"
    env = {**_env(repo, "v1.2.0"), "GITHUB_OUTPUT": str(output)}

    assert release_target.main(env, repo) == 0

    lines = output.read_text(encoding="utf-8").splitlines()
    assert lines == [
        "repository=pypi",
        "version=1.2.0",
        "prerelease=false",
        "index-url=https://pypi.org/simple/",
        "upload-url=https://upload.pypi.org/legacy/",
    ]
    assert "repository=pypi" in capsys.readouterr().out


def test_main_fails_without_writing_outputs_when_the_tag_does_not_match(repo: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    output = tmp_path / "github_output"
    env = {**_env(repo, "v9.9.9"), "GITHUB_OUTPUT": str(output)}

    assert release_target.main(env, repo) == 1

    assert not output.exists()
    assert "::error::" in capsys.readouterr().out
