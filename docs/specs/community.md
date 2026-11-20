# Contribution guide, issue forms and pull request template (#43): design

Status: reviewed (findings applied). Milestone 7 ("Early Users"). Section numbers (§1) are referred to by the implementation plan.

## 0. Starting point and decisions

**Starting point.**
- 0.1.0rc1 is on PyPI and the project belongs to the `icm` PyPI organization, so outside issues and pull requests can now arrive.
  0.1.0 waits until the TestPyPI organization is approved; #43 does not depend on it.
- The repository has no `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md` or `SECURITY.md`, and nothing under `.github/ISSUE_TEMPLATE/`. It has
  no pull request template. `AGENTS.md` holds the detailed conventions, and `RELEASING.md` the release steps.
- **Labels.** These exist:
  - `area: *` (cli, docs, gallery-ui, packaging, story-api, testing, theming);
  - `effort: xs…xl` and `priority: low/medium/high`;
  - `bug`, `enhancement`, `documentation`, `question`, `duplicate`, `invalid`, `wontfix`, `good first issue`, `help wanted` and
    `accessibility`;
  - Dependabot's `dependencies`, `python:uv` and `github_actions`.
- Discussions is enabled (`has_discussions: true`), and so is private vulnerability reporting.
- `pyside6-storybook --version` prints `pyside6-storybook X.Y.Z`. Nothing prints the PySide6, Qt, Python or OS versions.
- `cli.py` imports `QtWidgets` at module level, and the package `__init__` imports `app`. So every CLI option, `--version` included,
  needs the Qt shared libraries to load. It does not need a display.

**Decisions made with the owner.**
- The code of conduct's contact is `mail@icm.hr`, the organisation's shared address.
- Questions go to GitHub Discussions (Q&A). There is no question issue form, and blank issues are disabled.
- The debug-info option is `--debug-info`.

