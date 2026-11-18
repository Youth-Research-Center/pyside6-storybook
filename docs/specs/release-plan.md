# Release 0.1.0 (milestone 6): implementation plan

Status: reviewed (findings applied). Implements `docs/specs/release.md` (the spec) in seven stacked pull requests, followed by the
three release PRs of spec §6.1. Section numbers (§1) refer to the spec.

## Order, branches and merging

| # | Issue | Branch | Base |
| --- | --- | --- | --- |
| 1 | #36 metadata | `claude/pyside6-storybook-packaging-metadata` | `main` |
| 2 | #37 wheel smoke test | `claude/pyside6-storybook-wheel-smoke` | PR 1 |
| 3 | #38 release workflow | `claude/pyside6-storybook-release-workflow` | PR 2 |
| 4a | #40 docs toolchain | `claude/pyside6-storybook-docs-toolchain` | PR 3 |
| 4b | #40 docs content | `claude/pyside6-storybook-docs-content` | PR 4a |
| 4c | #40 docs screenshots | `claude/pyside6-storybook-docs-images` | PR 4b |
| 5 | #39 RELEASING.md and policy | `claude/pyside6-storybook-releasing` | PR 4c |

**Merging.**
- Every PR asks for "Create a merge commit" and says: "Stacked on #N; merge the stack bottom-up, retargeting each PR to `main`
  before merging it".
- Every commit in a PR keeps the tests green, because merge commits bring each commit onto `main`.
- **PR 4a merges only after the owner sets Settings → Pages → Source to "GitHub Actions"**, or the first deploy on `main` fails. Its
  description says so at the top.
- The release PRs (`0.1.0rc1`, `0.1.0`, `0.2.0.dev0`) are opened later, at their points in spec §6.2, from `main`.

**#41.** It stays open until 0.1.0 is published. The release PRs say `Refs #41`, and the last one says `Closes #41`. #40 closes with
PR 4c.

## Process per PR

1. A Sonnet subagent implements the PR in its own git worktree, following:
   - the spec and this plan;
   - `AGENTS.md` and `CLAUDE.md`;
   - `/tmp/claude-0/specs6/common.md`.

   It commits without pushing and pastes the real last lines of `ruff check`, `ty check`, `actionlint` and `pytest` into its report.
2. I review the diff, rerun every check, and fix what review finds, with a regression test for each fix. The checks are:
   - ruff, the W291/W292/W293 check, `ty`, `actionlint` and the icon check;
   - pytest with the default font and with DejaVu Sans;
   - the lowest-dependencies run on Python 3.11, and Python 3.14.
3. I push, open a draft PR, and **wait for the PR's CI to pass before reporting it ready**.

**Review checklist.**
- **Workflow safety.** No `${{ github.event.* }}` or `${{ inputs.* }}` in shell source, and `permissions` are minimal per job.
- **Portability.** Every `run:` uses `shell: bash`, and paths use forward slashes.
- **Versions.** Every version change is followed by `uv lock`. After a change to entry points, run
  `uv sync --reinstall-package pyside6-storybook`, because an editable install keeps the old `entry_points.txt`.
- **Privacy.** No personal name or e-mail address goes into the metadata.

## PR 1: packaging metadata (#36), spec §1

**Code.**
- `pyproject.toml`:
  - `license-files`, `authors`, `keywords`, `classifiers` and `[project.urls]` (§1.1);
  - `requires = ["hatchling>=1.27,<2"]`;
  - the sdist `include`/`exclude` (§1.2). This PR's list leaves out `mkdocs.yml` and `RELEASING.md`; PRs 4a and 5 add them when
    the files exist.
  - `pyyaml` in the dev group. `uv lock` afterwards.
- `scripts/icons/icon_bundle/`: the notices name the licence file by its installed path
  (`pyside6_storybook/resources/icons/licenses/phosphor-LICENSE.txt`). Regenerate `THIRD_PARTY_NOTICES.md`.
