# Contribution guide, issue forms and pull request template (#43): implementation plan

Status: draft. Implements `docs/specs/community.md` (the spec) in two pull requests. Section numbers (§1) refer to the spec.

## Order, branches and merging

| PR | Content | Branch | Base |
| --- | --- | --- | --- |
| A | `--debug-info` (spec §1) | `claude/pyside6-storybook-debug-info` | `main` |
| B | the community files (spec §2–§6, §9, §10) | `claude/pyside6-storybook-community-files` | PR A |

**Merging.**
- Both PRs ask for "Create a merge commit".
- B says "Stacked on #A; merge #A first, then retarget this PR to `main`".
- Every commit keeps the tests green.

**#43.**
- A says `Refs #43`.
- B says `Closes #43` only if the good first issues and the follow-up issue (spec §8) are filed before it is marked ready. Otherwise it
  says `Refs #43`, and #43 is closed by hand.

**Owner, before B merges:** confirm the Discussions category slugs `q-a` and `ideas` (spec §7), and approve the good-first-issue list
(§"Issues to file" below).

## Process per PR

1. **A Sonnet subagent implements the PR** in its own git worktree. It follows the spec, this plan, `AGENTS.md`, `CLAUDE.md` and
   `/tmp/claude-0/specs7/common.md`. It commits without pushing and pastes the real last lines of every check into its report.
2. **I review the diff and rerun every check.** I fix what review finds, with a regression test for each fix. The checks are:
   - `ruff`, the W291/W292/W293 check, `ty`, `actionlint` and the icon check;
   - pytest with the default font;
   - the lowest-dependencies run on Python 3.11.
3. **I push and open a draft PR.** I wait for the PR's CI to pass before reporting it ready.

**Review checklist.**
- **Privacy.** No personal name or personal e-mail address appears anywhere. The organisation address `mail@icm.hr` appears only in
  `CODE_OF_CONDUCT.md` and `SECURITY.md`.
- **Links.** Repository files link relatively from `CONTRIBUTING.md`, `SECURITY.md` and `CODE_OF_CONDUCT.md`. They use absolute URLs
  from `README.md` and `docs/`.
- **Commands.** Every command in `CONTRIBUTING.md` runs as written on a fresh clone. I run them in a new worktree.
- **Wording.** Plain, short sentences; no marketing.

## PR A: `--debug-info` (spec §1)

### Code
- **`src/pyside6_storybook/cli.py`.**
  - Imports: `platform`, and `from importlib.metadata import PackageNotFoundError, version`. `PySide6` and `qVersion` come from
    `PySide6` and `PySide6.QtCore`, at module level, since `cli.py` already imports Qt.
  - **`_QT_FOR_PYTHON_DISTRIBUTIONS`:** `("PySide6", "PySide6-Essentials", "PySide6-Addons", "shiboken6")`.
  - **`_installed_version(name: str) -> str | None`:** `version(name)`, or `None` on `PackageNotFoundError`.
  - **`_debug_info() -> str`:** builds the nine lines of spec §1.1 in order. A missing pytest or pytest-qt reads `not installed`. A
    missing `QT_QPA_PLATFORM` reads `not set`. The distributions line joins `"<name> <version>"` for each installed distribution
    with `", "`, or says `none found` when none is installed (an editable checkout can have none).
  - **`_DebugInfoAction(argparse.Action)`:**
    - `__init__(self, option_strings: Sequence[str], dest: str = argparse.SUPPRESS, default: str = argparse.SUPPRESS, help: str | None
      = None) -> None` passes `nargs=0`, like argparse's own `_VersionAction`.
    - `__call__` prints `_debug_info()` to stdout and calls `parser.exit()`.

    Keep the parameter name `help`, because argparse passes it by keyword.
  - **`_parser()`** adds `parser.add_argument("--debug-info", action=_DebugInfoAction, help=...)`, using spec §1.2's help text, after
    `--version`.
  - **`main()`'s docstring:** the `SystemExit` sentence now names `--debug-info`.
- **`scripts/smoke/smoke_check.py`.**
  - **`check_debug_info(version: str, package_dir: Path) -> None`**, "Step 3". It runs `[_console_script(), "--debug-info"]` through
    `_run` (which sets offscreen and the timeout). It raises `SmokeFailure` unless the first line is `pyside6-storybook: <version>` and
    some line starts with `PySide6: `. On success it calls `_ok("pyside6-storybook --debug-info reports <version>")`.
  - The later steps are renumbered (package data becomes Step 4, and so on).
  - `run_checks` calls it right after `check_version`.

