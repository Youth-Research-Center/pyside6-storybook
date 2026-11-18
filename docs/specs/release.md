# Release 0.1.0 (milestone 6): design

Status: reviewed (findings applied). Covers #36 (metadata), #37 (wheel smoke test), #38 (release workflow), #39 (RELEASING.md and
version policy), #40 (docs site) and #41 (the release). Section numbers (§1) are referred to by the implementation plan.

## 0. Starting point and goals

**Starting point.**
- **`pyproject.toml`.** Milestones 1 to 5 are merged. It has the name, version `0.1.0.dev0`, `license = "MIT"`, the description,
  the dependency, the `pytest` extra, the console script and the `pytest11` entry point. It has no authors, keywords, classifiers or
  URLs. The sdist takes everything hatchling finds by default.
- **`uv.lock` records the project's own version**, so changing the version without `uv lock` makes `uv sync --locked` fail in CI.
- **CI tests only the source tree.**
  - `tests.yml` runs lint, `ty` and the core tests.
  - `full-tests.yml` (manual) runs every test on three systems.
  - The two `full` tests in `tests/test_packaging.py` build a wheel and look inside it, but never install it.
- **The README is the only user documentation** (878 lines).
  - `tests/test_readme.py` runs its code blocks.
  - `tests/test_chrome_styling.py` compares its list of object names with the source.
  - It links `docs/roadmap.md`, `docs/theming.md` and `examples/themed_app` with relative paths, which break on PyPI.
- **The name is free.** On 18 November 2026 `pyside6-storybook` and its normalized spellings returned 404 on pypi.org and
  test.pypi.org. A pending trusted publisher does not reserve a name; only the first upload does.
- **The changelog** already has `[Unreleased]`, in Keep a Changelog form, listing milestones 1 to 5.

**Goals.**
- `pip install pyside6-storybook` works on Windows, macOS and Linux.
- Every release is built, smoke-tested and published by a workflow with no stored credential.
- The documentation lives on a site with one page per topic.
- A maintainer can release from `RELEASING.md` alone.

Every step that needs the repository owner is marked **Owner** and collected in §7.

## 1. Packaging metadata (#36)

### 1.1 `pyproject.toml`

```toml
[project]
license = "MIT"
license-files = ["LICENSE", "THIRD_PARTY_NOTICES.md"]
authors = [{ name = "Youth Research Center" }]
keywords = ["pyside6", "qt", "storybook", "widgets", "gui", "component explorer", "pytest"]
classifiers = [
    "Development Status :: 3 - Alpha",
    "Environment :: X11 Applications :: Qt",
    "Framework :: Pytest",
    "Intended Audience :: Developers",
    "Operating System :: MacOS",
    "Operating System :: Microsoft :: Windows",
    "Operating System :: POSIX :: Linux",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3 :: Only",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
    "Programming Language :: Python :: 3.13",
    "Programming Language :: Python :: 3.14",
    "Topic :: Software Development :: Testing",
    "Topic :: Software Development :: User Interfaces",
    "Typing :: Typed",
]

[project.urls]
Homepage = "https://github.com/Youth-Research-Center/pyside6-storybook"
Documentation = "https://youth-research-center.github.io/pyside6-storybook/"
Repository = "https://github.com/Youth-Research-Center/pyside6-storybook"
Issues = "https://github.com/Youth-Research-Center/pyside6-storybook/issues"
Changelog = "https://github.com/Youth-Research-Center/pyside6-storybook/blob/main/CHANGELOG.md"

[build-system]
requires = ["hatchling>=1.27,<2"]
```

- **`license-files`.** `THIRD_PARTY_NOTICES.md` is there because the wheel ships the Phosphor icons. The icon script (which
  generates the notices) names the licence file by its path inside the installed package,
  `pyside6_storybook/resources/icons/licenses/phosphor-LICENSE.txt`, not by its source path under `src/`.
- **No `License ::` classifier.** It is redundant with the licence expression. Neither hatchling nor `twine check` rejects one,
  so a test asserts there is none.