- `tests.yml` `lint` job: run `uvx --from actionlint-py actionlint` (pinned version) on every workflow.
- README: every relative link becomes an absolute GitHub URL:
  - `docs/roadmap.md` and `docs/theming.md`;
  - `examples/themed_app` and `src/pyside6_storybook/examples`;
  - `LICENSE` and `THIRD_PARTY_NOTICES.md`.

  Nothing else in the README changes until PR 4b.

**Tests.**
- `tests/test_packaging.py` (`full`):
  - the sdist contents, the wheel contents and the wheel metadata, as §1.2 lists them, including "no `License ::` classifier";
  - an unpacked-sdist run of `pytest --collect-only -m "not full"`, with `timeout=`.
- `tests/test_packaging.py` (core):
  - the Python classifiers equal the versions from `requires-python` to the newest in `full-tests.yml`'s matrix, read with PyYAML;
  - the test skips when the file is absent.
- `tests/test_workflows.py` (core). The module skips when `.github/workflows` is absent.
  - Every workflow parses. PyYAML reads the `on:` key as `True`.
  - No `run:` contains `${{ github.event` or `${{ inputs.`.
  - Every job has `timeout-minutes`, except jobs with `uses:`, which may not have one.
  - Every `run:` step uses bash, either as the workflow default or on the step.
- `tests/test_readme.py` (core):
  - no relative Markdown link or image (`](#…)` anchors are allowed; there are none today);
  - no GitHub alert syntax.
- The icon script's tests: the notices name the installed path.

**Docs.**
- CHANGELOG `### Added`: the PyPI metadata.
- AGENTS.md:
  - README rule: absolute links only, no GitHub-only syntax, because PyPI renders it;
  - the actionlint line in "Code quality";
  - `tests/test_workflows.py` in the structure.

## PR 2: wheel smoke test (#37), spec §2

**Code.**
- `scripts/smoke/smoke_check.py` (§2.2). The name does not match pytest's `test_*.py`/`*_test.py`. The script uses the standard
  library and the installed package only.
  - Each step is a function that takes the package directory (or the expected ids), so tests can point it at a copy.
  - `EXPECTED_STORY_IDS` is a frozenset of the 20 example ids.
  - Argument parser: `version` and `--skip-installed-check`.
  - Every subprocess call has `timeout=`.
  - Step 5:
    - load the examples with `load_stories(["pyside6_storybook.examples"])` into a fresh registry;
    - build `GalleryWindow(registry, provider)` (`gui/window.py`);
    - for each theme, call `set_theme(name)`, then `select_story(id)` for every id;
    - after `processEvents()`, assert `current_preview_widget() is not None`, because `None` means the error panel is shown.
  - Step 6 runs pytest in a `tempfile.TemporaryDirectory()` holding an empty `pyproject.toml`.
- `.github/workflows/package.yml`, as spec §2.1 says.
  - Use the current major versions of `actions/upload-artifact` and `actions/download-artifact`. Check their latest releases with
    `curl -s https://api.github.com/repos/actions/upload-artifact/releases/latest`.
- `pyproject.toml`: add `scripts/smoke` and `scripts/release` to `[tool.pytest.ini_options] pythonpath` and to
  `[tool.ty.environment] extra-paths`.

**Tests.**
- `tests/test_smoke_check.py`.
  - **core:**
    - `EXPECTED_STORY_IDS` equals the examples' ids, loaded with the `stories` fixture;
    - with a copy of the installed package in `tmp_path` without `py.typed`, step 3 fails;
    - with the examples package removed from the copy, step 4's id check fails.
  - **full:** run the script in a subprocess with `sys.executable`, the development version (`importlib.metadata.version`) and
    `--skip-installed-check`. It must exit 0 and print every `ok:` line. Use `@pytest.mark.timeout(600)` and `timeout=600`.