### Docs
- **`docs/command-line.md`:**
  - the Options row, placed after `--version`;
  - the exit-code `0` row reads "Success: the gallery closed normally, `--list` found every story, or `--version` or `--debug-info`
    was printed."
- **`docs/troubleshooting.md`:** a new last section, "## Reporting a bug", as spec §1.3 describes. It uses:
  - one `bash` block for `pyside6-storybook --debug-info`;
  - one for the fallback `python -m pip list`, followed by a sentence: "look for the lines that start with `PySide6`, `shiboken6` and
    `pytest`";
  - a link to `SECURITY.md` at `https://github.com/Youth-Research-Center/pyside6-storybook/blob/main/SECURITY.md`.

  The `SECURITY.md` link breaks until PR B merges. That is fine, because B follows straight after. `tests/test_docs.py` checks only
  that the link is absolute.
- **`CHANGELOG.md`:** the `### Added` entry of spec §1.3, as the first bullet under `### Added` in `[Unreleased]`.
- **`AGENTS.md`:** the `scripts/smoke/` entry adds "the debug information" to its list of steps.

### Tests
- **`tests/test_cli.py`.** The spec §1.4 tests:
  - `test_debug_info_prints_the_versions_in_order`: uses `capsys` and `pytest.raises(SystemExit)` with `code == 0`, and checks
    `[line.split(": ", 1)[0] for line in lines]` equals the nine keys;
  - `test_debug_info_wins_over_other_arguments`: parametrized over `["--bogus", "--debug-info"]` and
    `["--debug-info", "missing/target"]`;
  - `test_debug_info_loads_nothing`: `monkeypatch.chdir(tmp_path)` with a broken `pyproject.toml`, and `cli._ensure_application`,
    `cli.resolve_story_sources`, `cli.load_stories` and `cli.load_theme_provider` replaced by functions that call `pytest.fail`;
  - `test_debug_info_reports_missing_values`: `monkeypatch.delenv("QT_QPA_PLATFORM", raising=False)` after the conftest default, and
    `cli.version` patched to raise `PackageNotFoundError` for `pytest-qt` and `PySide6-Addons` and to call the real function otherwise;
  - `test_debug_info_prints_no_paths`.
- **`tests/test_smoke_check.py`.**
  - The full-script test's `ok:` list gains `"ok: pyside6-storybook --debug-info reports {version}"` after the `__version__` line.
    Check the real ordering of `check_version`'s own lines first.
  - `test_the_debug_info_check_fails_for_another_version`: with `pytest.raises(SmokeFailure, match=...)`, calls
    `check_debug_info("0.0.0", package_dir)`. Mark it `full` only if it runs the installed console script and the module's other
    console-script tests are `full`; follow the module's existing pattern.

## PR B: the community files (spec §2–§6, §9, §10)

### New files
- **`CONTRIBUTING.md`:** spec §2, all eleven sections in that order.
  - **"Set up"** uses the exact four packages from `tests.yml` plus `libxcb-cursor0`, in one line:
    `sudo apt-get install -y libegl1 libxkbcommon0 libfontconfig1 libdbus-1-3 libxcb-cursor0`.
  - **"Run the checks"** copies the command lines from `AGENTS.md` character for character, so the drift test can compare them.
  - **"How the code is laid out"** is at most ten lines.
  - **Checklists.** Every path is written in full from the repository root (`src/pyside6_storybook/controls/<name>_control.py`),
    and every code name the test checks is in backticks next to its file.
  - **The decorator checklist's closing note** links the follow-up issue by number once it is filed (see "Issues to file"). Until
    then, it says only that `docs/versions.md` does not list the module yet.
- **`.github/ISSUE_TEMPLATE/bug_report.yml`, `feature_request.yml` and `config.yml`:** spec §3.
  - The `story` placeholder:
    ```python
    from PySide6.QtWidgets import QPushButton

    from pyside6_storybook import StoryContext, story


    @story("Bug/Reproduction")
    def reproduction(ctx: StoryContext) -> QPushButton:
        return QPushButton("Click me")
    ```
  - Check `StoryContext` and `story` against the public API before using them.