- **Python classifiers** run from `requires-python` up to the newest version in `full-tests.yml`. A test keeps them equal, and
  skips when `.github/workflows/full-tests.yml` is absent (in an unpacked sdist).
- **The authors** are the organisation that holds the copyright in `LICENSE`. No personal name or e-mail address is added.
- **hatchling** gets an upper bound, so a future major version cannot change a release's metadata unnoticed.

### 1.2 What goes into the distributions

The wheel is unchanged: the package (with `py.typed`, the icon bundle and licence, and the examples) and
`pyside6_storybook_pytest.py`, plus `dist-info/licenses/` with `LICENSE` and `THIRD_PARTY_NOTICES.md`.

The sdist gets an explicit include list:

```toml
[tool.hatch.build.targets.sdist]
include = [
    "src/", "tests/", "docs/", "examples/", "scripts/",
    "README.md", "CHANGELOG.md", "RELEASING.md", "LICENSE", "THIRD_PARTY_NOTICES.md", "pyproject.toml", "uv.lock", "mkdocs.yml",
    ".github/workflows/",
]
exclude = ["docs/specs/", "**/__pycache__"]
```

The tests stay in the sdist for downstream packagers, together with what they read: `.github/workflows/` and `RELEASING.md`.
The rest of `.github/`, the caches, `.venv`, `dist/` and `site/` stay out. A test that needs a file the sdist lacks skips. A `full`
test unpacks the sdist and runs `pytest --collect-only -m "not full"` in it.

The `full` packaging tests grow:

**sdist contents.**
- It contains the package, the tests and `LICENSE`.
- It contains none of `.github/dependabot.yml`, `.venv/`, `site/`, `docs/specs/` or `__pycache__`.

**Wheel contents.**
- It contains `py.typed`, at least one `*_stories.py` module and both licence files under `dist-info/licenses/`.
- It contains no `tests/`, `scripts/`, `docs/` or `.github/`.

**Wheel metadata.**
- `License-Expression: MIT`.
- The five `Project-URL`s.
- Every classifier from §1.1, and no `License ::` classifier.

### 1.3 The README on PyPI

PyPI renders the README with its own CommonMark renderer:
- relative links and images break;
- GitHub-only syntax such as alerts (`> [!NOTE]`) and Mermaid does not render.

The README becomes the front page; the reference moves to the docs site (§5).

**What stays.**
- The introduction, the screenshot and the Install section.
- "Your first story": the story and the command. `tests/test_readme.py` keeps testing it, because this is the code PyPI shows.
- A "What's in it" list, one line per feature, each linking to its docs page.
- The Licence section, with its PySide6 note, and the "not affiliated" line.

**Rules.**
- Every link is absolute: the docs site, or `https://github.com/Youth-Research-Center/pyside6-storybook/blob/main/...` for
  repository files. A core test fails on a relative Markdown link or image, or a GitHub alert, in the README.
- **The install text and the status line change in the `0.1.0rc1` PR (§6.1), not before.** Until then `main` keeps the Git
  install.
  - From the rc on, the README says `pip install pyside6-storybook`, `uv add --dev pyside6-storybook` and, for development
    versions, the Git URL.
  - Until 0.1.0 is out, it also says to add `--pre` (`uv add --dev --prerelease allow`).
  - The status line says 0.1 is an early release whose API may change in minor versions before 1.0 (§4.2).

## 2. Wheel smoke test in CI (#37)

### 2.1 Workflow `package.yml`

**Triggers.**
- `push` to `main` and `pull_request`, with paths filters on:
  - `src/**`, `pyproject.toml`, `uv.lock`, `README.md`;
  - `LICENSE`, `THIRD_PARTY_NOTICES.md`;
  - `scripts/smoke/**`, `.github/workflows/package.yml`.
- `workflow_call`, so `release.yml` (§3) runs the same jobs.

**Top-level** `permissions: contents: read`. Every `run:` uses `shell: bash`, and paths use forward slashes.

