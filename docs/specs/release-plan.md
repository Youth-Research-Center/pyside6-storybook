# Release 0.1.0 (milestone 6): implementation plan

Status: draft. Implements `docs/specs/release.md` (the spec) in five stacked pull requests, followed by the three release PRs of
spec §6.1. Section numbers (§1) refer to the spec.

## Order, branches and merging

| # | Issue | Branch | Base |
| --- | --- | --- | --- |
| 1 | #36 metadata | `claude/pyside6-storybook-packaging-metadata` | `main` |
| 2 | #37 wheel smoke test | `claude/pyside6-storybook-wheel-smoke` | PR 1 |
| 3 | #38 release workflow | `claude/pyside6-storybook-release-workflow` | PR 2 |
| 4 | #40 docs site | `claude/pyside6-storybook-docs-site` | PR 3 |
| 5 | #39 RELEASING.md and policy | `claude/pyside6-storybook-releasing` | PR 4 |

**Merging.**
- Every PR asks for "Create a merge commit" and says: "Stacked on #N; merge the stack bottom-up, retargeting each PR to `main`
  before merging it".
- PR 5 comes after the docs site because the version policy is a docs page.
- The release PRs (`0.1.0rc1`, `0.1.0`, `0.2.0.dev0`) are opened later, at their points in spec §6.2, from `main`.

**#41.** It stays open until 0.1.0 is published. The release PRs say `Refs #41`, and the last one says `Closes #41`.

## Process per PR

1. A Sonnet subagent implements the PR in its own git worktree. It follows:
   - the spec and this plan;
   - `AGENTS.md` and `CLAUDE.md`;
   - `/tmp/claude-0/specs6/common.md`.

   It commits without pushing and pastes the real last lines of `ruff check`, `ty check` and `pytest` into its report.
2. I review the diff, rerun the checks, and fix what review finds, with a regression test for each fix. The checks:
   - ruff, the W291/W292/W293 check, `ty` and the icon check;
   - pytest with the default font and with DejaVu Sans, the lowest-dependencies run on Python 3.11, and Python 3.14.
3. Workflow files are checked locally with `actionlint` (run through `uvx`/`go run` if available, otherwise by reading) and by a
   YAML parse test.
4. I push, open a draft PR, and **wait for the PR's CI to pass before reporting it ready**. A workflow added by a PR runs on that
   PR when its triggers include `pull_request`.

**Review checklist.**
- No `${{ github.event.* }}` or `${{ inputs.* }}` in shell source.
- `permissions` are minimal per job.
- Every `run:` uses `shell: bash`, and paths use forward slashes.
- Every version change is followed by `uv lock`.
- No personal name or e-mail address is added to the metadata.

## PR 1: packaging metadata (#36), spec §1

**Code.**
- `pyproject.toml`:
  - `license-files`, `authors`, `keywords`, `classifiers` and `[project.urls]` (§1.1);
  - `requires = ["hatchling>=1.27,<2"]`;
  - `[tool.hatch.build.targets.sdist]` with `include`/`exclude` (§1.2), without `mkdocs.yml` (PR 4 adds it to the list).
  - `uv lock` afterwards: the lock records the build system only indirectly, so it may not change; run it and commit any change.
- `scripts/icons/icon_bundle/`: the notices name the licence file by its installed path
  (`pyside6_storybook/resources/icons/licenses/phosphor-LICENSE.txt`). Regenerate `THIRD_PARTY_NOTICES.md`; `--check` passes.
- README: every relative link becomes an absolute GitHub URL:
  - `docs/roadmap.md`, `docs/theming.md`, `examples/themed_app`, `LICENSE`;
  - in-page anchors stay as they are.

  The rest of the README is untouched until PR 4.

**Tests.**
- `tests/test_packaging.py` (`full`): the sdist contents, the wheel contents and the wheel metadata, as §1.2 lists them,
  including "no `License ::` classifier".
- `tests/test_packaging.py` (core):
  - the Python classifiers equal the versions from `requires-python` to the newest in `full-tests.yml`;
  - the test skips when the workflow file is absent.
- `tests/test_readme.py` (core): no relative Markdown link or image (in-page `#anchors` allowed), and no GitHub alert syntax.
- `tests/test_icons.py` or the icon script's tests: the notices name the installed path.

**Docs.**
- CHANGELOG `### Added`: the PyPI metadata.
- AGENTS.md: no change.

## PR 2: wheel smoke test (#37), spec §2

**Code.**
- `scripts/smoke/smoke_test.py` (§2.2). Standard library and the installed package only. It is not imported by `src/`, and it is
  not in the wheel (its folder is outside `src/`).
  - `EXPECTED_STORY_IDS` is a frozenset of the 20 example ids.
  - Its argument parser takes `version` and `--skip-installed-check`.
  - Every subprocess call has `timeout=`.
  - Step 5 uses the gallery window's real selection path (the sidebar). Read `gui/window.py` and `tests/test_window.py` for how
    tests select stories.
  - Step 6 runs pytest in a `tempfile.TemporaryDirectory()` with an empty `pyproject.toml`, so no parent configuration applies.
- `.github/workflows/package.yml`, exactly as spec §2.1 says:
  - a `build` job output `version`;
  - the sparse checkout into `checkout/`;
  - the interpreter path resolved per OS;
  - `timeout-minutes` on every job;
  - `actions/upload-artifact@v4` and `actions/download-artifact@v4`, following the existing workflows' major versions.

