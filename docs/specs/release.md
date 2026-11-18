# Release 0.1.0 (milestone 6): design

Status: draft. Covers #36 (metadata), #37 (wheel smoke test), #38 (release workflow), #39 (RELEASING.md and version policy),
#40 (docs site) and #41 (the release). Section numbers (§1) are referred to by the implementation plan.

## 0. Starting point and goals

- **The project is complete enough to release.** Milestones 1 to 5 are merged. `pyproject.toml` has the name, version
  `0.1.0.dev0`, `license = "MIT"`, the description, the dependency, the `pytest` extra, the console script and the `pytest11`
  entry point.
  - It has no authors, keywords, classifiers or URLs.
  - The sdist takes everything hatchling finds by default.
- **CI tests only the source tree.**
  - `tests.yml` runs lint, `ty` and the core tests.
  - `full-tests.yml` (manual) runs every test on three systems.
  - The two `full` tests in `tests/test_packaging.py` build a wheel and look inside it, but never install it.
- **The README is the only user documentation.** It has 878 lines covering everything from install to styling the gallery.
  - `tests/test_readme.py` runs its code blocks.
  - `tests/test_chrome_styling.py` compares its list of object names with the source.
  - It links `docs/roadmap.md`, `docs/theming.md` and `examples/themed_app` with relative paths, which break on PyPI. The
    screenshot is already an absolute URL.
- **The name is free.** On 18 November 2026 `pyside6-storybook` (and its normalized spellings) returned 404 on both pypi.org
  and test.pypi.org.
- **The `[Unreleased]` changelog section already exists.** It is in Keep a Changelog form and lists milestones 1 to 5.

Goals: `pip install pyside6-storybook` works on Windows, macOS and Linux, and every release is built, smoke-tested and published
by a workflow with no stored credential. The documentation lives on a site with one page per topic, and a maintainer can release
from `RELEASING.md` alone.

Every step that needs the repository owner (PyPI accounts, repository settings, approving a deployment, pushing a tag) is marked
**Owner** and collected in §7.

## 1. Packaging metadata (#36)

### 1.1 `pyproject.toml`

```toml
[project]
name = "pyside6-storybook"
version = "0.1.0.dev0"                       # set by the release PRs (§6)
description = "..."                          # unchanged
readme = "README.md"
requires-python = ">=3.11"
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
```

- **`license-files`:** `THIRD_PARTY_NOTICES.md` is included because the wheel ships the Phosphor icons. Their licence text is
  already in the package as `resources/icons/licenses/phosphor-LICENSE.txt`.
- **No `License ::` classifier:** with a licence expression (PEP 639) PyPI rejects them.
- **Python classifiers:** one per version the Full test suite runs (3.11 and 3.14) and the versions between them. A test
  keeps them equal to the versions from `requires-python` up to the newest in `full-tests.yml`.
- **`Framework :: Pytest`:** the plugin ships in the wheel.
- **The authors** are the organisation that holds the copyright in `LICENSE`. No personal name or e-mail address is added.

### 1.2 What goes into the distributions

The wheel is unchanged. It holds the package (with `py.typed`, the icon bundle and its licence, and the examples) and
`pyside6_storybook_pytest.py`. Its `dist-info/licenses/` holds `LICENSE` and `THIRD_PARTY_NOTICES.md`.

The sdist gets an explicit include list instead of "everything not ignored":

```toml
[tool.hatch.build.targets.sdist]
include = [
    "src/",
    "tests/",
    "docs/",
    "examples/",
    "scripts/",
    "README.md",
    "CHANGELOG.md",
    "LICENSE",
    "THIRD_PARTY_NOTICES.md",
    "pyproject.toml",
    "uv.lock",
]
exclude = ["docs/specs/", "**/__pycache__"]
```

The tests stay in the sdist so that downstream packagers (conda-forge, Linux distributions) can run them. `.github/`, the
caches, `.venv`, `dist/` and `site/` stay out.

The `full` packaging tests grow:
- **sdist contents:** the sdist contains the package, the tests and `LICENSE`, and none of `.github/`, `.venv/`, `site/`,
  `docs/specs/` or `__pycache__`.
- **wheel contents:** the wheel contains `py.typed`, at least one `*_stories.py` example module and both licence files under
  `dist-info/licenses/`, and no `tests/`, `scripts/`, `docs/` or `.github/`.