**`build`** (ubuntu-latest, Python 3.11):
1. Check out and set up uv, then run `uv build`.
2. Metadata check: `uvx twine@7 check --strict dist/*`.
3. Check that there is exactly one wheel and one sdist, both named with the version from `pyproject.toml`.
4. Upload `dist/` as artifact `dist` (`if-no-files-found: error`).

**`smoke`** (matrix `ubuntu-latest`, `windows-latest`, `macos-latest` × Python 3.11 and 3.14, `fail-fast: false`, `needs: build`):
1. On Linux, install the Qt system libraries as `tests.yml` does.
2. Download `dist` into `dist/`.
3. Check out only the smoke script: `actions/checkout` with `path: checkout`, `sparse-checkout: scripts/smoke` and
   `sparse-checkout-cone-mode: false`. A checkout into the workspace root would delete `dist/`.
4. Create `venv` with `python -m venv` (pip, not uv, as a user would). Its interpreter is `venv/Scripts/python.exe` on
   Windows and `venv/bin/python` elsewhere; a step resolves it once into an output.
5. Install with `"$PY" -m pip install --no-cache-dir "$(ls dist/*.whl)[pytest]"`.
6. From a new empty directory, with `QT_QPA_PLATFORM=offscreen` and `timeout-minutes: 15`, run
   `"$PY" -I ../checkout/scripts/smoke/smoke_check.py "$VERSION"`. The version comes from the `build` job's output.

**`sdist`** (ubuntu-latest, Python 3.11, `needs: build`):
- Install the Qt libraries, then install `dist/*.tar.gz` in a fresh venv (pip builds it from source).
- Run the smoke script there too, so the sdist is proved to build a working package.

### 2.2 The checks: `scripts/smoke/smoke_check.py`

A plain script, run with `python -I`, so neither its folder nor the working directory is on `sys.path`. It takes the expected
version and exits non-zero with a clear message on the first failure. Each step prints `ok: <what>`, so the job log reads as a
checklist.

1. **Installed package.** `pyside6_storybook.__file__` is under `sysconfig.get_paths()["purelib"]`. The flag
   `--skip-installed-check` turns this off for the repository's own test of the script.
2. **Version.**
   - `pyside6_storybook.__version__` equals the argument.
   - The console script `pyside6-storybook --version` (found next to `sys.executable`) prints `pyside6-storybook <version>`.
3. **Package data.**
   - `py.typed` exists next to `__init__.py`.
   - `icon_svg` returns an SVG for every name in the bundle.
   - The Phosphor licence file exists.
4. **Examples.**
   - `pyside6-storybook --list --examples` and `python -m pyside6_storybook --list --examples` exit 0 and print the same ids on
     standard output. Standard error, which names the source and the provider, is not compared.
   - The ids are exactly the expected set the script carries. A repository test keeps that set equal to the examples.
5. **The gallery.**
   - Build the gallery window over the examples with the built-in provider, show it, and select every story in Light and in
     Dark through the window's own selection path.
   - After processing events, each story shows its widget, not the error panel.
   - Close and delete the window, and deactivate the provider.
6. **The pytest plugin.**
   - In a temporary folder, run `python -m pytest --storybook --storybook-stories pyside6_storybook.examples
     --storybook-themes Light,Dark -q -p no:cacheprovider` in a subprocess with a 300-second timeout.
   - It must exit 0 with `40 passed`. There is no `-p pyside6_storybook`, so the entry point users rely on is what loads it.

**Acceptance.** Removing `py.typed` or the examples from the wheel makes step 3 or 4 fail.

**Tests.** A `full` test (it runs the console script and renders every example) runs the script in a subprocess against the
development environment with `--skip-installed-check`. A core test checks that the script's expected ids equal the examples'
ids.

## 3. Release workflow (#38)

### 3.1 How releases flow

- **A release candidate goes to both indexes.**
  - First TestPyPI, by a manual run of the workflow, as the dry run.
  - Then PyPI, by pushing a tag `vX.Y.ZrcN`. This claims the name early and exercises the whole PyPI path (environment,
    publisher, verification, GitHub pre-release) before the final release.
  - pip ignores pre-releases unless asked (`--pre`), so an rc on PyPI does not reach users by accident.