**Tests.**
- `tests/test_smoke_script.py`:
  - **core:** `EXPECTED_STORY_IDS` equals the examples' ids, loaded through `load_stories` with the `stories` fixture;
  - **full:** run the script in a subprocess with `sys.executable`, the installed development version
    (`importlib.metadata.version`) and `--skip-installed-check`. It must exit 0 and print every `ok:` line. `timeout=600`.
- `tests/test_workflows.py` (core):
  - every workflow file parses as YAML. Add `pyyaml` to the dev group, unless a workflow test already exists that uses
    something else; `tomllib` cannot read YAML.
  - no `run:` block contains `${{ github.event` or `${{ inputs.`;
  - every job has `timeout-minutes`.
  - It applies to every file in `.github/workflows/`, so PRs 3 and 4 inherit it.

**Docs.**
- AGENTS.md: the structure (`scripts/smoke/`, the new workflow) and the CI section (three workflows).
- CHANGELOG: none; it is not user-facing.

## PR 3: release workflow (#38), spec §3

**Code.**
- `.github/workflows/release.yml`, exactly as spec §3.2 says.
  - The `target` job is a short inline Python script, run with `python - <<'EOF'`. It reads `GITHUB_REF_TYPE`, `GITHUB_REF_NAME`
    and `GITHUB_SHA` from the environment and writes `$GITHUB_OUTPUT`.
  - The ancestor check fetches `main` and `release/*` first.
- `scripts/release/changelog_section.py` (§3.3). Standard library only, with a `main(argv)` for tests.

**Tests.**
- `tests/test_changelog_section.py` (core): the five cases of §3.3, plus a run against the real `CHANGELOG.md` with a pre-release
  version, which must print the `[Unreleased]` body.
- `tests/test_workflows.py` additions:
  - `release.yml`'s `publish` job is the only job with `id-token: write`;
  - `github-release` is the only job with `contents: write`;
  - the top level has `contents: read`;
  - `verify` and `github-release` list `target` in `needs`;
  - `publish` uses `pypa/gh-action-pypi-publish` with no `password`.

**Docs.**
- AGENTS.md: the structure (`scripts/release/`, `release.yml`).
- `RELEASING.md` comes in PR 5. Until then the workflow file's header comment points to spec §3.4.

## PR 4: docs site (#40), spec §5

The largest PR. Commit in this order, so review can follow:

1. **Toolchain.**
   - `pyproject.toml` group `docs` (§5.1), then `uv lock`.
   - `mkdocs.yml`; add `mkdocs.yml` to the sdist include.
   - `.github/workflows/docs.yml`.
2. **Pages.** Create the pages of §5.2 by moving the README's sections (`git mv`-style: cut and paste, then fix links and
   headings).
   - `docs/theming.md` merges into `docs/themes.md` and is left as a pointer.
   - `docs/roadmap.md` gets the milestones link and absolute links.
   - New pages: `troubleshooting.md`, `versions.md` (as a stub that PR 5 fills), `reference.md` and `changelog.md`.
3. **README.** Shrink it to §1.3's front page with absolute links. Keep "Your first story" as it is, because `test_readme.py`
   still runs it.
4. **Tests.**
   - `tests/test_docs.py` (§5.3). Move the checks from `test_readme.py`, keeping each assertion.
   - Execute every Python block, with the skip marker.
   - The CLI options check against `cli._parser()`.
   - The `reference.md` coverage check.
   - The relative-link check.
   - Point `test_chrome_styling.py` at `themes.md`.
5. **Screenshots.**
   - `scripts/docs/render_docs_images.py` and the committed images: the gallery and one per control type.
   - A `full` test that runs the script into `tmp_path`.
   - Fold `render_theming_images.py` into it if that is simple; otherwise keep both.
6. **References.**
   - AGENTS.md: README mentions become the docs pages; `docs/theming.md` becomes `docs/themes.md`; the structure lists
     `mkdocs.yml`, the docs workflow and `test_docs.py`.
   - CHANGELOG: entries that say "in the README" name the docs page.
   - CHANGELOG `### Added`: the docs site.

**Checks** (in addition to the usual ones):
- `uv sync --group docs` and `uv run mkdocs build --strict` pass locally.
- Open the built `site/index.html` and two other pages with Playwright, take screenshots for the review, and check that search
  and the palette toggle work.

**Follow-up.** File the Zensical migration issue (spec §5.1), linked from the PR.

## PR 5: RELEASING.md and policy (#39), spec §4

**Code and docs.**
- `RELEASING.md` (§4.3).
- `CHANGELOG.md`: the header (links, the rule, `### Breaking`) and the link reference for `[Unreleased]` (§4.1).
- `docs/versions.md` filled (§4.2), linked from `RELEASING.md` and the README's "What's in it".
- AGENTS.md: the releasing line and the `### Breaking` heading in the changelog rule.

**Tests.**
- `tests/test_changelog.py` (core):
  - the header has the rule;
  - every `## [` heading is `[Unreleased]` or `[X.Y.Z] - YYYY-MM-DD`;
  - each section's `###` headings are among Breaking, Added, Changed, Fixed, Removed, Deprecated and Security, with Breaking
    first;
  - every version heading has a link reference.
- `tests/test_releasing.py` (core):
  - every workflow file and script that `RELEASING.md` names exists;
  - the environment names it gives equal the ones in `release.yml`.

## Release PRs (spec §6.1), later

Each is opened from `main` when spec §6.2 reaches it. Each runs `uv lock`, and is checked by:
- CI;
- the `package.yml` smoke jobs;
- the version test of `smoke_test.py`.

## After the stack

- The user runs the Full test suite on `main`.
- #36, #37, #38, #39 and #40 close with their PRs. #41 closes with the `0.2.0.dev0` PR, after the release.
- The final summary lists every manual step (spec §7), in order.