- **`.github/pull_request_template.md`:** spec §4, verbatim.
- **`CODE_OF_CONDUCT.md`:** spec §5.
  - Download the official 2.1 Markdown:
    `curl -sSfL https://www.contributor-covenant.org/version/2/1/code_of_conduct/code_of_conduct.md -o /tmp/claude-0/coc21.md`.
  - Check that it contains `[INSERT CONTACT METHOD]` and `version 2.1`.
  - Replace the placeholder with `mail@icm.hr` and change nothing else, except wrapping it in no extra formatting.
  - If the download fails, stop and report. Never write the Covenant from memory.
- **`SECURITY.md`:** spec §6, four sections with `##` headings. Every option and key it names is checked against
  `src/pyside6_storybook_pytest.py` and `discovery/sources.py`.
- **`tests/test_community_files.py`:** spec §9.
  - `_ROOT = Path(__file__).resolve().parents[1]`.
  - A module-level `pytestmark` skip when `_ROOT / ".github" / "ISSUE_TEMPLATE"` is missing.
  - `LABELS`: the §0 list, as a `frozenset`.
  - **Relative links in `CONTRIBUTING.md`.** Take every `[text](target)` whose target has no scheme and does not start with `#`. Drop
    any `#anchor` part. Require `(_ROOT / target).exists()`.
  - **Checklist paths.** Take every backticked token that starts with `src/`, `tests/`, `scripts/` or `docs/`. Replace `<name>` with
    `*`, then require `glob` to find at least one match.
  - **Checklist names.** A small table of `(name, file)` pairs, written in the test, for `EDITORS`, `_control_row`, `_CONTROLS`,
    `_CONTROL_TYPES` and `Control`. Each asserts that the name appears in the file, and that `CONTRIBUTING.md` mentions the name. The
    test does not parse the prose.
  - **Command lines shared with `AGENTS.md`.** The `uv run pytest` and `uv run ruff check` lines are found with a regex over fenced
    `bash` blocks, comparing the text before any `#` comment.
  - **Linux packages.** The `apt-get install` packages are parsed from the `tests.yml` step whose name is "Install Qt system
    libraries", and from the `CONTRIBUTING.md` line, then compared as sets (superset).

### Changed files
- **`README.md`:** "## Contributing" before "## Licence", spec §10, three sentences at most, absolute URLs:
  - `https://github.com/Youth-Research-Center/pyside6-storybook/blob/main/CONTRIBUTING.md`;
  - `.../blob/main/CODE_OF_CONDUCT.md`;
  - `https://github.com/Youth-Research-Center/pyside6-storybook/discussions`.

  Run `tests/test_readme.py`.
- **`docs/index.md`:** one bullet at the end of "Where to go next": "[Contributing](absolute URL): set up, run the checks, and open
  issues and pull requests." Run `tests/test_docs.py`, since it checks links from docs pages to files outside `docs/`.
- **`AGENTS.md`:** spec §10, three edits.

## Issues to file (after the owner approves the list)

I check each candidate against the code before proposing it, and file it with the labels in spec §8:
1. **An example story for `QDial`** (area: story-api; effort: s). It adds the story to the examples. It also updates `EXPECTED_IDS`,
   `EXPECTED_STORY_IDS`, `EXPECTED_PYTEST_SUMMARY`, the smoke test's counts and the docs screenshot if the gallery's first story
   changes. Acceptance: `tests/test_examples.py`, `tests/test_smoke_check.py` and the full suite pass.
2. **`pyside6-storybook --list --json`** (area: cli; effort: s). It prints a JSON array of `{"id", "title", "file"}` objects in story
   order, and gets an Options row, a test, and a changelog entry. Before filing, I check which fields a story has (`Story`,
   `StoryOrigin`).
3. **One docs improvement** (area: docs; effort: xs), chosen while I review `CONTRIBUTING.md`. I name it in my report.

The follow-up issue, not labelled a good first issue: "Say whether `pyside6_storybook.decorators` is public API" (area: docs;
effort: xs; priority: medium; labels `documentation`). It cites `docs/versions.md` and `docs/writing-stories.md`.

## Shared instructions for subagents

`/tmp/claude-0/specs7/common.md` is a copy of `/tmp/claude-0/specs6/common.md` with these changes:
- the paths now point at `community.md` and `community-plan.md`;
- the DejaVu run is dropped, because nothing in #43 renders text;
- a rule that the subagent never files issues or touches GitHub.