- **A final release** goes to PyPI only, by pushing `vX.Y.Z`.

### 3.2 `release.yml`

```yaml
on:
  push:
    tags: ["v*"]
  workflow_dispatch:            # publishes the current ref to TestPyPI; no inputs
permissions:
  contents: read
concurrency:
  group: release
  cancel-in-progress: false
```

**Jobs.**

1. **`target`** (ubuntu): checks out with full history.
   - **Where to publish.** A tag push goes to `pypi`; a dispatch goes to `testpypi`.
   - **The version.** It is read from `pyproject.toml` with `tomllib`.
   - **Tag push checks.** Each one fails with both values in the message.
     - The tag must equal `v` + version.
     - The tagged commit must be on `main` or a `release/*` branch: `git merge-base --is-ancestor "$GITHUB_SHA"
       origin/<branch>` for each remote branch matching those names.
   - **Outputs.** `repository`, `version`, `prerelease` (true for `aN`, `bN`, `rcN` or `.devN`), `index-url` and `upload-url`.
   - Every value from the event reaches the shell through `env:`.
2. **`package`.** `uses: ./.github/workflows/package.yml`. Its `dist` artifact, which passed the smoke jobs, is what gets
   published; nothing is rebuilt.
3. **`publish`** (ubuntu, `needs: [target, package]`).
   - `environment: { name: ${{ needs.target.outputs.repository }}, url: <project page on that index> }`.
   - `permissions: id-token: write` on this job only.
   - Steps: download `dist`, then `pypa/gh-action-pypi-publish@release/v1` with `repository-url: ${{
     needs.target.outputs.upload-url }}`.
   - No token or `password:`. Attestations stay on (the default), and `skip-existing` is not set.
   - The step lives in `release.yml`, because PyPI matches the trusted publisher against the top-level workflow.
4. **`verify`** (matrix ubuntu, windows, macos; Python 3.11; `needs: [target, publish]`). It installs from the index, without the
   cache, and runs the smoke script.
   - Install the Qt libraries on Linux, and check out `scripts/smoke` as in §2.1.
   - Create a fresh venv. Dependencies always come from PyPI, so a squatted name on TestPyPI can never be installed:
     - **PyPI:** `pip install --no-cache-dir "pyside6-storybook[pytest]==$VERSION"`.
     - **TestPyPI:** first `pip install --no-cache-dir "PySide6-Essentials>=6.8" "pytest>=8.0" "pytest-qt>=4.4"` from PyPI, then
       `pip install --no-cache-dir --no-deps --index-url https://test.pypi.org/simple/ "pyside6-storybook==$VERSION"`.
   - The install is retried every 30 s for up to 10 minutes, for index propagation.
   - Then `python -I scripts/smoke/smoke_check.py "$VERSION"`. This is #41's acceptance (install, then the gallery opens with both
     themes) checked on the published files on three systems.
5. **`github-release`** (ubuntu, `needs: [target, verify]`, only for a tag push; `permissions: contents: write`).
   - Check out, download `dist`, and extract the notes with `python scripts/release/changelog_section.py "$VERSION" > notes.md`.
   - Then run `gh release create "$TAG" --title "$TAG" --notes-file notes.md dist/*`, adding `--prerelease` when
     `prerelease` is true.
   - `GH_TOKEN: ${{ github.token }}`, and `TAG` and `VERSION` come in through `env:`.

### 3.3 `scripts/release/changelog_section.py`

The script prints the body of `## [X.Y.Z] - YYYY-MM-DD` from `CHANGELOG.md`, without the heading, up to the next `## ` or the
link references.
- **Pre-release.** For a version such as `0.1.0rc1` it uses `## [0.1.0rc1]` if present, else `## [Unreleased]`. Candidates are
  tagged while the changelog still says Unreleased.
