"""Keep the community files honest: the issue forms are valid, and CONTRIBUTING.md's links, paths, names and commands match the repository."""

import glob
import re
from pathlib import Path

import pytest
import yaml

from pyside6_storybook import cli
from pyside6_storybook.discovery.constants import ENTRY_POINT_GROUP

_ROOT = Path(__file__).resolve().parents[1]
_TEMPLATES = _ROOT / ".github" / "ISSUE_TEMPLATE"

pytestmark = pytest.mark.skipif(not _TEMPLATES.is_dir(), reason=".github/ISSUE_TEMPLATE is not part of this source tree (the sdist leaves it out)")

# The labels of the repository. Update this set when a label is renamed.
LABELS = frozenset(
    {
        "area: cli",
        "area: docs",
        "area: gallery-ui",
        "area: packaging",
        "area: story-api",
        "area: testing",
        "area: theming",
        "effort: xs",
        "effort: s",
        "effort: m",
        "effort: l",
        "effort: xl",
        "priority: low",
        "priority: medium",
        "priority: high",
        "bug",
        "enhancement",
        "documentation",
        "question",
        "duplicate",
        "invalid",
        "wontfix",
        "good first issue",
        "help wanted",
        "accessibility",
        "dependencies",
        "python:uv",
        "github_actions",
    }
)

_FORMS = ("bug_report.yml", "feature_request.yml")


def _read(relative: str) -> str:
    return (_ROOT / relative).read_text(encoding="utf-8")


def _form(name: str) -> dict:
    return yaml.safe_load(_read(f".github/ISSUE_TEMPLATE/{name}"))


def _fields(form: dict) -> dict[str, dict]:
    return {element["id"]: element for element in form["body"] if element["type"] != "markdown"}


def _without_code_blocks(text: str) -> str:
    return re.sub(r"^```.*?^```", "", text, flags=re.DOTALL | re.MULTILINE)


def _bash_commands(text: str) -> set[str]:
    """The command lines of the fenced ``bash`` blocks that run pytest or ruff, without their trailing comments."""
    commands = set()
    for block in re.findall(r"^```bash\n(.*?)^```", text, flags=re.DOTALL | re.MULTILINE):
        for line in block.splitlines():
            command = re.sub(r"\s+#.*$", "", line).strip()
            if re.search(r"\buv run (pytest|ruff check)\b", command):
                commands.add(command)
    return commands


@pytest.mark.parametrize("name", _FORMS)
def test_an_issue_form_has_its_keys_and_known_labels(name: str) -> None:
    form = _form(name)

    assert {"name", "description", "labels", "body"} <= set(form)
    assert form["labels"]
    assert set(form["labels"]) <= LABELS


@pytest.mark.parametrize("name", _FORMS)
def test_every_element_of_an_issue_form_except_markdown_has_a_unique_id_and_a_label(name: str) -> None:
    body = _form(name)["body"]
    fields = [element for element in body if element["type"] != "markdown"]

    assert fields
    assert [element["id"] for element in fields] == list(dict.fromkeys(element["id"] for element in fields))
    assert all(element["attributes"]["label"] for element in fields)
    markdown = [element for element in body if element["type"] == "markdown"]
    assert all(set(element) == {"type", "attributes"} and set(element["attributes"]) == {"value"} for element in markdown)


def test_the_bug_form_requires_the_fields_a_maintainer_needs() -> None:
    fields = _fields(_form("bug_report.yml"))

    for field_id in ("where", "what", "story", "steps", "expected", "actual", "environment"):
        assert fields[field_id]["validations"]["required"] is True, field_id


def test_the_bug_form_asks_for_the_debug_info_and_the_command_exists() -> None:
    description = _fields(_form("bug_report.yml"))["environment"]["attributes"]["description"]
    options = {option for action in cli._parser()._actions for option in action.option_strings}

    assert "pyside6-storybook --debug-info" in description
    assert "--debug-info" in options


def test_the_issue_chooser_has_no_blank_issues_and_only_https_links() -> None:
    config = yaml.safe_load(_read(".github/ISSUE_TEMPLATE/config.yml"))

    assert config["blank_issues_enabled"] is False
    assert config["contact_links"]
    assert all(link["url"].startswith("https://") for link in config["contact_links"])


