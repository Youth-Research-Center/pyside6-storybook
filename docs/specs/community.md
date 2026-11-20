# Contribution guide, issue forms and pull request template (#43): design

Status: draft. Milestone 7 ("Early Users"). Section numbers (§1) are referred to by the implementation plan.

## 0. Starting point and decisions

**Starting point.**
- 0.1.0rc1 is on PyPI and 0.1.0 is about to be released, so outside issues and pull requests can now arrive.
- The repository has no `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md` or `SECURITY.md`, and nothing under `.github/ISSUE_TEMPLATE/`. It has
  no pull request template. `AGENTS.md` holds the detailed conventions, and `RELEASING.md` the release steps.
- The labels exist: `area: *` (cli, docs, gallery-ui, packaging, story-api, testing, theming), `effort: xs…xl`,
  `priority: low/medium/high`, `bug`, `enhancement`, `documentation`, `question`, `good first issue`, `help wanted`, `accessibility`,
  and Dependabot's `dependencies`, `python:uv`, `github_actions`.
- Private vulnerability reporting is enabled (the API reports `enabled: true`).
- Discussions is off today. **Owner** turns it on before #43's second pull request merges (§7).
- `pyside6-storybook --version` prints `pyside6-storybook X.Y.Z`. Nothing prints the PySide6, Qt, Python or OS versions.

**Decisions made with the owner.**
- The code of conduct's contact is `mail@icm.hr`, the organisation's shared address.
- Questions go to GitHub Discussions (Q&A). There is no question issue form, and blank issues are disabled.
- The debug-info option is `--debug-info`. A `--verbose` that only works next to `--version` would be odd with argparse's
  `version` action, and the issue allows either.