- **Errors.** It exits 1 with a message when the section is missing or empty.

Core unit tests cover:
- a normal section;
- the last section before the link references;
- a missing version;
- an empty section;
- the pre-release fallback.

### 3.4 One-time setup (Owner, in `RELEASING.md`)

**PyPI accounts.**
- pypi.org and test.pypi.org are separate accounts. Each needs a verified e-mail address and 2FA.
- On each index, add a pending trusted publisher:
  - project `pyside6-storybook`, owner `Youth-Research-Center`, repository `pyside6-storybook`;
  - workflow `release.yml`;
  - environment `pypi` on pypi.org and `testpypi` on test.pypi.org.

**GitHub environments** (repository settings → Environments).
- **`testpypi`:** no reviewers. Deployment branches and tags: selected, with branch `main` and branch `release/*`.
- **`pypi`:** a required reviewer (the owner). Deployment branches and tags: selected, with a rule of **Ref type: Tag** and pattern
  `v*`.

**After the first upload.**
- The project belongs to the account that published it. Add a second owner on pypi.org (or create a PyPI organization), so the
  project does not depend on one person.

**Recommended.**
- A tag ruleset on `v*` so only maintainers can create release tags.
- Required status checks: lint and core tests only. `package.yml` and `docs.yml` have paths filters, and a required check that does
  not run blocks the PR.

## 4. `RELEASING.md`, changelog and version policy (#39)

### 4.1 `CHANGELOG.md`

- **Header.** It gains the Keep a Changelog 1.1.0 and SemVer links and the rule: "every user-facing pull request adds one entry
  under `[Unreleased]`".
- **Release sections.** They are named `## [X.Y.Z] - YYYY-MM-DD`. Release candidates get no section of their own.
- **`### Breaking`.** It comes first in a section when a minor release before 1.0 breaks the public API.
- **Link references** at the bottom:
  - `[Unreleased]` compares the newest tag with `main`;
  - each version links to its GitHub Release.
- **Entries.** The existing entries stay as they are.
- **README references.** Entries that say "see … in the README" are updated to name the docs page, because the README loses those
  sections (§5).

### 4.2 Version policy (docs page "Versions and compatibility")

**Scheme.** Semantic Versioning. Before 1.0:
- a minor release (0.x.0) may break the public API, and says so under `### Breaking`;
- a patch release (0.x.y) never does.

**The public API** is:
- `__all__` of `pyside6_storybook`, and `pyside6_storybook.checks`;
- the command line's options and exit codes;
- the `[tool.pyside6-storybook]` keys and the `pyside6_storybook.stories` entry-point group;
- the pytest plugin's options, ini keys, item ids and `render_story` fixture;
- the `sbk` object names and the `sbkChrome` property.

Everything else is internal: the modules under `gui/`, `testing/` and `discovery/`, the gallery's look, and the text of messages.

**Supported versions.**
- **Python:** 3.11 up to the newest version CI tests. Support for a version is dropped in a minor release after its end of life.
- **PySide6:** 6.8 and newer.
  - CI tests 6.8.0 (in the lowest-dependencies job) and the newest release.
  - The minimum rises only in a minor release.
  - Known bad versions are excluded in `pyproject.toml`, with a comment.

**Patch releases** come from a branch `release/X.Y.x`, cut from the `vX.Y.0` tag. Fixes are made on `main` first and
cherry-picked onto it, so a patch never carries `main`'s breaking changes.

### 4.3 `RELEASING.md`

At the repository root, written for a maintainer who has never released this project. Every version change is followed by
`uv lock`; CI's `uv sync --locked` fails otherwise.

1. **One-time setup:** §3.4, step by step, with the exact values.
2. **Before a release.**
   - CI is green on `main`, and the Full test suite has passed on `main` (start it by hand).
   - The milestone's issues are closed.