- **metadata:** the `METADATA` file of the built wheel has the expected `License-Expression`, `Project-URL`s and `Classifier`s.

### 1.3 The README on PyPI

PyPI renders the README with its own CommonMark renderer:
- relative links break;
- GitHub-only syntax (alerts such as `> [!NOTE]`, Mermaid, relative images) does not render.

The README becomes the project's front page; the reference moves to the docs site (§5):
- **Kept:**
  - the introduction and the screenshot;
  - Install;
  - "Your first story" (shortened to the story and the command);
  - a "What's in it" list of one line per feature, each linking to its docs page;
  - Licence;
  - the "not affiliated" line.
- **Status line:** says 0.1 is an early release and the API may change in minor versions before 1.0 (§4.2).
- **Install:** the README says `pip install pyside6-storybook` and `uv add --dev pyside6-storybook`, and keeps the Git URL as "the
  development version".
  - This text lands in the PR that sets `0.1.0rc1` (§6), not before, so `main`'s README never advertises a package that does
    not exist yet.
- **Links:** every link is absolute: the docs site, or `https://github.com/Youth-Research-Center/pyside6-storybook/blob/main/...`
  for repository files.
- **Licence section:** keeps the existing PySide6 licence note (LGPLv3, GPLv3 or commercial).

A new core test (`tests/test_readme.py`) fails on a relative Markdown link or image and on a GitHub alert in the README, so the
PyPI page cannot regress.

The README's code samples and its "Styling the gallery" list move with their sections to the docs pages (§5.3). The tests that
check them follow the text: they read the docs pages instead.

## 2. Wheel smoke test in CI (#37)

### 2.1 Workflow `package.yml`

`.github/workflows/package.yml`. Triggers:
- `push` to `main` and `pull_request`, with paths filters on `src/**`, `pyproject.toml`, `uv.lock`, `README.md`,
  `scripts/smoke/**` and `.github/workflows/package.yml`;
- `workflow_call`, so `release.yml` (§3) runs the same jobs.

Top-level `permissions: contents: read`.

**`build`** (ubuntu-latest):
1. Check out, set up uv, `uv build`.
2. Metadata check: `uvx twine@7 check --strict dist/*`.
3. A check that there is exactly one wheel and one sdist, both named with the version from `pyproject.toml`.
4. Upload `dist/` as artifact `dist`.

**`smoke`** (matrix `ubuntu-latest`, `windows-latest`, `macos-latest`; Python 3.11 and 3.14 on each, `fail-fast: false`):
1. Install the Qt system libraries on Linux, as `tests.yml` does.
2. Download `dist`.
3. Check out only `scripts/smoke/` (sparse checkout), into a folder that is never on `sys.path`.
4. Create a virtual environment with `python -m venv` (pip, not uv, as a user would) and install
   `"<wheel>[pytest]"`. The wheel's name is found with a glob in a `shell: bash` step on every system.
5. From an empty working directory, with `QT_QPA_PLATFORM=offscreen` and `timeout-minutes: 10`, run the checks (§2.2).

**`sdist`** (ubuntu-latest, Python 3.11): installs the sdist (`pip install dist/*.tar.gz`) in a fresh environment, which builds it
from source, then runs `pyside6-storybook --version` and the version check of §2.2.

### 2.2 The checks: `scripts/smoke/smoke_test.py`

