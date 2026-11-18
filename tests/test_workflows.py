"""Keep the CI workflows safe and portable: they parse, never put untrusted input into shell source and always bound a job and its shell."""

from pathlib import Path

import pytest
import release_target
import yaml

_WORKFLOWS = Path(__file__).resolve().parents[1] / ".github" / "workflows"

pytestmark = pytest.mark.skipif(not _WORKFLOWS.is_dir(), reason=".github/workflows is not part of this source tree")

_FILES = sorted(_WORKFLOWS.glob("*.yml")) + sorted(_WORKFLOWS.glob("*.yaml"))


def _load(path: Path) -> dict:
    workflow = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(workflow, dict), path.name
    return workflow


def _run_steps(workflow: dict) -> list[tuple[str, dict]]:
    return [(job_id, step) for job_id, job in workflow["jobs"].items() for step in job.get("steps", []) if "run" in step]


def test_there_are_workflows() -> None:
    assert _FILES


@pytest.mark.parametrize("path", _FILES, ids=lambda path: path.name)
def test_every_workflow_parses_and_has_a_trigger_and_jobs(path: Path) -> None:
    workflow = _load(path)

    # PyYAML reads the bare key `on` as the boolean True.
    assert True in workflow or "on" in workflow
    assert workflow["jobs"]


@pytest.mark.parametrize("path", _FILES, ids=lambda path: path.name)
def test_no_run_step_interpolates_the_event_or_the_inputs(path: Path) -> None:
    for job_id, step in _run_steps(_load(path)):
        assert "${{ github.event" not in step["run"], (job_id, step)
        assert "${{ inputs." not in step["run"], (job_id, step)


@pytest.mark.parametrize("path", _FILES, ids=lambda path: path.name)
def test_every_job_has_a_timeout_except_the_jobs_that_call_a_reusable_workflow(path: Path) -> None:
    for job_id, job in _load(path)["jobs"].items():
        if "uses" in job:
            assert "timeout-minutes" not in job, job_id
        else:
            assert isinstance(job.get("timeout-minutes"), int), job_id


@pytest.mark.parametrize("path", _FILES, ids=lambda path: path.name)
def test_every_run_step_uses_bash(path: Path) -> None:
    workflow = _load(path)
    default_shell = workflow.get("defaults", {}).get("run", {}).get("shell")
    for job_id, step in _run_steps(workflow):
        job_default = workflow["jobs"][job_id].get("defaults", {}).get("run", {}).get("shell")
        assert (step.get("shell") or job_default or default_shell) == "bash", (job_id, step)


_RELEASE = _WORKFLOWS / "release.yml"


@pytest.mark.skipif(not _RELEASE.is_file(), reason="release.yml is not part of this source tree")
class TestReleaseWorkflow:
    def test_the_token_permissions_are_minimal(self) -> None:
        workflow = _load(_RELEASE)

        assert workflow["permissions"] == {"contents": "read"}
        id_token = [job_id for job_id, job in workflow["jobs"].items() if job.get("permissions", {}).get("id-token") == "write"]
        contents_write = [job_id for job_id, job in workflow["jobs"].items() if job.get("permissions", {}).get("contents") == "write"]
        assert id_token == ["publish"]
        assert contents_write == ["github-release"]

    def test_verify_takes_the_dependencies_from_the_package_metadata_not_from_a_list_in_the_workflow(self) -> None:
        # A hand-written dependency list drifts from pyproject.toml: "PySide6-Essentials>=6.8" installed 6.12.0 on Python 3.11, which the
        # project excludes there. The TestPyPI path downloads only the release's wheel and installs it with its extra from PyPI.
        (install,) = [step["run"] for step in _load(_RELEASE)["jobs"]["verify"]["steps"] if step.get("name") == "Install the published version"]

        assert "PySide6" not in install
        assert "pytest-qt" not in install
        assert "pip download --no-cache-dir --no-deps --only-binary :all: --index-url" in install
        assert '[pytest]"' in install

    def test_verify_and_the_github_release_need_the_target(self) -> None:
        jobs = _load(_RELEASE)["jobs"]

        assert "target" in jobs["verify"]["needs"]
        assert "target" in jobs["github-release"]["needs"]

    def test_publish_uses_the_trusted_publisher_without_a_password(self) -> None:
        steps = _load(_RELEASE)["jobs"]["publish"]["steps"]

        publish = [step for step in steps if step.get("uses", "").startswith("pypa/gh-action-pypi-publish@")]
        assert len(publish) == 1
        assert "password" not in publish[0].get("with", {})
        assert "skip-existing" not in publish[0].get("with", {})

    def test_the_environment_name_comes_from_the_target_and_the_names_are_pypi_and_testpypi(self) -> None:
        environment = _load(_RELEASE)["jobs"]["publish"]["environment"]

        assert environment["name"] == "${{ needs.target.outputs.repository }}"
        assert set(release_target.INDEXES) == {"pypi", "testpypi"}

    def test_the_github_release_runs_for_tag_pushes_only(self) -> None:
        assert _load(_RELEASE)["jobs"]["github-release"]["if"] == "github.ref_type == 'tag'"