3. **Release candidate.**
   - A PR sets `X.Y.Zrc1` (and runs `uv lock`); merge it.
   - Actions → Release → Run workflow on `main` publishes to TestPyPI.
   - Check the TestPyPI page: README, screenshot, licence, links, classifiers.
   - Install from TestPyPI on Windows, macOS and Linux with the two-step command of §3.2, and do the manual checks of §6.2.
   - If all is well, run `git tag -a vX.Y.Zrc1 -m "X.Y.Zrc1"` on the same commit and `git push origin vX.Y.Zrc1`, then approve the
     `pypi` deployment.
   - A problem: fix it on `main` and repeat with `rc2`.
4. **The release.**
   - A PR sets `X.Y.Z`, moves `[Unreleased]` to `## [X.Y.Z] - <date>`, updates the link references and runs `uv lock`; merge it.
   - Tag `vX.Y.Z` on the merge commit, push the tag, and approve the `pypi` deployment.
5. **After.** Check the PyPI page and the GitHub Release. Then a PR opens the next cycle: `X.(Y+1).0.dev0`, an empty
   `[Unreleased]`, and `uv lock`.
6. **A patch release.**
   - Create `release/X.Y.x` from `vX.Y.0`, if it does not exist yet.
   - Cherry-pick the fixes, set `X.Y.(Z+1)`, and add its changelog section there and on `main`.
   - Tag on the branch (the workflow accepts tags on `release/*`).
7. **A broken release.** PyPI never accepts a version number twice, even after deletion. Yank the broken version on PyPI (with
   the reason) and release the next patch; never delete it.
8. **A failed run.**
   - **Before `publish`:** fix the problem and re-run the workflow, or push a new rc tag.
   - **During `publish`:** use "Re-run failed jobs". It uploads the same `dist` artifact, and PyPI accepts a file it already has
     with the same name and content. If PyPI refuses anyway, release the next number.
   - **After `publish`:** re-run `verify` or `github-release` alone.

**`AGENTS.md`.**
- It gains "Releasing: see `RELEASING.md`; every version change is followed by `uv lock`".
- Its changelog rule gains the `### Breaking` heading.
- Its references to README sections and `docs/theming.md` are updated to the docs pages (§5).

## 5. Docs site (#40)

### 5.1 Generator

- **MkDocs with the Material theme**, as the issue suggests, and `mkdocstrings[python]` for the API reference.
- **Material reaches end of life on 5 May 2027**, as its own PyPI page says. Its successor, Zensical, reads the same `mkdocs.yml`
  and supports mkdocstrings.
  - This milestone ships on Material, which is stable today. Zensical is at 0.1.
  - The site uses only features both tools have: no Material Insiders features and no plugins beyond mkdocstrings.
  - A follow-up issue, filed with this milestone, moves the site to Zensical before May 2027.
- **Dependency group `docs`.**
  - `mkdocs>=1.6,<2` (MkDocs 2.0 pre-releases exist, and Material does not support MkDocs 2), `mkdocs-material>=9.8,<10` and
    `mkdocstrings[python]>=1.0`.
  - Locked in `uv.lock`. Never a runtime dependency, and not in `dev`.
  - The lowest-dependencies run resolves this group too, so its lower bounds must be real (it is not installed there).
- **`mkdocs.yml`** at the repository root:
  - `site_url` and `repo_url`;
  - `strict: true`, and `validation` set to `warn` for links, anchors, nav omissions and unrecognised links;
  - `exclude_docs: specs/`;
  - `not_in_nav: /theming.md`;
  - `markdown_extensions` with `pymdownx.snippets` (`base_path: ["."]`, `check_paths: true`), admonitions and tables;
  - a light and dark palette toggle, and search.
- **Links.** A docs page links another page relatively (`controls.md`). It links a file outside `docs/` with its absolute GitHub
  URL. The `mkdocs build --strict` run enforces both.

### 5.2 Pages

The README's reference sections move to pages, mostly as they are. Nothing is lost.