**Docs.**
- AGENTS.md:
  - the structure: `scripts/smoke/` and the new workflow;
  - the CI section: the package workflow, what it checks, and that it runs on pull requests that touch packaging.
- CHANGELOG: no entry, because nothing changes for users.

## PR 3: release workflow (#38), spec §3

**Code.**
- `.github/workflows/release.yml`, as spec §3.2 says.
  - The `target` job uses `actions/checkout` with `fetch-depth: 0`, which already fetches every branch and tag.
  - It lists branches with `git for-each-ref --format='%(refname)' refs/remotes/origin/main 'refs/remotes/origin/release/*'`,
    then checks `git merge-base --is-ancestor`.
  - It uses `actions/setup-python` (3.11), then `python - <<'EOF'` reading `GITHUB_REF_TYPE`, `GITHUB_REF_NAME` and `GITHUB_SHA`
    from the environment and writing `$GITHUB_OUTPUT`.
  - The `package` job (`uses:`) has no `timeout-minutes`.
- `scripts/release/changelog_section.py` (§3.3). Standard library only, with a `main(argv)` for tests.

**Tests.**
- `tests/test_changelog_section.py` (core):
  - the five cases of §3.3;
  - a run against the real `CHANGELOG.md` with a pre-release version, which prints the `[Unreleased]` body.
- `tests/test_workflows.py` additions, scoped to `release.yml`:
  - `publish` is its only job with `id-token: write`, and `github-release` its only job with `contents: write`;
  - the top level has `contents: read`;
  - `verify` and `github-release` list `target` in `needs`;
  - `publish` uses `pypa/gh-action-pypi-publish` with no `password`;
  - the environment names are `pypi` and `testpypi`.

**Docs.**
- AGENTS.md: the structure (`scripts/release/`, `release.yml`).
- Until `RELEASING.md` exists (PR 5), the workflow's header comment points to spec §3.4.

## PR 4a: docs toolchain (#40), spec §5.1, §5.5

**Code.**
- `pyproject.toml`: the `docs` group (§5.1), then `uv lock`. Add `mkdocs.yml` to the sdist include.
- `mkdocs.yml` (§5.1), with the nav listing only the pages that exist after this PR:
  - `index.md`: a short version of the README intro, which PR 4b completes;
  - `reference.md`: one `:::` per name;
  - `changelog.md`;
  - `roadmap.md`: the existing file, with the milestones link added and its links made absolute.
- `.github/workflows/docs.yml` (§5.5), with `NO_MKDOCS_2_WARNING=1` set to quiet Material's banner.
- `.github/dependabot.yml`: on the uv entry, ignore `mkdocs` versions `>=2`.

**Tests** (core).
- `tests/test_docs.py`:
  - `reference.md`'s `:::` lines equal the names in `pyside6_storybook.__all__` and `pyside6_storybook.checks.__all__`;
  - no page in the nav links a path outside `docs/` relatively.
- `tests/test_workflows.py`: `docs.yml`'s `deploy` is its only job with `pages: write` or `id-token: write`.

**Checks.**
- `uv sync --group docs`, then `uv run mkdocs build --strict`.

**Docs.**
- AGENTS.md:
  - "Docs site": `uv sync --group docs`, `uv run mkdocs serve`, `uv run mkdocs build --strict`;
  - the rule "a new name in `__all__` needs a `:::` line in `docs/reference.md`".
- CHANGELOG `### Added`: the docs site.

**Follow-up.** File the Zensical migration issue (spec §5.1) and link it.

## PR 4b: docs content (#40), spec §5.2, §5.3, §1.3

One atomic change, so no commit has a page and its test out of step.

**Pages.**
- **Moved from the README:** the pages of §5.2.
  - `docs/theming.md` merges into `docs/themes.md` and is left as a pointer, which is in `not_in_nav`.
  - `command-line.md` turns the README's usage block into a table, one row per option, and lists the exit codes.
