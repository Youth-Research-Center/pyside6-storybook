"""Keep the CI workflows safe and portable: they parse, never put untrusted input into shell source and always bound a job and its shell."""

from pathlib import Path

import pytest
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