| Page | Content | From |
| --- | --- | --- |
| `index.md` | What it is, screenshot, install, the first story, links | README intro, Install, Your first story |
| `writing-stories.md` | `@story`, ids and groups, `StoryContext`, variants, layout, decorators | README: first story, Variants, Layout and decorators |
| `controls.md` | Every control type, its options, and a screenshot of its editor | README Controls + new screenshots |
| `finding-stories.md` | Targets, file naming, `[tool.pyside6-storybook]`, entry points, module names and `sys.path` | README "Where your stories come from" + loader rules |
| `command-line.md` | Every option, exit codes | README Command line |
| `gallery.md` | The window, keyboard, canvas, Docs tab, logging actions, hot reload | README sections of the same names |
| `themes.md` | Built-in themes, providers, tokens, styling the gallery | `docs/theming.md` + README Themes, Design tokens, Styling the gallery |
| `testing.md` | The pytest plugin, checks, snapshots, the fixture | README "Testing stories" |
| `troubleshooting.md` | Load errors, duplicate ids, running headless, fonts and subpixel text in CI, the System theme in contrast checks | new, from existing notes |
| `versions.md` | §4.2 | new (added with `RELEASING.md`) |
| `reference.md` | One `::: pyside6_storybook.<name>` block per name in `__all__`, and one per name in `pyside6_storybook.checks` | mkdocstrings |
| `roadmap.md` | The existing `docs/roadmap.md`, kept in place, with a link to the milestones at the top and its links made absolute | existing |
| `changelog.md` | `--8<-- "CHANGELOG.md"` | snippet include |

- **`docs/theming.md`** becomes a one-line pointer to `themes.md`, kept out of the nav (`not_in_nav`), so existing links keep
  working.
- **The worked example** `examples/themed_app` is linked by its GitHub URL.

### 5.3 Code and facts that cannot drift

**`tests/test_docs.py`** replaces most of `tests/test_readme.py`, with the same mechanism.
- **Every existing check moves**, keeping its assertion and changing only where it reads from:
  - the controls table;
  - the `pyproject.toml` example;
  - variants, layout, decorators and size presets;
  - logging.
- **Every Python block on every page is executed.** Each runs in a fresh namespace with the `stories` fixture, so stories register
  in an isolated registry.
  - A block that cannot run on its own is preceded by `<!-- docs-test: skip — <reason> -->`.
  - The test lists the skipped blocks with their reasons, so a skip is a visible decision.
  - The named checks above add behavioural assertions on top.
- **Command line.** The options in `command-line.md`'s table equal the options of `cli._parser()`.
- **Reference.** `reference.md` has a `:::` line for every name in `pyside6_storybook.__all__` and in
  `pyside6_storybook.checks.__all__`, and no other.
- **Links.** No page links a path outside `docs/` relatively. This mirrors the strict build, for local runs without the docs group.

**What stays elsewhere.**
- `tests/test_readme.py` keeps the first-story test, plus the PyPI rules of §1.3.
- `tests/test_chrome_styling.py` reads the object-name list from `themes.md`.

### 5.4 Screenshots

`scripts/docs/render_docs_images.py` (development only) renders offscreen with the built-in Light theme:
- the gallery: `docs/images/gallery.png`, which replaces the hand-made one. The README keeps its absolute URL to it.
- one image per control type's editor: `docs/images/controls/<type>.png`.

The images are committed. A `full` test runs the script into a temporary folder and checks that every file exists, is non-empty
and has a plausible size.

### 5.5 Workflow `docs.yml`

**Triggers.**
- `pull_request` and `push` to `main`, with paths filters on:
  - `docs/**`, `mkdocs.yml`, `src/**`;
  - `README.md`, `CHANGELOG.md`;
  - `pyproject.toml`, `uv.lock`, the workflow file.
- `workflow_dispatch`.

**`build`.**
- `uv sync --group docs --locked`, then `uv run --no-sync mkdocs build --strict`.
- On `main` only, upload the site with `actions/upload-pages-artifact`.

**`deploy`** (push to `main` only).
- `needs: build`, `environment: github-pages`.
- `permissions: pages: write, id-token: write` on this job only.
- Runs `actions/deploy-pages`.

