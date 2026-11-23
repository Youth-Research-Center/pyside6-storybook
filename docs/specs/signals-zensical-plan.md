# Implementation plan: log every signal (#66) and Zensical (#100)

Status: reviewed (findings applied in the last section). Implements `docs/specs/log-signals.md` and `docs/specs/zensical.md`. Section numbers (§1) refer to those specs.

## Order, branches and merging

| PR | Issue | Branch | Base |
| --- | --- | --- | --- |
| C | #66 `log_signals` | `claude/pyside6-storybook-log-signals` | `main` |
| D | #100 Zensical | `claude/pyside6-storybook-zensical` | `main` |

- **Independent.** C and D touch different files, except `CHANGELOG.md` and `AGENTS.md`, and are not stacked. Whichever merges second
  merges `main` into its branch first. The conflicts are confined to the changelog and AGENTS.md lines. Both use "Create a merge commit".
- **Closing the issues.** C says `Closes #66`, and D says `Closes #100`.
- **If #110 (0.1.0) merges first,** the docs-site changelog entry that D edits has moved to `[0.1.0]`. D edits it there: the site was not
  in any release before 0.1.0, so the entry should describe what 0.1.0 actually ships. If 0.1.0 is already on PyPI by then, D adds a
  `### Changed` entry instead.

## Process per PR

1. A Sonnet subagent implements each PR in its own git worktree. C and D run in parallel. Each follows its spec, this plan, `AGENTS.md`,
   `CLAUDE.md` and `/tmp/claude-0/specs8/common.md`. It commits without pushing, and pastes into its report the real last lines of every
   check.
2. I review each diff and rerun every check:
   - ruff, the W291/W292/W293 check, `ty`, `actionlint` and the icon check;
   - the full pytest run;
   - the lowest-dependencies run on Python 3.11, which covers PySide6 6.8 for C;
   - the docs build with the warning check.

   I fix what review finds, with a regression test for each fix.
3. I push, open a draft PR, and wait for its CI to pass before reporting it ready. For D, the PR includes the before/after screenshots and
   the list of visible differences (zensical §0).

**Review checklist.**
- **C:**
  - no connection holds the widget;
  - no behaviour change to `log_signal`;
  - docstrings for `ActionSink`, `StoryContext.actions` and the docs wording all name the three methods;
  - the example story still meets `tests/test_examples.py`.