**Goals (the issue's acceptance criteria).**
- The new-issue page offers the bug form and the feature form, plus links to Discussions, the docs and private security reporting.
- A new pull request is pre-filled with the template.
- A first-time contributor can go from clone to a passing test run using `CONTRIBUTING.md` alone.

**Out of scope (the issue's own list).**
- A contributor licence agreement.
- Stale-issue bots and label sync.

## 1. `pyside6-storybook --debug-info` (pull request A)

### 1.1 Behaviour
`pyside6-storybook --debug-info` prints the versions a bug report needs and exits with code 0. It does nothing else:
- it reads no `pyproject.toml`;
- it loads no story and no theme provider;
- it creates no `QApplication`, so it works without a display.

It wins over every other argument, the way `--version` does. `pyside6-storybook --debug-info some/target` therefore still only prints.
`python -m pyside6_storybook --debug-info` behaves the same.

Output: one `key: value` line per item, plain text, in this order:

```text
pyside6-storybook: 0.1.0
PySide6: 6.11.3
Qt: 6.11.3
Python: 3.11.9 (CPython)
Platform: Linux-6.8.0-1017-azure-x86_64-with-glibc2.39
pytest: 9.0.1
pytest-qt: 4.5.0
QT_QPA_PLATFORM: offscreen
```

- **`pyside6-storybook`:** `pyside6_storybook.__version__`.
- **`PySide6`:** `PySide6.__version__`, the version of the binding.
- **`Qt`:** `PySide6.QtCore.qVersion()`, the Qt runtime. It can differ from the binding with a system Qt.
- **`Python`:** `platform.python_version()` and `platform.python_implementation()`.
- **`Platform`:** `platform.platform()`. It names the OS, its release and the architecture. It never names the user, the host or
  a path.
- **`pytest` and `pytest-qt`:** `importlib.metadata.version(...)`, or `not installed`. They matter for bugs in the pytest plugin, and
  both belong to the `pytest` extra.
- **`QT_QPA_PLATFORM`:** the environment variable's value, or `not set`. Headless problems depend on it.

Not printed:
- **Paths** (the interpreter, site-packages, the working directory). They can contain the user's name, and the issue does not ask
  for them.
- **The Qt platform plugin in use.** Finding it needs a `QGuiApplication`, which `--debug-info` must not create.

### 1.2 Where the code goes
- **`cli.py`:** `_parser()` adds `--debug-info`, with `action="store_true"` and help text "print the versions of
  pyside6-storybook, PySide6, Qt, Python and the platform for a bug report, and exit".
- **`main()`:** returns early when the flag is set, before `resolve_story_sources`. It prints `debug_info()` and returns 0.
- **`_debug_info() -> str`:** a private function in `cli.py`. It returns the lines joined with `\n`. Nothing new is added to the
  public API: the CLI option is not part of `__all__`.
- **`main()`'s docstring:** says that `--debug-info` exits with 0 without loading anything.

### 1.3 Documentation
- **`docs/command-line.md`:**
  - a row in the Options table: `| --debug-info | Print the versions of pyside6-storybook, PySide6, Qt, Python and the platform, for a
    bug report, and exit. |`;
  - the exit-code `0` row also covers `--debug-info`.

  `tests/test_docs.py` already fails if the option has no row.
- **`docs/troubleshooting.md`:** a new last section, "Reporting a bug". It says:
  - run `pyside6-storybook --debug-info` and paste the output into the bug form;
  - include a minimal story that reproduces the problem, built from stock Qt widgets where possible;
  - report a vulnerability privately (link to `SECURITY.md` by its absolute GitHub URL).
- **`CHANGELOG.md`:** under `[Unreleased]` → `### Added`: "`pyside6-storybook --debug-info` prints the versions of
  pyside6-storybook, PySide6, Qt, Python and the platform for a bug report."

### 1.4 Tests
In `tests/test_cli.py`:
- **The lines.** `--debug-info` exits with 0 and prints exactly the eight keys in order. The `pyside6-storybook` value equals
  `__version__`, `PySide6` equals `PySide6.__version__`, and `Qt` equals `qVersion()`.
- **It loads nothing.** Run in a `tmp_path` whose `pyproject.toml` has an invalid `[tool.pyside6-storybook]` table, with a target that
  does not exist. The exit code is still 0. `_ensure_application`, `load_stories` and `load_theme_provider` are each replaced by a
  function that fails the test if called.
- **Values that may be missing.**
  - With `QT_QPA_PLATFORM` removed through `monkeypatch.delenv`, the line reads `QT_QPA_PLATFORM: not set`.
  - With `importlib.metadata.version` monkeypatched to raise `PackageNotFoundError` for `pytest-qt`, the line reads
    `pytest-qt: not installed`.
- **No paths.** The output does not contain `str(Path.home())` or `sys.executable`.

The existing `test_the_command_line_table_lists_every_option_of_the_parser` covers the docs row.

The smoke script (`scripts/smoke/smoke_check.py`) gets a step `check_debug_info(version, package_dir)`. It runs the installed
console script with `--debug-info` and checks two things: the first line is `pyside6-storybook: <version>`, and a `PySide6:` line
exists. `tests/test_smoke_check.py` covers the step the way it covers `check_version`.

## 2. `CONTRIBUTING.md` (pull request B)

The guide sits at the repository root, so GitHub links it from the new-issue and new-pull-request pages. It is written for a person, so
it explains and gives commands, and it links `AGENTS.md` for the full conventions instead of repeating them. Sections:

1. **Welcome:** a short paragraph. Who can help (code, docs, examples, testing on your platform, design feedback). Links to
   Discussions for questions and to the code of conduct.
2. **Before you start:**
   - a bug or a well-scoped request → an issue, using the forms;
   - a bigger change or a design question → Discussions (Ideas) first;
   - `good first issue` and `help wanted` labels as starting points;
   - comment on an issue before working on it, so two people do not do the same thing.
3. **Set up.** Prerequisites: Git, Python 3.11 or newer, and [uv](https://docs.astral.sh/uv/). Linux also needs the Qt system
   libraries; the list is the one in `tests.yml`'s "Install Qt system libraries" step, given as one `apt-get` command. Then:
   ```bash
   git clone https://github.com/Youth-Research-Center/pyside6-storybook.git
   cd pyside6-storybook
   uv sync
   uv run pyside6-storybook --examples
   ```
   Fork first if you do not have write access, and clone the fork.
4. **Run the checks:** the commands from `AGENTS.md` "Tests" and "Code quality", in the order CI runs them: `ruff check`, `ty check`,
   `QT_QPA_PLATFORM=offscreen uv run pytest -q -m "not full"`, and the full run before a pull request. Each gets one sentence on what it
   does. Windows PowerShell gets the `$env:QT_QPA_PLATFORM = "offscreen"` form. `actionlint` and the icon check apply only when you
   change workflows or icons. The docs site (`uv sync --group docs`, `uv run mkdocs serve`) applies only when you change `docs/`.
5. **How the code is laid out:** ten lines at most. `src/pyside6_storybook/` with its main sub-packages (`registry`, `controls`,
   `decorators`, `discovery`, `gui`, `themes`, `testing`, `checks`), the pytest plugin's entry module, `tests/` (one module per source
   module) and `docs/`. A link to `AGENTS.md` "Project structure" for the full map.
6. **Adding a control type.** The checklist, from the code as it is:
   1. `controls/<name>_control.py`, a frozen dataclass with `label`, `description`, `display_label` and `coerce`, using `_options.py`;
   2. export it in `controls/__init__.py`, add it to the `Control` union, and add it to `pyside6_storybook.__all__`;
   3. `gui/editors/<name>_editor.py`, a `ControlEditor` subclass, registered in `EDITORS`;
   4. use it in an example story (`tests/test_examples.py` requires every control type and option);
   5. document it in `docs/controls.md`, and add its image with `uv run python scripts/docs/render_docs_images.py`;
   6. add a `:::` line in `docs/reference.md` for the new public name;
   7. write tests (`tests/test_<name>_control.py`, `tests/test_<name>_editor.py`) and a changelog entry.
7. **Adding a built-in decorator.**
   1. `decorators/<name>.py`, reusing `_checks.py`;
   2. export it in `decorators/__init__.py`;
   3. document it in `docs/writing-stories.md` where the built-in decorators are listed;
   4. add a `:::` line in `docs/reference.md` if the name is public;
   5. write tests and a changelog entry.

   The implementation plan checks every path named in §2.6 and §2.7 against the code.
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
11. **Coding agents:** `AGENTS.md` (and `CLAUDE.md`) hold the conventions for both people and coding agents. A pull request made with an
    agent follows the same rules.

**Links.** Every link to a repository file is relative (`AGENTS.md`, `RELEASING.md`), because the guide is read on GitHub, not on PyPI.

## 3. Issue forms (pull request B)

`.github/ISSUE_TEMPLATE/` uses GitHub's issue-form YAML schema.

### 3.1 `bug_report.yml`
- `name: Bug report`; `description: Something in pyside6-storybook does not work as documented`; `labels: ["bug"]`.
- **Body.** Each field has an `id`, a label and a description. The fields are:
  1. **`markdown`:** a short intro. Search the existing issues first; questions go to Discussions; vulnerabilities go to private
     reporting (link).
  2. **`dropdown` `where`** ("Where does it happen?"): The gallery window, The command line, The pytest plugin, The checks
     (`pyside6_storybook.checks`), Writing stories (the Python API), Installation or packaging, Something else. Required.
  3. **`textarea` `what`** ("What happened?"): required.
  4. **`textarea` `story`** ("A minimal story that reproduces it"): `render: python`, required. The placeholder is a ten-line
     `@story` using stock Qt widgets. The description says to remove everything that is not needed and to replace the application's
     own widgets with stock Qt widgets where the bug still shows.
  5. **`textarea` `steps`** ("Steps to reproduce"): the command run, and what you clicked or typed. Required.
  6. **`textarea` `expected`** ("Expected behaviour"): required.
  7. **`textarea` `actual`** ("Actual behaviour"): the traceback or the error panel's text, or a screenshot. Required.
  8. **`textarea` `environment`** ("Versions"): `render: text`, required. The description reads "Paste the output of
     `pyside6-storybook --debug-info`". The placeholder is the §1.1 sample.
  9. **`textarea` `theme`** ("Theme provider and application style"): optional. Whether you use the built-in themes or your
     application's `ThemeProvider`, and any application-wide style sheet.

### 3.2 `feature_request.yml`
- `name: Feature request`; `description: Propose a new feature or a change`; `labels: ["enhancement"]`.
- **Body.** The fields match the issues this repository already writes:
  1. **`markdown`:** a bigger or open-ended idea can start in Discussions (Ideas) first.
  2. **`textarea` `summary`** ("Summary"): required.
  3. **`textarea` `why`** ("Why"): the problem it solves, and for whom. Required.
  4. **`textarea` `scope`** ("Proposed scope"): what is in, ideally as a list. Optional.
  5. **`textarea` `alternatives`** ("Alternatives considered"): optional.

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
  - name: Report a vulnerability
    url: https://github.com/Youth-Research-Center/pyside6-storybook/security/advisories/new
    about: Report a security problem privately, not in a public issue.
```
The two Discussions URLs work once **Owner** has enabled Discussions with the default categories (§7).

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

The file is the Contributor Covenant 2.1, copied verbatim from the official Markdown at
`https://www.contributor-covenant.org/version/2/1/code_of_conduct/code_of_conduct.md`.
- **Contact.** The `[INSERT CONTACT METHOD]` placeholder becomes `mail@icm.hr`.
- **Attribution.** The attribution section is kept.
- **Licence.** The Covenant is CC BY 4.0, so keeping its attribution meets the licence. No entry in `THIRD_PARTY_NOTICES.md` is
  needed: that file is generated by the icon script and lists bundled software.

Why 2.1 and not 3.0: 2.1 is the text GitHub's own community-health template offers, and the one most contributors recognise.

## 6. `SECURITY.md` (pull request B)

Sections:
1. **Supported versions.** Before 1.0 only the latest release gets fixes. A fix ships as a patch release (see `RELEASING.md`, "A patch
   release").
2. **Reporting a vulnerability.** Report it privately through GitHub's private vulnerability reporting (the URL from §3.3) or by e-mail
   to `mail@icm.hr`. Do not open a public issue. Include the affected version (`pyside6-storybook --debug-info`), what an attacker could
   do, and the steps to reproduce. Maintainers acknowledge the report, agree on a fix and a disclosure date with the reporter, and credit
   the reporter in the advisory unless asked not to. No response time is promised, because the project is run by volunteers.
3. **What is not a vulnerability: running project code is the design.**
   - Opening the gallery, `pyside6-storybook --list`, or `pytest --storybook` imports the story modules you name. It also imports the
     ones `[tool.pyside6-storybook]` in the working directory's `pyproject.toml` names, the `pyside6_storybook.stories` entry points of
     installed packages, and the `theme_provider` module. Importing a module runs its code.
   - So running the gallery or the plugin in an untrusted checkout runs that checkout's code, just like running its tests does. Treat it
     the same way.
4. **What is in scope:**
   - code running from a place the user did not name or configure;
   - the gallery making network requests (it never should; see the icon rules);
   - a problem in the published wheel or sdist, or in the release workflow (for example, an artifact that does not match the tagged
     source);
   - a dependency problem that affects pyside6-storybook users.

## 7. Repository settings and labels (Owner)

| Step | Who | When |
| --- | --- | --- |
| Enable Discussions (Settings → General → Features → Discussions), keeping the default categories (Announcements, General, Ideas, Polls, Q&A, Show and tell) | Owner | before PR B merges |
| Post and pin the welcome discussion | Owner | after PR B merges, so its links to `CONTRIBUTING.md` and the code of conduct work |
| Check that the new-issue page shows the two forms and the four links | Owner | after PR B merges |
| Apply `good first issue` to suitable issues (§8) | Claude files the issues; Owner approves the list | after PR B merges |

## 8. Good first issues

Few open issues fit today:
- #66 (log every signal) needs Qt signal introspection;
- #100 (move to Zensical) touches the whole docs toolchain;
- #42 (migrate PandaPlot) is a cross-repository task.

The plan therefore proposes three to four new small issues. Each touches one area, has a clear test, and is something the project
wants anyway. The owner approves the list before any issue is filed. Each is filed with the issue form's sections (Summary, Why, Scope,
Acceptance criteria) and labels `good first issue`, its `area:`, `effort: xs` or `effort: s`, and `priority: low`. Candidates for the
plan to check against the code:
- a "Copy story id" item in the sidebar's context menu, or a shortcut for it (gallery);
- `pyside6-storybook --list --json`, so tools can read the ids, titles and source files (cli);
- a new example story for a stock widget that no example covers yet, such as `QDial` or `QProgressBar` (examples, which teaches the
  examples' rules and `EXPECTED_STORY_IDS`);
- a docs page fix or recipe that a reader asked for (docs), if one is open by then.

## 9. Tests for pull request B

`tests/test_community_files.py`, skipped like `test_workflows.py` when the files are not in the source tree (the sdist):
- **Both issue forms.** Each parses with `yaml.safe_load` and has `name`, `description`, `labels` and `body`. Every non-markdown item
  has a unique `id` and a `label`. The forms' labels exist in the label list given in §0, kept as a constant in the test with a
  comment saying to update it when a label is renamed.
- **The bug form.** It has the fields `where`, `what`, `story`, `steps`, `expected`, `actual` and `environment`, all required. The
  `environment` description contains `pyside6-storybook --debug-info`, and that option is one of `cli._parser()`'s options, so the form
  cannot name an option that was removed.
- **`config.yml`.** `blank_issues_enabled` is false, and every contact link is an `https://` URL.
- **The pull request template.** It contains `Closes #`, `Refs #`, `CHANGELOG.md`, `ruff check`, `ty check` and `pytest`.
- **`CONTRIBUTING.md`.**
  - Every relative link resolves to a file in the repository.
  - Every source path in its "Adding a control type" and "Adding a built-in decorator" lists exists, with `<name>` patterns checked
    against one existing module.
  - Its `uv run pytest` and `uv run ruff check` lines also appear in `AGENTS.md`, so the two cannot drift.
  - The Linux package list equals the one in `tests.yml`.
- **`CODE_OF_CONDUCT.md`.** It contains `Contributor Covenant`, `version 2.1` and `mail@icm.hr`, and no `[INSERT`.
- **`SECURITY.md`.** It contains the private-reporting URL and `mail@icm.hr`, and its "not a vulnerability" section mentions
  `theme_provider` and the entry points.

## 10. Other changes in pull request B

- **`README.md`:** a short "Contributing" section before "Licence". It says contributions are welcome and links `CONTRIBUTING.md`, the
  code of conduct and Discussions by absolute URL (the README is the PyPI page; `tests/test_readme.py` checks the URLs).
- **`docs/index.md`:** one line under the existing project links, pointing to `CONTRIBUTING.md` by absolute GitHub URL.
- **`AGENTS.md`:** the "Project structure" list gains `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `SECURITY.md`, `.github/ISSUE_TEMPLATE/`
  and `.github/pull_request_template.md`. The "Pull requests" section says the template's checklist is the one to fill in. "Code
  conventions" says `CONTRIBUTING.md`'s two checklists must change with the code (the test enforces their paths).
- **`pyproject.toml`:** the sdist `include` gains `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md` and `SECURITY.md`, so a source tree is
  complete. `.github/ISSUE_TEMPLATE/` and the template stay out, like the rest of `.github/` except the workflows. Update
  `tests/test_packaging.py`'s sdist test if it lists the root files.
- **`CHANGELOG.md`:** no entry. These files do not change the library.

## 11. Pull requests

- **A: `--debug-info`.** §1. `Refs #43`. Independent of B.
- **B: the community files.** §2–§6, §9 and §10. Based on A, because the bug form and `SECURITY.md` name `--debug-info` and the test
  checks that the option exists. `Closes #43` once the good first issues are filed and labelled (§8). If they are not filed yet when B
  is ready, use `Refs #43` and close #43 by hand afterwards.