The code-sample tests run with the core tests in `tests.yml`, which does not install the docs group.

**Owner.**
- Settings → Pages → Source: GitHub Actions, **before** the docs PR merges.
- The About box: website set to the docs URL, and topics.

## 6. The release itself (#41)

### 6.1 Release pull requests

Each is one small PR with `uv lock`, merged at its point in §6.2:

1. **`0.1.0rc1`.**
   - Version `0.1.0rc1`.
   - The README's install section and status line (§1.3).
   - The changelog stays `[Unreleased]`.
2. **`0.1.0`.**
   - Version `0.1.0`, and `## [0.1.0] - <date>` replaces `[Unreleased]`.
   - Link references.
   - The README drops the `--pre` note.
3. **`0.2.0.dev0`.** The version and a new empty `## [Unreleased]`.

### 6.2 Order of events

1. **PRs for §1 to §5 merged.** CI is green on `main`, and the Full test suite is green on `main`.
2. **Owner setup:** §3.4 and the Pages source (§5.5).
3. **The rc1 PR merged.** **Owner:** Actions → Release → Run workflow on `main` (TestPyPI). The `verify` job installs and
   smoke-tests it on three systems.
4. **Owner manual checks** on Windows, macOS and Linux:
   - install from TestPyPI with the two-step command;
   - `pyside6-storybook --examples` opens the gallery;
   - switch themes and edit a control;
   - open a story folder with `pyside6-storybook path/to/stories`;
   - run `pytest --storybook` in a small project.

   Then check the TestPyPI page. If there is a problem, fix it and release `0.1.0rc2` the same way.
5. **Owner:** tag `v0.1.0rc1` on the same commit, push it, and approve the `pypi` deployment. The workflow publishes the rc to
   PyPI, verifies it and creates a GitHub pre-release. This claims the name and proves the PyPI path.
6. **The 0.1.0 PR merged.** **Owner:** tag `v0.1.0` on its merge commit, push it, and approve the `pypi` deployment.
7. **Owner:** check the PyPI page and the GitHub Release, set the About box (docs, PyPI) and topics, and add a second PyPI owner.
8. **The `0.2.0.dev0` PR merged.**

## 7. Manual steps for the owner (summary)

| When | Where | Step |
| --- | --- | --- |
| Before the docs PR merges | Repository settings → Pages | Source: GitHub Actions |
| Before the first release | pypi.org and test.pypi.org (two accounts, each with a verified e-mail and 2FA) | Pending trusted publisher: `pyside6-storybook`, `Youth-Research-Center/pyside6-storybook`, `release.yml`, environment `pypi` / `testpypi` |
| Before the first release | Repository settings → Environments | `testpypi`: branches `main`, `release/*`. `pypi`: required reviewer (you), rule Ref type Tag `v*` |
| Before the first release (recommended) | Repository settings → Rules | Tag ruleset on `v*`; required checks: lint and core tests only |
| Before the release PRs | Actions → Full test suite | Run on `main`; it must pass |
| Release candidate | Actions → Release → Run workflow | On `main` (publishes to TestPyPI) |
| Release candidate | Windows, macOS, Linux | Install from TestPyPI (two-step command) and check by hand (§6.2 step 4); check the TestPyPI page |
| Release candidate | Terminal, then the Release run | `git tag -a v0.1.0rc1 -m "0.1.0rc1"`, `git push origin v0.1.0rc1`; approve `pypi` |
| Release | Terminal, then the Release run | `git tag -a v0.1.0 -m "0.1.0"` on the release PR's merge commit, `git push origin v0.1.0`; approve `pypi` |
| After the release | pypi.org, GitHub | Check the PyPI page and the GitHub Release; add a second PyPI owner or organization; About box: website, topics |

## 8. Out of scope

- **Automation:** automatic version bumps and changelog generation, and CI that enforces changelog entries.
- **Other channels:** conda-forge, and announcing the release.
- **Docs:** versioned docs (one version until 1.0), and the move to Zensical (a follow-up issue).
- **#42 and #43** (milestone 7).