A plain script run with `python -I` (isolated mode: neither the script's folder nor the working directory is on `sys.path`). It
takes the expected version as its only argument and exits non-zero with a clear message on the first failure. In order:

1. **It runs the installed package.** `pyside6_storybook.__file__` is inside the environment's `site-packages`.
2. **Version.** `pyside6_storybook.__version__` equals the argument. `pyside6-storybook --version` (the console script, in a
   subprocess) prints `pyside6-storybook <version>`.
3. **Package data.** `py.typed` exists next to `__init__.py`, and `pyside6_storybook.gui.icons.icon_svg` returns an SVG for every
   icon name in the bundle.
4. **Examples.**
   - `pyside6-storybook --list --examples` and `python -m pyside6_storybook --list --examples` exit 0 and print the same ids.
   - The list has the 20 example ids: the script carries the expected set, and a test in the repository keeps that set equal to
     the examples.
5. **The gallery.** Build a `GalleryWindow` over the examples' registry with the built-in provider, show it, and select every
   story in Light and in Dark through the window's own selection path. After processing events, each must show its widget,
   not the error panel. Close and delete the window.
6. **The pytest plugin.** In a temporary folder, run `python -m pytest -p pyside6_storybook --storybook --storybook-stories
   pyside6_storybook.examples --storybook-themes Light,Dark -q` in a subprocess with a 120-second timeout. It must exit 0 with
   40 passed tests. This proves that the entry point and the extra work from the wheel.

Each step prints one line (`ok: version 0.1.0rc1`), so the job log reads as a checklist.

**Acceptance:** removing `py.typed` or the examples from the wheel makes step 3 or 4 fail. A core test runs the script against the
development environment (`sys.executable`, the source version) in a subprocess, so the script itself cannot rot. That test skips
step 1, which needs an installed package, through a `--skip-installed-check` flag.

### 2.3 Workflow hygiene

- **Shell:** every `run:` uses `shell: bash`.
- **Paths:** forward slashes in every path.
- **No untrusted interpolation:** no `${{ github.event.* }}` or `${{ inputs.* }}` in shell source.
- **Actions** are pinned by major version, as in the existing workflows.

## 3. Release workflow (#38)

### 3.1 `release.yml`

```yaml
on:
  push:
    tags: ["v*"]
  workflow_dispatch:
    inputs:
      repository:
        description: "Where to publish"
        type: choice
        options: [testpypi, pypi]
        default: testpypi
permissions:
  contents: read
concurrency:
  group: release
  cancel-in-progress: false
```

Jobs, in order:

1. **`target`** (ubuntu): works out where to publish and checks the version. Nothing is uploaded unless it passes.
   - Where to publish: a tag push publishes to `pypi`; a dispatch uses `inputs.repository`, passed through `env:`.
   - It reads the version from `pyproject.toml` (Python's `tomllib`).
   - **Tag push:** the tag must equal `v` + version, or the job fails with both values in the message.
   - **Dispatch to `pypi`:** refused, so a final release always has a tag. "PyPI releases are made by pushing a tag."
   - **Dispatch to `testpypi`:** the version must be a pre-release or a dev release (`0.1.0rc1`, `0.2.0.dev3`), so a final
     version number is never used up on TestPyPI by mistake.
   - Outputs: `repository`, `version`, `index-url`, `upload-url`.
2. **`package`:** `uses: ./.github/workflows/package.yml`, the same build, sdist and smoke jobs as §2. Its artifact `dist` is
   what gets published; nothing is rebuilt.
3. **`publish`** (ubuntu, `needs: [target, package]`):
   - `environment: ${{ needs.target.outputs.repository }}`, with the environment URL set to the project page;
   - `permissions: id-token: write` on this job only.
   - Steps: download `dist`, then `pypa/gh-action-pypi-publish@release/v1` with `repository-url` set from `upload-url`.
   - No token, no `password:`. Attestations stay on (the action's default).
   - The publish step is in `release.yml` itself, not in the reusable workflow, because PyPI's trusted publisher is
     matched against the top-level workflow file.
4. **`verify`** (matrix ubuntu, windows, macos; `needs: publish`):
   - Install `pyside6-storybook==<version>` from the index into a fresh venv. For TestPyPI, with
     `--index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/`, because PySide6 is not on TestPyPI.
   - Retry for up to 10 minutes (every 30 s) for index propagation, then run `pyside6-storybook --version` and
     `pyside6-storybook --list --examples`.
5. **`github-release`** (ubuntu, `needs: verify`, only for a tag push; `permissions: contents: write`):
   - Extract the changelog section for the version with `scripts/release/changelog_section.py <version>` and create the
     release with `gh release create "$TAG" --title "$TAG" --notes-file notes.md dist/*`.
   - The tag and the version come from `env:`.
   - A pre-release version (`rc`, `a`, `b`) gets `--prerelease`.

### 3.2 `scripts/release/changelog_section.py`

Prints the body of `## [X.Y.Z] - YYYY-MM-DD` from `CHANGELOG.md`, without the heading, up to the next `## `. It exits 1 with a
message when there is no such section or the section is empty, so a release with no changelog entry fails before the GitHub
Release.

For a pre-release (`0.1.0rc1`) it looks for `## [0.1.0rc1]` first, then falls back to `## [Unreleased]`. Release candidates
are published from `main` while the changelog still says Unreleased.

Unit tests (core) cover:
- a normal section;
- the last section in the file;
- a missing version;
- an empty section;
- the pre-release fallback.

### 3.3 One-time setup (Owner, documented in `RELEASING.md`)

- **pypi.org:** add a pending trusted publisher: project `pyside6-storybook`, owner `Youth-Research-Center`, repository
  `pyside6-storybook`, workflow `release.yml`, environment `pypi`.
- **test.pypi.org:** the same, with environment `testpypi`. TestPyPI needs its own account.
- **Repository settings → Environments:**
  - `testpypi`: no reviewers, deployment branches `main` only;
  - `pypi`: a required reviewer (the owner), deployment branches and tags `v*` only.
- **Tag protection (optional):** a ruleset on `v*` so only maintainers can push release tags.

## 4. `RELEASING.md`, changelog and version policy (#39)

### 4.1 `CHANGELOG.md`

- **Header.** It already uses Keep a Changelog's layout. The header gains the two links (Keep a Changelog 1.1.0, Semantic
  Versioning) and the rule "every user-facing pull request adds one entry under `[Unreleased]`".
- **Release sections:** `## [0.1.0] - 2026-MM-DD`. The release PR (§6) moves `[Unreleased]` there.
- **Link references** at the bottom: `[Unreleased]` compares the last tag with `main`, and each version links its tag.
- **Breaking changes:** a `### Breaking` heading, used from 0.2 on, lists what a minor release breaks. It always comes first in
  its section.
- **No restructuring:** the existing 0.1 entries stay as they are. Restructuring them is out of scope; they already list what
  milestone 1 added.

### 4.2 Version policy (in `docs/` as "Versions and compatibility", linked from `RELEASING.md` and the README)

- **Scheme.** Semantic Versioning. Before 1.0:
  - a minor release (0.x.0) may break the public API and says so under `### Breaking`;
  - a patch release (0.x.y) never breaks it.
- **The public API** is:
  - what `pyside6_storybook/__init__.py` exports in `__all__`, and `pyside6_storybook.checks`;
  - the command line's options and exit codes;
  - the `[tool.pyside6-storybook]` keys;
  - the `pyside6_storybook.stories` entry-point group;
  - the pytest plugin's options, ini keys, item ids and the `render_story` fixture;
  - the `sbk` object names and the `sbkChrome` property that application style sheets may target.
- **Not public API:** everything else, including the modules under `gui/`, `testing/` and `discovery/`, the look of the gallery
  and the exact text of messages.
- **Supported versions.**
  - Python: every version from 3.11 to the newest that CI tests. Support for a version is dropped in a minor release after it
    reaches its end of life.
  - PySide6: 6.8 and newer, tested with 6.8.0 (the lowest-dependencies job) and the newest release. The minimum is raised only
    in a minor release.
  - Known bad versions are excluded in `pyproject.toml` with a comment, as 6.12.0 is on Python 3.11.

### 4.3 `RELEASING.md`

At the repository root. It is written for a maintainer who has never released this project:

1. **One-time setup:** §3.3, step by step, with the exact values.
2. **Before a release:** CI is green on `main`, the Full test suite has passed on `main` (start it by hand), and the milestone's
   issues are closed.
3. **Release candidate:**
   - open a PR that sets the version to `X.Y.Zrc1` and merge it;
   - run Actions → Release → Run workflow with `testpypi`;
   - check the TestPyPI page (README, screenshot, licence, links, classifiers);
   - install it on Windows, macOS and Linux with the command the workflow prints, and do the manual checks (§6.2).
4. **The release:**
   - open a PR that sets `X.Y.Z` and moves `[Unreleased]` to `## [X.Y.Z] - <date>`; merge it;
   - `git tag -a vX.Y.Z -m "X.Y.Z"` on the merge commit and `git push origin vX.Y.Z`;
   - approve the `pypi` deployment.
5. **After:** check the PyPI page and the GitHub Release. Open the next cycle with a PR: `X.(Y+1).0.dev0` and a new `[Unreleased]`
   section.
6. **A broken release.** PyPI never accepts a version number twice, even after deletion. Yank the broken version on PyPI (with the
   reason) and release the next patch version; never delete it.
7. **A failed workflow:**
   - **Before `publish`:** fix the problem and re-run.
   - **After a partial upload:** the release workflow does not set the action's `skip-existing`, so a re-run fails on the files
     already uploaded. `RELEASING.md` says to release the next number instead: the next rc for a candidate, the next patch for a
     final release.

`AGENTS.md` gains "Releasing: see `RELEASING.md`". Its changelog rule already exists; it gains the `### Breaking` heading.

## 5. Docs site (#40)

### 5.1 Generator

- **MkDocs with the Material theme** (`mkdocs-material` 9.8, actively released), as the issue suggests, and `mkdocstrings[python]`
  for the API reference.
- **Status of the alternatives:** MkDocs itself has had no release since 1.6.1 (August 2024). Zensical, the Material team's
  successor, is at 0.1 and reads the same `mkdocs.yml`, so a later switch costs little.
- **Dependency group `docs`:**
  - `mkdocs-material>=9.8`, `mkdocstrings[python]>=1.0` and `mkdocs>=1.6`, locked in `uv.lock`;
  - never a runtime dependency, and not in `dev`, so CI's test jobs do not install it.
- **`mkdocs.yml`** at the repository root:
  - `site_url` is the Pages URL, and `repo_url` is set;
  - `strict: true`, and the `validation` options set every link, anchor and nav problem to warn, so strict mode fails on it;
  - the theme has a light and dark palette toggle and search.

### 5.2 Pages

The README's reference sections move to pages, mostly as they are, with links between them. Nothing is lost.

| Page | Content | From |
| --- | --- | --- |
| `index.md` | What it is, screenshot, install, the first story, links | README intro, Install, Your first story |
| `writing-stories.md` | `@story`, ids and groups, `StoryContext`, variants, layout, decorators | README: first story, Variants, Layout and decorators |
| `controls.md` | Every control type, its options, and a screenshot of its editor | README Controls + new screenshots |
| `finding-stories.md` | Targets, file naming, `[tool.pyside6-storybook]`, entry points, module names and `sys.path` | README "Where your stories come from" + loader rules |
| `command-line.md` | Every option, exit codes | README Command line, checked against `--help` (§5.3) |
| `gallery.md` | The window, keyboard, canvas, Docs tab, logging actions, hot reload | README sections of the same names |
| `themes.md` | Built-in themes, providers, tokens, styling the gallery | `docs/theming.md` + README Themes, Design tokens, Styling the gallery |
| `testing.md` | The pytest plugin, checks, snapshots, the fixture | README "Testing stories" |
| `troubleshooting.md` | Load errors, duplicate ids, running headless (`QT_QPA_PLATFORM=offscreen`), fonts in CI, the System theme in contrast checks | new, from existing notes |
| `versions.md` | §4.2 | new |
| `reference.md` | API reference for `pyside6_storybook` (`__all__`) and `pyside6_storybook.checks` | mkdocstrings |
| `roadmap.md` | Links to `docs/roadmap.md` on GitHub and to the milestones | new, short |
| `changelog.md` | Includes `CHANGELOG.md` | snippet include |

- **`docs/theming.md`** moves into `docs/themes.md`. Its old path becomes a one-line pointer, so existing links keep working.
- **`docs/specs/`** and **`docs/roadmap.md`** are excluded from the build (`exclude_docs`). They stay in the repository.

### 5.3 Code and facts that cannot drift

- **Code samples.** `tests/test_readme.py` becomes `tests/test_docs.py`, with the same mechanism. It extracts the fenced Python
  blocks under named headings of the named pages and runs them, exactly as it does for the README today. Every existing check
  keeps its assertion and only changes where it reads from:
  - first story;
  - controls table;
  - `pyproject.toml` example;
  - variants;
  - layout;
  - decorators;
  - size presets;
  - logging.

  New checks:
  - every Python block in `writing-stories.md`, `controls.md` and `testing.md` at least compiles;
  - **command line:** the options listed in `command-line.md` equal the parser's options (from `cli._build_parser()` or the
    module's equivalent, without running it).
- **Styling names.** `tests/test_chrome_styling.py` reads the object-name list from `themes.md` instead of the README.
- **API reference:** generated, so it cannot drift. A test checks that every name in `__all__` appears on `reference.md`.

### 5.4 Screenshots

`scripts/docs/render_docs_images.py` (development only, next to `render_theming_images.py`) renders, offscreen with the built-in
Light theme:
- the gallery (`docs/images/gallery.png`, replacing the hand-made one; the README keeps its absolute URL);
- one image per control type's editor (`docs/images/controls/<type>.png`).

The images are committed. A `full` test runs the script into a temporary folder, checks that it produces every file, and checks
that each image is non-empty and of a plausible size. It does not compare pixels.

### 5.5 Workflow `docs.yml`

- **Triggers:**
  - `pull_request` and `push` to `main`, with paths filters on `docs/**`, `mkdocs.yml`, `src/**`, `README.md`, `CHANGELOG.md`
    and the workflow;
  - `workflow_dispatch`.
- **`build`:** `uv sync --group docs --locked`, then `uv run --no-sync mkdocs build --strict`. Upload the site with
  `actions/upload-pages-artifact` on `main` only.
- **`deploy`** (on push to `main` only):
  - `needs: build`, `environment: github-pages`;
  - `permissions: pages: write, id-token: write` on this job only;
  - `actions/deploy-pages`.
- **Code samples and the CLI check** run with the core tests in `tests.yml`, not here.

**Owner:** Settings → Pages → Source: GitHub Actions. Also set the repository's About box (website: the docs URL; topics).

## 6. The release itself (#41)

### 6.1 What lands as pull requests

1. **`0.1.0rc1`:**
   - version `0.1.0rc1`;
   - the README's install section switches to PyPI (§1.3);
   - the changelog's `[Unreleased]` stays.
2. **`0.1.0`:**
   - version `0.1.0`;
   - `## [0.1.0] - <date>` replaces `[Unreleased]` with its content;
   - link references;
   - the README status line.
3. **`0.2.0.dev0`:** version `0.2.0.dev0` and a new empty `## [Unreleased]`.

Each is one small PR, merged at its point in §6.2.

### 6.2 Order of events

1. PRs for §1 to §5 merged. CI green, and the Full test suite green on `main`.
2. **Owner:** trusted publishers and environments (§3.3), Pages source (§5.5).
3. PR "Release 0.1.0rc1" merged. **Owner:** run the Release workflow with `testpypi`.
4. **Owner** (manual checks on Windows, macOS and Linux): install from TestPyPI in a clean venv, then:
   - `pyside6-storybook --examples` opens the gallery;
   - switch themes;
   - edit a control;
   - open a story folder (`pyside6-storybook path/to/stories`);
   - `pytest --storybook` in a small project.

   Then check the TestPyPI page. Problems found: fix, and release `0.1.0rc2` the same way.
5. PR "Release 0.1.0" merged. **Owner:** tag `v0.1.0` on the merge commit, push it, and approve the `pypi` deployment.
6. The workflow verifies the install and creates the GitHub Release. **Owner:** check the PyPI page, and set the About box links
   (docs, PyPI) and topics.
7. PR "Start 0.2.0" merged.

## 7. Manual steps for the owner (summary)

| When | Where | Step |
| --- | --- | --- |
| Before the first release | pypi.org (account with 2FA) | Add a pending trusted publisher: `pyside6-storybook`, `Youth-Research-Center/pyside6-storybook`, `release.yml`, environment `pypi` |
| Before the first release | test.pypi.org (separate account) | The same, environment `testpypi` |
| Before the first release | GitHub repository settings → Environments | Create `testpypi` (deployments from `main`) and `pypi` (required reviewer: you; deployments from tags `v*`) |
| Before the first release (optional) | GitHub repository settings → Rules | Tag ruleset protecting `v*` |
| When the docs PR merges | GitHub repository settings → Pages | Source: GitHub Actions |
| Release candidate | Actions → Release → Run workflow | Repository `testpypi` |
| Release candidate | Windows, macOS, Linux | Install from TestPyPI and check by hand (§6.2 step 4); check the TestPyPI page |
| Release | Terminal | `git tag -a v0.1.0 -m "0.1.0"` on the release PR's merge commit; `git push origin v0.1.0` |
| Release | Actions → the Release run | Approve the `pypi` deployment |
| After the release | pypi.org, GitHub | Check the PyPI page and the GitHub Release; About box: website, topics |
| Each milestone stack | Actions → Full test suite | Run on `main` before the release PR |

## 8. Out of scope

- **Automation:** automatic version bumps and changelog generation; CI that enforces changelog entries.
- **Other channels:** conda-forge; announcing the release.
- **Docs:** versioned docs (one version until 1.0).
- **#42 and #43** (milestone 7).