- **D:**
  - no `mkdocs-material` in `uv.lock`;
  - the workflow's shell step quotes nothing from `github.event`;
  - `set -o pipefail` is present;
  - the grep pattern matches real griffe output (check against the reviewer's bogus-`Args:` case).

## PR C: `StoryContext.log_signals` (#66), log-signals spec §1–§2

### Code: `src/pyside6_storybook/registry/story_context.py`
- **Imports:**
  - `logging`;
  - `from collections.abc import Callable, Iterable, Mapping`;
  - `QMetaMethod`, `QObject`, `SignalInstance` from `PySide6.QtCore`;
  - `QWidget` from `PySide6.QtWidgets`, already imported.
- **Module-level names:**
  - `_logger = logging.getLogger(__name__)`. It is a module-level helper's logger, which the spec explains.
  - `_NOISY_SIGNALS = frozenset({"updateRequest"})`.
  - `_ENUM_OWNER_MODULES = (QtCore, QtGui, QtWidgets)`, from `from PySide6 import QtCore, QtGui, QtWidgets` at module level.
    `QtWidgets` already loads `QtGui`, so this costs nothing. This replaces the spec's lazy import of `QtGui`, which a review of this
    plan may revisit.
- **`_signal_methods(obj: QObject) -> dict[str, list[QMetaMethod]]`.** It returns name → every signal entry with that name, from the base
  offset up, in declaration order, without `_NOISY_SIGNALS`. The base offset is `QWidget.staticMetaObject.methodCount()` if `obj` is a
  `QWidget`, else `QObject.staticMetaObject.methodCount()`. A test helper in `tests/test_registry.py` uses its keys to assert which names
  are connected.
- **`_resolve_parameter_types(method: QMetaMethod) -> bool`.** As in spec §1.2.
- **`StoryContext.log_signals(self, obj, *, exclude=())`.** As in spec §1.1. The order inside:
  1. return if there is no sink;
  2. check the types;
  3. collect the methods;
  4. warn about unknown excludes;
  5. resolve every remaining name's entries;
  6. warn once about the unresolved names;
  7. connect the rest.
- **Docstrings** of `ActionSink`, `StoryContext` (the `actions` attribute) and `log_signal`: they say "`log`, `log_signal` and
  `log_signals`".

### Example and docs
- **`src/pyside6_storybook/examples/inputs_stories.py`, "Inputs/Combo Box":** after the widget is configured, call
  `ctx.log_signals(widget, exclude=("highlighted", "textHighlighted"))`, and extend the docstring.
- **`docs/gallery.md`, "Logging actions":** per spec §1.3, one new Python block with its imports. A second, short block shows the item
  view case (`ctx.log_signals(view.selectionModel())`) on a `QListView` with a `QStringListModel`, so that it runs in
  `tests/test_docs.py`.
- **`CHANGELOG.md`:** the `### Added` entry under `[Unreleased]`.
- **`AGENTS.md`:** the `story_context.py` and `actions_panel.py` entries.

### Tests
- **`tests/test_registry.py`:** every test in spec §2 except the gallery one.
  - The fresh-process `QMovie` test is marked `full`. It writes its script into `tmp_path`, runs it with `sys.executable` and a 60 s
    timeout, with `QT_QPA_PLATFORM=offscreen`, and uses a path inside `tmp_path` that does not exist.
  - **Before committing:** temporarily make `_resolve_parameter_types` return `True` without touching anything, confirm the test fails,
    restore it, and say so in the report.
- **`tests/test_actions_panel.py`:** the gallery test of spec §2, following the module's existing example-story test (the
  `load_stories([EXAMPLES_MODULE])` pattern). It changes the combo box's current index through the widget's own setter.

## PR D: Zensical (#100), zensical spec §1–§4

- **`mkdocs.yml`:** `variant: classic` under `theme`, and a comment above `validation` per spec §1.
- **`pyproject.toml`:** the `docs` group of spec §2, then `uv lock`. Check `uv.lock`: `mkdocs-material` is absent; `zensical` and
  `zensical-ui` are present.
- **`.github/workflows/docs.yml`:**
  - the build step of spec §2, verbatim, with `name:`;
  - remove the top-level `env:` block that holds only `NO_MKDOCS_2_WARNING`;
  - update the header comment.

  Run `actionlint` with shellcheck. `tests/test_workflows.py` requires bash and `timeout-minutes`; both stay.
- **`.github/dependabot.yml`:** the comment on the `mkdocs` ignore. `tests/test_dependabot.py` still passes.
- **`AGENTS.md`, `CONTRIBUTING.md` and `CHANGELOG.md`:** per spec §2. Then grep `docs/`, `README.md`, `RELEASING.md`, `CONTRIBUTING.md`
  and `AGENTS.md` for `mkdocs build`, `mkdocs serve`, `Material` and `NO_MKDOCS`, and report what is left. The left-over should be only
  `mkdocs.yml` file-name mentions and the `mkdocstrings` name.
- **`tests/test_docs.py`:** the two tests of spec §3. Then try each of the four broken-tree cases (orphan page, `/absolute`,
  `[x](gallery/)`, `[x](some-dir)`), confirm the right test fails, and revert.
- **Manual checks for the report:**
  - the negative build cases of spec §4, including the bogus `Args:` entry with the CI step run locally as a bash script;
  - the Playwright screenshots of spec §4, both builds, under the `/pyside6-storybook/` prefix. Save them under
    `/tmp/claude-0/-home-user/4df5fe2d-b25a-5b0a-a479-3368b73ac402/scratchpad/zensical/`, never in the repository.

    Use the pre-installed Chromium (`/opt/pw-browsers/chromium-1243/chrome-linux64/chrome`) with `uv run --no-project --with playwright
    python script.py`. To build the MkDocs version for comparison, check out `origin/main` into a scratch worktree under `/tmp`.