- **New:** `troubleshooting.md`.
- **Every Python block is complete.** Add the imports a block needs (`IntControl`, `story`, the widget class it uses).
  - A block that cannot run alone, such as `raise SystemExit(run(...))`, which opens the gallery, or a fragment using `ctx`, gets
    `<!-- docs-test: skip — <reason> -->`.

**README.** It shrinks to the front page of §1.3, with absolute links. "Your first story" stays as it is.

**Tests.**
- `tests/test_docs.py` gains:
  - **The checks moved from `test_readme.py`**, each with its assertion. Section lookups use the new heading levels, and
    `_section()` ends a section at the next heading of the same or a higher level or at the end of the file.
  - **Execution of every Python block** on the pages in the nav (not `specs/`), each in a fresh namespace with the `stories` fixture.
    A test lists the skipped blocks and their reasons.
  - **The CLI table:** the documented options equal
    `{o for a in cli._parser()._actions for o in a.option_strings} - {"-h", "--help"}`. The exit codes on the page are 0, 1 and 2,
    with a short assertion.
- `tests/test_chrome_styling.py` reads `docs/themes.md`. Its section regex becomes `(?=^## |\Z)`.
- `tests/test_readme.py` keeps the first story and the PyPI rules.

**Docs.**
- AGENTS.md:
  - the README mentions become the docs pages, and `docs/theming.md` becomes `docs/themes.md`;
  - the rule "a new CLI option needs a row in `docs/command-line.md`";
  - the `mark_chrome` rule names `docs/themes.md`.
- CHANGELOG: entries that say "in the README" name the docs page.

**Checks.**
- `mkdocs build --strict` passes.
- Open `site/index.html`, `controls.md` and `themes.md` with Playwright for the review screenshots.

## PR 4c: docs screenshots (#40), spec §5.4

**Code.**
- `scripts/docs/render_docs_images.py`, and the committed images:
  - the gallery, replacing `docs/images/gallery.png`;
  - `docs/images/controls/<type>.png`, one per control type.
- `controls.md` shows each image.
- Fold `render_theming_images.py` into the script if that is simple; otherwise keep both.

**Tests.** A `full` test runs the script into `tmp_path` and checks that every file exists, is non-empty and has a plausible size.

## PR 5: RELEASING.md and policy (#39), spec §4

**Code and docs.**
- `RELEASING.md` (§4.3); add it to the sdist include.
- `docs/versions.md` (§4.2), added to the nav and linked from `RELEASING.md` and the README.
- `CHANGELOG.md`:
  - the header: the links, the rule and `### Breaking`;
  - `[Unreleased]: https://github.com/Youth-Research-Center/pyside6-storybook/commits/main` until a tag exists.
- AGENTS.md:
  - the releasing line;
  - `### Breaking` in the changelog rule.
- `release.yml`'s header comment points to `RELEASING.md`.

**Tests** (core).
- `tests/test_changelog.py`:
  - the header has the rule;
  - every `## [` heading is `[Unreleased]` or `[X.Y.Z] - YYYY-MM-DD`;
  - each section's `###` headings are among Breaking, Added, Changed, Fixed, Removed, Deprecated and Security, with Breaking
    first;
  - every version heading has a link reference.
- `tests/test_releasing.py` (skips when `RELEASING.md` is absent):
  - every workflow file and script that `RELEASING.md` names exists;
  - the environment names it gives equal those in `release.yml`.

## Release PRs (spec §6.1), later

Each is opened from `main` when spec §6.2 reaches it. Each runs `uv lock`, and is checked by CI, the `package.yml` smoke jobs and
the smoke script's version step.

## After the stack

- The user runs the Full test suite on `main`.
- #36 to #40 close with their PRs. #41 closes with the `0.2.0.dev0` PR, after the release.
- The final summary lists every manual step of spec §7, in order.