def test_the_pull_request_template_has_the_checklist() -> None:
    template = _read(".github/pull_request_template.md")

    for text in ("Closes #", "Refs #", "CHANGELOG.md", "ruff check", "ty check", "pytest"):
        assert text in template, text


def test_contributing_links_to_files_that_exist() -> None:
    prose = _without_code_blocks(_read("CONTRIBUTING.md"))

    targets = re.findall(r"\[[^\]]*\]\(([^)\s]+)\)", prose)
    relative = [target for target in targets if not re.match(r"[a-z][a-z0-9+.-]*:", target) and not target.startswith("#")]

    assert relative
    missing = [target for target in relative if not (_ROOT / target.split("#", 1)[0]).exists()]
    assert not missing


def test_contributing_uses_inline_links_only() -> None:
    prose = _without_code_blocks(_read("CONTRIBUTING.md"))

    assert not re.search(r"\]\[", prose)
    assert not re.search(r"^\s*\[[^\]]+\]:", prose, flags=re.MULTILINE)


def test_every_path_contributing_names_exists() -> None:
    prose = _without_code_blocks(_read("CONTRIBUTING.md"))

    paths = [token for token in re.findall(r"`([^`\n]+)`", prose) if token.startswith(("src/", "tests/", "scripts/", "docs/"))]

    assert len(paths) > 20
    missing = [path for path in paths if not glob.glob(str(_ROOT / path.replace("<name>", "*")))]
    assert not missing


@pytest.mark.parametrize(
    ("name", "file"),
    [
        ("EDITORS", "src/pyside6_storybook/gui/editors/__init__.py"),
        ("_control_row", "src/pyside6_storybook/gui/docs_panel.py"),
        ("_CONTROLS", "scripts/docs/render_docs_images.py"),
        ("_CONTROL_TYPES", "tests/test_docs_images.py"),
        ("Control", "src/pyside6_storybook/controls/__init__.py"),
    ],
)
def test_a_name_the_control_checklist_gives_is_in_the_file_it_belongs_to(name: str, file: str) -> None:
    assert re.search(rf"\b{name}\b", _read(file))
    assert f"`{name}`" in _read("CONTRIBUTING.md")


def test_the_commands_contributing_shares_with_agents_md_are_identical() -> None:
    contributing = _bash_commands(_read("CONTRIBUTING.md"))

    assert len(contributing) >= 3
    assert contributing <= _bash_commands(_read("AGENTS.md"))


def test_contributing_lists_every_system_package_the_ci_installs() -> None:
    workflow = yaml.safe_load(_read(".github/workflows/tests.yml"))
    steps = [step for job in workflow["jobs"].values() for step in job.get("steps", []) if step.get("name") == "Install Qt system libraries"]
    assert len(steps) == 1
    match = re.search(r"install -y (.+)$", steps[0]["run"].strip())
    assert match is not None
    packages = match.group(1).split()

    contributing = _read("CONTRIBUTING.md")
    assert len(packages) >= 4
    assert [package for package in packages if not re.search(rf"\b{re.escape(package)}\b", contributing)] == []


def test_the_code_of_conduct_is_the_covenant_with_the_contact_address() -> None:
    text = _read("CODE_OF_CONDUCT.md")

    assert "Contributor Covenant" in text
    assert "version 2.1" in text
    assert "mail@icm.hr" in text
    assert "[INSERT" not in text


def test_the_security_policy_gives_both_ways_to_report_and_names_what_loads_code() -> None:
    text = _read("SECURITY.md")

    assert "https://github.com/Youth-Research-Center/pyside6-storybook/security/advisories/new" in text
    assert "mail@icm.hr" in text
    for name in ("pythonpath", "theme_provider", "pyside6_storybook.stories", "--storybook-stories"):
        assert name in text, name


def test_the_options_keys_and_entry_point_group_the_security_policy_names_exist() -> None:
    text = _read("SECURITY.md")
    options = {option for action in cli._parser()._actions for option in action.option_strings}
    plugin = _read("src/pyside6_storybook_pytest.py")

    assert {"--theme-provider", "--debug-info"} <= options
    assert ENTRY_POINT_GROUP in text
    for option in ("--storybook-stories", "--storybook-theme-provider"):
        assert option in text
        assert f'"{option}"' in plugin
    for key in ("storybook_stories", "storybook_theme_provider"):
        assert key in text
        assert f'"{key}"' in plugin
    assert "--theme-provider" in text