**Goals (the issue's acceptance criteria).**
- The new-issue page offers the bug form and the feature form, with links to Discussions and the docs. GitHub adds the security link
  itself (§3.3).
- A new pull request is pre-filled with the template.
- A first-time contributor can go from clone to a passing test run using `CONTRIBUTING.md` alone.

**Out of scope (the issue's own list).**
- A contributor licence agreement.
- Stale-issue bots and label sync.

## 1. `pyside6-storybook --debug-info` (pull request A)

### 1.1 Behaviour
`pyside6-storybook --debug-info` prints the versions a bug report needs and exits with code 0. It behaves like `--version`: a
custom `argparse.Action` prints and calls `parser.exit()` while the arguments are parsed. So:
- **It wins over other arguments**, as `--version` does. `--debug-info some/target` and `--bogus --debug-info` print and exit with 0.
  An option that is missing its value is still a usage error: `--theme --debug-info` exits with 2, as `--theme --version` does.
- **It loads nothing.** It reads no `pyproject.toml`, loads no story and no theme provider, and creates no `QApplication`, so it works
  without a display. It still needs the Qt libraries to import (§0); the bug form and the troubleshooting page give a fallback for
  when the command itself fails.
- **`python -m pyside6_storybook --debug-info` behaves the same.**

Output: one `key: value` line per item, plain text, in this order:

```text
pyside6-storybook: 0.1.0
PySide6: 6.11.3
Qt: 6.11.3
Qt for Python distributions: PySide6-Essentials 6.11.3, shiboken6 6.11.3
Python: 3.11.9 (CPython)
Platform: Linux-6.8.0-1017-azure-x86_64-with-glibc2.39
pytest: 9.0.1
pytest-qt: 4.5.0
QT_QPA_PLATFORM: offscreen
```

- **`pyside6-storybook`:** `pyside6_storybook.__version__`.
- **`PySide6`:** `PySide6.__version__`, the version of the binding.
- **`Qt`:** `PySide6.QtCore.qVersion()`, the Qt runtime.
- **`Qt for Python distributions`:** each of `PySide6`, `PySide6-Essentials`, `PySide6-Addons` and `shiboken6` that is installed, with
  its version, in that order, from `importlib.metadata`. Mixed installs, such as a full `PySide6` next to a different
  `PySide6-Essentials`, are a common cause of import errors.
- **`Python`:** `platform.python_version()` and `platform.python_implementation()`.
- **`Platform`:** `platform.platform()`. It names the OS, its release and the architecture, never the user, the host or a path.
- **`pytest` and `pytest-qt`:** `importlib.metadata.version(...)`, or `not installed`. They matter for the pytest plugin.
- **`QT_QPA_PLATFORM`:** the environment variable's value, or `not set`.

Not printed:
- **Paths** (the interpreter, site-packages, the working directory). They can contain the user's name.
- **The Qt platform plugin in use.** Finding it needs a `QGuiApplication`.

### 1.2 Where the code goes
- **`cli.py`.**
  - It imports `from importlib.metadata import PackageNotFoundError, version`, so tests patch `cli.version`, the way `test_cli.py`
    patches `sources.entry_points`.
  - `_debug_info() -> str`, a private function, returns the lines joined with `\n`.
  - `_DebugInfoAction(argparse.Action)` takes `nargs=0`. Its `__call__` prints `_debug_info()` and calls `parser.exit()`.
- **`_parser()`** adds `--debug-info`. The help text is "print the versions of pyside6-storybook, PySide6, Qt, Python and the
  platform for a bug report, and exit".
- **`main()`'s docstring** says that `--help`, `--version`, `--debug-info` and usage errors exit through `SystemExit`, with codes 0, 0, 0
  and 2.
- **Public API.** Nothing new is added: per `docs/versions.md` the command line's options are public, but the option is not in
  `__all__`.

### 1.3 Documentation
- **`docs/command-line.md`:**
  - an Options row: `| --debug-info | Print the versions of pyside6-storybook, PySide6, Qt, Python and the platform, for a bug report,
    and exit. |`;
  - the exit-code `0` row also names `--debug-info`.
- **`docs/troubleshooting.md`:** a new last section, "Reporting a bug". It says:
  - run `pyside6-storybook --debug-info` and paste its output into the bug form;
  - if the command itself fails, for example with an `ImportError` about a Qt library, paste that error instead, together with the output
    of `python -m pip list` filtered to `pyside6`, `shiboken6` and `pytest`, the Python version and the OS;
  - include a minimal story that reproduces the problem, built from stock Qt widgets where possible;
  - report a vulnerability privately, with a link to `SECURITY.md` by its absolute GitHub URL.
- **`CHANGELOG.md`:** under `[Unreleased]` → `### Added`: "`pyside6-storybook --debug-info` prints the versions of
  pyside6-storybook, PySide6, Qt, Python and the platform for a bug report."
- **`AGENTS.md`:** the `scripts/smoke/` entry lists the new step.

### 1.4 Tests
In `tests/test_cli.py`:
- **The lines.** `--debug-info` raises `SystemExit(0)` and prints exactly the nine keys in order. The `pyside6-storybook` value equals
  `__version__`, `PySide6` equals `PySide6.__version__`, and `Qt` equals `qVersion()`.
- **It wins, like `--version`.** `["--bogus", "--debug-info"]` and `["--debug-info", "missing/target"]` exit with 0 and print the
  lines.
- **It loads nothing.** Run in a `tmp_path` whose `pyproject.toml` has an invalid `[tool.pyside6-storybook]` table. `cli._ensure_application`,
  `cli.resolve_story_sources`, `cli.load_stories` and `cli.load_theme_provider` are each replaced by a function that fails the test if
  called.
- **Values that may be missing.**
  - With `QT_QPA_PLATFORM` removed, the line reads `QT_QPA_PLATFORM: not set`.
  - With `cli.version` patched to raise `PackageNotFoundError` for `pytest-qt` and `PySide6-Addons`, the pytest-qt line reads
    `pytest-qt: not installed`, and the distributions line leaves out `PySide6-Addons`.
- **No paths.** The output contains neither `str(Path.home())` nor `sys.executable`.

The existing `test_the_command_line_table_lists_every_option_of_the_parser` covers the docs row.

**Smoke script.**
- `scripts/smoke/smoke_check.py` gets `check_debug_info(version, package_dir)`. It runs the installed console script with
  `--debug-info`, with `QT_QPA_PLATFORM=offscreen` like the other subprocess steps. It checks that the first line is
  `pyside6-storybook: <version>` and that a `PySide6:` line exists.
- `run_checks` calls it after `check_version`, and the "Step N" docstrings are renumbered.
- `tests/test_smoke_check.py`:
  - the full-script test's expected `ok:` lines gain the new one;
  - a new core test checks that `check_debug_info` fails for a wrong version, like `test_the_examples_check_fails_for_other_ids`.

## 2. `CONTRIBUTING.md` (pull request B)

The guide sits at the repository root, so GitHub links it from the new-issue and new-pull-request pages. It is written for a person:
it explains and gives commands, and it links `AGENTS.md` for the full conventions instead of repeating them. Links to repository files
are relative, because the guide is read on GitHub. Sections:

1. **Welcome:** who can help (code, docs, examples, testing on your platform, design feedback). Links to Discussions for questions and
   to the code of conduct.
2. **Before you start:**
   - a bug or a well-scoped request → an issue, using the forms;
   - a bigger change or a design question → Discussions (Ideas) first;
   - `good first issue` and `help wanted` as starting points;
   - comment on an issue before working on it, so two people do not do the same thing.
3. **Set up.** Prerequisites: Git, Python 3.11 or newer, and [uv](https://docs.astral.sh/uv/).
   - **Linux.** Qt needs some system libraries. On Debian or Ubuntu, install the four packages from `tests.yml`'s "Install Qt system
     libraries" step (`libegl1 libxkbcommon0 libfontconfig1 libdbus-1-3`), plus `libxcb-cursor0`, which the gallery window needs on
     X11. A desktop install usually has the rest (libGL, GLib). If Qt reports `Could not load the Qt platform plugin "xcb"`, the
     error names the missing library.
   - **Commands:**
     ```bash
     git clone https://github.com/Youth-Research-Center/pyside6-storybook.git
     cd pyside6-storybook
     uv sync
     uv run pyside6-storybook --examples
     ```
   - Fork first if you do not have write access, and clone the fork.
4. **Run the checks.** The commands from `AGENTS.md` "Tests" and "Code quality", in the order CI runs them:
   - `uv run ruff check .`, then `uv run ty check`;
   - `QT_QPA_PLATFORM=offscreen uv run pytest -q -m "not full"`, and the full `QT_QPA_PLATFORM=offscreen uv run pytest -q` before a pull
     request.

   Each gets one sentence on what it does. Windows PowerShell gets the `$env:QT_QPA_PLATFORM = "offscreen"` form. `actionlint` and the
   icon check apply only when you change workflows or icons. The docs site (`uv sync --group docs`, `uv run mkdocs serve`) applies only
   when you change `docs/`.
5. **How the code is laid out:** ten lines at most.
   - `src/pyside6_storybook/` and its sub-packages: `registry`, `controls`, `decorators`, `discovery`, `gui`, `themes`, `testing`,
     `checks`;
   - the pytest plugin's entry module;
   - `tests/` and `docs/`.

   A link to `AGENTS.md` "Project structure" gives the full map.
6. **Adding a control type.** The places that list every control:
   1. `src/pyside6_storybook/controls/<name>_control.py`, a frozen dataclass with `label`, `description`, `display_label` and
      `coerce`, using `_options.py`;
   2. `controls/__init__.py`: export it and add it to the `Control` union; add it to `pyside6_storybook.__all__` and to the set in
      `tests/test_package.py`;
   3. `src/pyside6_storybook/gui/editors/<name>_editor.py`, a `ControlEditor` subclass, registered in `EDITORS` (and in the set in
      `tests/test_editors.py`);
   4. `gui/docs_panel.py`, which needs a branch in `_control_row`, or the Docs tab raises `TypeError` for the new control;
   5. an example story that uses the control and every one of its options (`tests/test_examples.py` checks both);
   6. `docs/controls.md`: the table, the image bullet and "The options";
   7. its image: add it to `_CONTROLS` in `scripts/docs/render_docs_images.py` and to `_CONTROL_TYPES` in
      `tests/test_docs_images.py`, then run `uv run python scripts/docs/render_docs_images.py`;
   8. a `:::` line in `docs/reference.md`;
   9. tests in `tests/test_controls.py`, `tests/test_editors.py` and `tests/test_docs_panel.py`;
   10. the module lists in `AGENTS.md`, and a `CHANGELOG.md` entry.
7. **Adding a built-in decorator.**
   1. `src/pyside6_storybook/decorators/<name>.py`, reusing `_checks.py`;
   2. export it in `decorators/__init__.py`, and add it to the `__all__` test in `tests/test_decorators.py`;
   3. document it in `docs/writing-stories.md`, where the built-in decorators are shown;
   4. tests in `tests/test_decorators.py`, the module list in `AGENTS.md`, and a `CHANGELOG.md` entry.

   `pyside6_storybook.decorators` is documented but not named as public API in `docs/versions.md`. That existing gap gets its own issue
   (§8). The checklist does not work around it.
8. **Pull requests.** One concern per pull request, and the template's checklist:
   - tests for the change, and a regression test for a bug;
   - a `CHANGELOG.md` entry under `[Unreleased]` for user-facing changes;
   - docs updated, and screenshots for UI changes;
   - `Closes #N` only when the issue is fully done, otherwise `Refs #N`.

   Maintainers merge with "Create a merge commit". CI runs lint, `ty` and the core tests, and the package smoke tests when packaging
   files change.
9. **Issues, labels and milestones.**
   - What the label groups mean: `area:` is the part of the code, `effort:` the rough size, and `priority:` the order.
   - Maintainers add the labels.
   - Milestones group the issues of one goal. The issue tracker, not the roadmap, is the source of truth for scope.
10. **Releases:** maintainers only; see `RELEASING.md`.
11. **Coding agents:** `AGENTS.md` (and `CLAUDE.md`) hold the conventions for people and coding agents alike. A pull request made
    with an agent follows the same rules.

## 3. Issue forms (pull request B)

`.github/ISSUE_TEMPLATE/` uses GitHub's issue-form YAML schema. A `markdown` element has only `attributes.value`. It has no `id`,
label, description or validations. Every other element has an `id`, `attributes.label` and, where it is required,
`validations.required: true`. Dropdown options are plain text, without Markdown.

### 3.1 `bug_report.yml`
- `name: Bug report`; `description: Something in pyside6-storybook does not work as documented`; `labels: ["bug"]`.
- **Body:**
  1. **`markdown`:** search the existing issues first; questions go to Discussions; vulnerabilities go to private reporting, not an
     issue.
  2. **`dropdown` `where`** ("Where does it happen?"). Options: The gallery window; The command line; The pytest plugin; The checks
     API; Writing stories (the Python API); Installation or packaging; Something else. Required.
  3. **`textarea` `what`** ("What happened?"). Required.
  4. **`textarea` `story`** ("A minimal story that reproduces it"). `render: python`, required. The placeholder is a short `@story`
     using stock Qt widgets. The description says to remove everything not needed, and to use stock Qt widgets where the bug still
     shows.
  5. **`textarea` `steps`** ("Steps to reproduce"): the command you ran, and what you clicked or typed. Required.
  6. **`textarea` `expected`** ("Expected behaviour"). Required.
  7. **`textarea` `actual`** ("Actual behaviour"): the traceback, the error panel's text, or a screenshot. Required.
  8. **`textarea` `environment`** ("Versions"). `render: text`, required. The description says: paste the output of
     `pyside6-storybook --debug-info`; if that command fails, paste its error and the versions of Python, PySide6 and your OS. The
     placeholder is the §1.1 sample.
  9. **`textarea` `theme`** ("Theme provider and application style"): the built-in themes or your application's `ThemeProvider`,
     and any application-wide style sheet. Optional.

### 3.2 `feature_request.yml`
- `name: Feature request`; `description: Propose a new feature or a change`; `labels: ["enhancement"]`.
- **Body:**
  1. **`markdown`:** a bigger or open-ended idea can start in Discussions (Ideas).
  2. **`textarea` `summary`** ("Summary"). Required.
  3. **`textarea` `why`** ("Why"): the problem it solves, and for whom. Required.
  4. **`textarea` `scope`** ("Proposed scope"): what is in, ideally as a list. Optional.
  5. **`textarea` `alternatives`** ("Alternatives considered"). Optional.

### 3.3 `config.yml`
```yaml
blank_issues_enabled: false
contact_links:
  - name: Question or help
    url: https://github.com/Youth-Research-Center/pyside6-storybook/discussions/categories/q-a
    about: Ask in Discussions (Q&A) how to do something with pyside6-storybook.
  - name: Idea or design discussion
    url: https://github.com/Youth-Research-Center/pyside6-storybook/discussions/categories/ideas
    about: Discuss a bigger change before opening a feature request.
  - name: Documentation
    url: https://youth-research-center.github.io/pyside6-storybook/
    about: The guide, the command line and the API reference.
```
- **No security link.** GitHub adds "Report a security vulnerability" to the chooser by itself once `SECURITY.md` exists, so the
  config does not repeat it.
- **Category slugs.** `q-a` and `ideas` are the default slugs. **Owner** checks them after PR B merges (§7). If the categories were
  renamed, the plan's implementer updates the URLs.

## 4. `.github/pull_request_template.md` (pull request B)

```markdown
## What and why

<!-- What does this pull request change, and why? Link the issue: "Closes #N" only when it fully resolves it, otherwise "Refs #N". -->

## How it was tested

<!-- The tests you added or ran, and anything you checked by hand. Add screenshots for changes to the gallery. -->

## Checklist

- [ ] `uv run ruff check .` and `uv run ty check` pass
- [ ] `QT_QPA_PLATFORM=offscreen uv run pytest` passes
- [ ] New behaviour has tests, and a bug fix has a regression test that fails without the fix
- [ ] User-facing changes have an entry under `[Unreleased]` in `CHANGELOG.md`
- [ ] Docs (`docs/`, `README.md`) are updated where behaviour changed
- [ ] Screenshots are included for visible changes to the gallery
```

## 5. `CODE_OF_CONDUCT.md` (pull request B)

- **Text.** The Contributor Covenant 2.1, copied verbatim from the official Markdown at
  `https://www.contributor-covenant.org/version/2/1/code_of_conduct/code_of_conduct.md`.
- **Contact.** The `[INSERT CONTACT METHOD]` placeholder becomes `mail@icm.hr`.
- **Attribution.** The attribution section is kept.
- **Licence.** The text is CC BY 4.0, so keeping its attribution meets the licence. It is not bundled software, so it does not go in
  `THIRD_PARTY_NOTICES.md`.
- **Why 2.1 rather than 3.0.** 2.1 is the most widely adopted version and the one most contributors recognise. If the implementer
  cannot fetch the 2.1 Markdown, they stop and report; they do not write it from memory.

## 6. `SECURITY.md` (pull request B)

Sections:
1. **Supported versions.** Before 1.0 only the latest release gets fixes. A fix ships as a patch release (see `RELEASING.md`, "A patch
   release").
2. **Reporting a vulnerability.**
   - Report privately, through GitHub's private vulnerability reporting
     (`https://github.com/Youth-Research-Center/pyside6-storybook/security/advisories/new`) or by e-mail to `mail@icm.hr`. Do not open a
     public issue.
   - Include the affected version (`pyside6-storybook --debug-info`), what an attacker could do, and the steps to reproduce.
   - Maintainers acknowledge the report, agree on a fix and a disclosure date with the reporter, and credit the reporter in the advisory
     unless asked not to.
   - No response time is promised, because the project is run by volunteers.
3. **Running project code is the design.** The gallery (`pyside6-storybook`, with or without `--list`) and the pytest plugin import
   Python modules, and importing a module runs its code. The modules come from:
   - the targets you name: on the command line, in `--storybook-stories`, or in the `storybook_stories` ini key;
   - `[tool.pyside6-storybook]` in the working directory's `pyproject.toml`: its `stories`, and its `theme_provider` (also
     `--theme-provider`, `--storybook-theme-provider` and `storybook_theme_provider`);
   - the `pyside6_storybook.stories` entry points of every installed package, which are used when no target is configured;
   - the working directory and the `pythonpath` folders, which are put first on `sys.path`, so a module there shadows an installed
     module of the same name.

   Hot reload imports changed modules again. Running the gallery or the plugin in an untrusted checkout therefore runs that checkout's
   code, like running its tests does, so treat it the same way. None of this is a vulnerability.
4. **What is in scope:**
   - code running that none of the sources above would load;
   - the gallery making a network request (it never should);
   - a published wheel or sdist that does not match the tagged source, or a weakness in the release workflow;
   - a dependency problem that affects pyside6-storybook users.

## 7. Repository settings (Owner)

| Step | When |
| --- | --- |
| Check that the Discussions categories Q&A and Ideas exist with the slugs `q-a` and `ideas` (open each category; the URL shows the slug) | before PR B merges |
| Post and pin the welcome discussion | after PR B merges, so its links to `CONTRIBUTING.md` and the code of conduct work |
| Check that the new-issue page shows the two forms, the three links and GitHub's security link | after PR B merges |
| Approve the good-first-issue list (§8) before Claude files it | while PR B is in review |

## 8. Good first issues and the follow-up issue

Few open issues fit today:
- #66 (log every signal) needs Qt signal introspection;
- #100 (move to Zensical) touches the whole docs toolchain;
- #42 (migrate PandaPlot) spans repositories.

The plan proposes three new small issues. Each touches one area, has a clear test, and is something the project wants anyway. The
owner approves the list before any issue is filed. Each is filed in the feature form's shape (Summary, Why, Scope, Acceptance
criteria) with these labels: `good first issue`, its `area:`, an `effort:` (`xs` or `s`), and `priority: low`. Candidates for the plan
to check against the code:
- an example story for a stock widget that no example covers yet, such as `QDial` or `QCalendarWidget`. It touches
  `EXPECTED_IDS` in `tests/test_examples.py`, `EXPECTED_STORY_IDS` and the expected pytest summary in `scripts/smoke/smoke_check.py`,
  and the story counts in the smoke test, which teaches the examples' rules. Effort `s`.
- `pyside6-storybook --list --json`, so tools can read the ids, titles and source files. Area cli, effort `s`.
- one docs improvement that a first-time reader would notice, picked while writing `CONTRIBUTING.md`. Area docs, effort `xs`.

A "Copy story id" context menu is not on the list: the sidebar has no context menu yet, which makes it more than a first issue.

The follow-up issue, filed with PR B and not labelled a good first issue: name `pyside6_storybook.decorators` (and any other documented
sub-module) as public API in `docs/versions.md`, or say why it is not.

## 9. Tests for pull request B

`tests/test_community_files.py` is skipped as a whole when `.github/ISSUE_TEMPLATE` is not in the source tree, as in the sdist, which
leaves out `.github/` except the workflows. The sdist's contents do not change.
- **Both issue forms.**
  - Each parses with `yaml.safe_load` and has `name`, `description`, `labels` and `body`.
  - Every element except `markdown` has a unique `id` and an `attributes.label`.
  - The forms' labels are in the label list of §0, kept as a constant in the test with a comment saying to update it when a label
    is renamed.
- **The bug form.**
  - It has the fields `where`, `what`, `story`, `steps`, `expected`, `actual` and `environment`, each with
    `validations.required: true`.
  - The `environment` description contains `pyside6-storybook --debug-info`, and that option is one of `cli._parser()`'s options.
- **`config.yml`.** `blank_issues_enabled` is false, and every contact link is an `https://` URL.
- **The pull request template.** It contains `Closes #`, `Refs #`, `CHANGELOG.md`, `ruff check`, `ty check` and `pytest`.
- **`CONTRIBUTING.md`.**
  - Every relative link resolves to a file in the repository.
  - Every path in its two checklists that starts with `src/`, `tests/`, `scripts/` or `docs/` exists. For a `<name>` pattern, at
    least one file matches with `<name>` replaced by `*`.
  - Every name in its checklists written as code (`EDITORS`, `_control_row`, `_CONTROLS`, `_CONTROL_TYPES`, `Control`) appears in the
    file the checklist names.
  - Its `uv run pytest` and `uv run ruff check` command lines also appear in `AGENTS.md`.
  - Its Linux package list contains every package in `tests.yml`'s "Install Qt system libraries" step.
- **`CODE_OF_CONDUCT.md`.** It contains `Contributor Covenant`, `version 2.1` and `mail@icm.hr`, and no `[INSERT`.
- **`SECURITY.md`.** It contains the private-reporting URL and `mail@icm.hr`. Its design section names `pythonpath`,
  `theme_provider`, `pyside6_storybook.stories` and `--storybook-stories`.

## 10. Other changes in pull request B

- **`README.md`:** a short "Contributing" section before "Licence". It says contributions are welcome and links `CONTRIBUTING.md`, the
  code of conduct and Discussions by absolute URL, because PyPI shows the README.
- **`docs/index.md`:** one bullet under "Where to go next", linking `CONTRIBUTING.md` by its absolute GitHub URL.
- **`AGENTS.md`:**
  - "Project structure" gains `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `SECURITY.md`, `.github/ISSUE_TEMPLATE/` and
    `.github/pull_request_template.md`.
  - "Pull requests" says the template's checklist is the one to fill in.
  - "Code conventions" says `CONTRIBUTING.md`'s two checklists change with the code, and that `tests/test_community_files.py` checks
    their paths and names.
- **`CHANGELOG.md`:** no entry. These files do not change the library.

## 11. Pull requests

- **A: `--debug-info`.** §1. `Refs #43`. Independent of B.
- **B: the community files.** §2–§6, §9 and §10, based on A: the bug form and `SECURITY.md` name `--debug-info`, and the test checks
  that the option exists.
  - Use `Closes #43` once the good first issues and the follow-up issue are filed (§8).
  - If they are not filed when B is ready, use `Refs #43` and close #43 by hand afterwards.