## Shared instructions for subagents

`/tmp/claude-0/specs8/common.md` is a copy of `/tmp/claude-0/specs7/common.md` with these changes:
- the spec and plan paths point at `/tmp/claude-0/specs8/`;
- the docs check is the one in zensical spec §2. PR C runs it with today's MkDocs, because C does not change the docs toolchain: `uv sync
  --group docs && NO_MKDOCS_2_WARNING=1 uv run mkdocs build --strict && uv sync`.

## Corrections from the plan review (these override the text above)

**PR C**
1. **Docs blocks.**
   - `tests/test_docs.py` (`test_the_logging_example_logs_actions_and_does_nothing_without_a_sink`) unpacks exactly one Python block from
     "Logging actions", and `_section` includes deeper headings. So the `log_signals` examples go in a new sibling section,
     `## Logging every signal`, right after "Logging actions" in `docs/gallery.md`. Its text is the spec §1.3 paragraph.
   - **Its blocks are story functions**, not module-level widgets: one for a combo box with `exclude=`, and one for a `QListView` that
     logs `view.selectionModel()` and the model after `view.setModel(...)`.
   - **A new test** in `tests/test_docs.py`, like the existing logging test, loads that section's blocks, renders each story with a
     recording sink, drives it once, and asserts the recorded names. `tests/test_docs.py` is therefore a file this PR changes.
2. **Type rules, in this order** (spec §1.2 is read this way):
   1. a name without `::` needs nothing, even if it contains `<` (`QList<int>`, `QList<QPersistentModelIndex>`);
   2. a name with both `::` and `<` is unresolvable;
   3. otherwise, resolve `Owner::...`.

   Add a test: `log_signals(QStringListModel(...))` connects `dataChanged` with no warning, and `setData` records `dataChanged` with its
   arguments.
3. **Owner lookup.** Search, in this order:
   - `QtCore`, `QtGui` and `QtWidgets`;
   - then `sys.modules[cls.__module__]` for each `cls` in `type(obj).__mro__` that has a `__module__` in `sys.modules`.

   `_resolve_parameter_types(method, modules)` takes the module list.
4. **Connected-name assertions** use `obj.isSignalConnected(method)` for every `QMetaMethod` of the name. It works on 6.8 and 6.12. Use it
   in the connected-names test, the "without a sink nothing is connected" test and the "unresolvable `clicked` is not connected" test,
   not `_signal_methods` keys.
5. **The `QMovie` fresh-process test** also asserts `returncode == 0`. On 6.8, without the fix, the `TypeError` escapes `start()`.
6. **Details:**
   - keep the existing `Qt` import;
   - reflow the `ActionSink` docstring line;
   - the Combo Box story's variable is `box`;
   - `caplog.set_level(logging.WARNING, logger="pyside6_storybook.registry.story_context")`.

**PR D**
7. **Every Zensical build uses `--clean`:** CI's step, the AGENTS.md command, the subagent check and the spec §4 negative checks.
   Zensical's cache hides a docstring warning on a second build of the same tree.
8. **The shell check runs with `set -o pipefail`**, so the status of `zensical build` is not masked by `tee`. That applies to the CI step
   (spec §2) and to the subagent check.
9. **`tests/test_docs.py`.** `exclude_docs` and `not_in_nav` are YAML block strings, so split them into non-empty, stripped lines.
10. **The grep for leftover mentions** also covers `.github/`, `pyproject.toml` and `tests/`. Mentions of the `mkdocs.yml` file name are
    expected.

**Merging (both PRs)**
11. After merging `main` into a branch, inspect `git diff origin/main...HEAD -- CHANGELOG.md`. Git can put a new entry under the wrong
    version heading without a conflict. Move entries under `## [Unreleased]`, adding its `### Added` or `### Changed` heading if needed.
    If 0.1.0 is already on PyPI, revert D's edit of the released entry and add a `### Changed` entry instead. Run `uv lock` after any
    merge that touches `pyproject.toml` or `uv.lock`.
