# Build the docs site with Zensical (#100): design and plan

Status: reviewed (findings applied). One pull request. Section numbers (§1) are used by the plan.

## 0. Starting point

- **Today's build.** The site is built by MkDocs 1.6.1 with Material for MkDocs 9.8 and mkdocstrings, from `mkdocs.yml`. `docs.yml` runs
  `mkdocs build --strict` and deploys `site/` to Pages on `main`.
- **Material's end of life** is 5 May 2027. Zensical (MIT, as is its theme package `zensical-ui`) is at 0.1.3 (20 November 2026; 0.1.0
  came out on 5 November). It requires Python 3.11 or newer and ships a compiled wheel per platform.
- **What was checked.** On 23 November 2026, I and a reviewer built this repository's `mkdocs.yml` with `zensical build --strict` (0.1.3)
  and `mkdocstrings[python]` 1.0.8, with `theme.variant: classic` added. The build passed in about 1.5 s with "No issues found". All 14
  pages were compared with today's MkDocs build, by their article HTML and by screenshots:
  - **Content.** The API reference renders the same, and the `CHANGELOG.md` snippet include works.
  - **Unchanged parts:** permalinks, admonitions, images, the repo link, canonical and description tags, `objects.inv` (261 entries
    both) and `sitemap.xml` (same URLs).
  - **Search:** Ctrl+K and "theme provider" give 36 results, API reference included, and Enter opens the right anchor.
  - **Toggle:** it switches `default` to `slate` and still applies after a reload.
  - **404 page:** a deep 404 is styled and its nav works.
  - **Sub-path:** served under a `/pyside6-storybook/` prefix, as on GitHub Pages, no asset request fails.
  - **Config:** `exclude_docs: specs/` is honoured, and `theming.md` (in `not_in_nav`) is still built. `variant` is the right key
    (`zensical/config.py`, default `"modern"`), and there are no deprecation warnings.
- **Visible differences** with `variant: classic`. None removes anything that matters, and they are listed in the pull request:
  - code blocks get Pygments highlighting, because Zensical always enables `pymdownx.superfences`;
  - two `toml` fences inside list items on `finding-stories` now render as code blocks. On the live site they render as inline
    `<p><code>`, so this is a fix;
  - the table of contents title is "On this page";
  - search opens as a Ctrl+K dialog;
  - the home page title is "Home - pyside6-storybook";
  - the footer says "Made with Zensical";
  - there is no `sitemap.xml.gz`.
- **What strict mode catches.** These abort the build:
  - a link to a missing page, and a missing anchor;
  - a missing snippet and a `:::` identifier mkdocstrings cannot collect. These two abort through a Python traceback even without
    `--strict`, after "No issues found" has already been printed.
  - a link to a page excluded by `exclude_docs`, which MkDocs allowed; Zensical is stricter here.
- **What strict mode lets through but MkDocs failed on:**
  1. **mkdocstrings/griffe docstring warnings**, such as an `Args:` entry for a parameter that does not exist. MkDocs aborts with
     "Aborted with 2 warnings in strict mode!". Zensical prints the same `griffe:` lines to stderr and exits 0.
  2. **A page that is in neither `nav` nor `not_in_nav`** (`validation.nav.omitted_files`).
  3. **A root-relative link** such as `/absolute`.
  4. **An unrecognised relative link** such as `[x](gallery/)` or `[x](some-dir)` (`validation.links.unrecognized_links`).
  5. **A missing image.** Already covered by `test_every_image_a_page_shows_exists_under_docs`.
  6. **A nav entry for a missing file.** Already covered by `test_the_nav_lists_existing_pages`.

  §2 and §3 replace 1 to 4.
- **Dependencies.** With Zensical, `mkdocs-material` is not installed. `mkdocs` 1.6.1 still is, because `mkdocstrings` 1.x depends on it
  and imports its internals. MkDocs 2.0 pre-releases (2.0.dev0 to dev6) are on PyPI.

## 1. Configuration (`mkdocs.yml`)

- **Keep `mkdocs.yml`.** Zensical reads it, and the tests parse its `nav`. A move to `zensical.toml` is out of scope.
- **`theme`:** add `variant: classic`, so the site keeps Material's look. The `palette` block stays.
- **`validation`:** keep the block. Zensical maps `links.not_found`, `links.anchors` and `links.absolute_links` into its own link and
  anchor checks, so the block still matters; setting `not_found: ignore` would switch link checking off. Zensical ignores
  `nav.omitted_files` and `links.unrecognized_links`; §3 covers those. Add a comment in the file saying so.
- **Everything else is unchanged:** `strict: true` (which Zensical honours even without the flag), `exclude_docs`, `not_in_nav`, `nav`,
  `plugins` and `markdown_extensions`.

## 2. Dependencies, workflow and docs

- **`pyproject.toml`, the `docs` group:**
  ```toml
  docs = [
      "zensical>=0.1.3,<0.2",
      "mkdocstrings[python]>=1.0.7",
      "mkdocs>=1.6,<2",  # not used directly: caps the MkDocs that mkdocstrings needs (it does not support MkDocs 2)
  ]
  ```
  `mkdocs-material` leaves. Zensical is pre-1.0, so `<0.2` keeps a 0.2 with breaking changes from arriving unreviewed; Dependabot
  proposes it as a normal update after the cooldown.
- **`uv.lock`:** run `uv lock`. Check that `mkdocs-material` is gone and that `zensical` and `zensical-ui` are in.
- **`.github/workflows/docs.yml`:**
  - **Build step.** The build runs with its output saved, and a docstring warning fails it:
    ```yaml
    - name: Build the site (strict, and failing on docstring warnings)
      run: |
        set -o pipefail
        uv run --no-sync zensical build --strict 2>&1 | tee build.log
        if grep -E '^(griffe|mkdocstrings|mkdocs_autorefs):' build.log; then
          echo "::error::mkdocstrings reported a docstring problem; see the lines above"
          exit 1
        fi
    ```
    The steps run with bash (`defaults.run.shell: bash`). The reviewer checked this: it fails on a bogus `Args:` entry and passes on
    `main`.
  - **Other edits:**
    - the header comment names Zensical and the warning check;
    - the `NO_MKDOCS_2_WARNING` env block goes, because the warning was Material's;
    - the Pages artifact path stays `site`, Zensical's default;
    - the `paths` filters keep `mkdocs.yml`.
- **`.github/dependabot.yml`:** keep the `mkdocs>=2` ignore, with a comment saying MkDocs comes in through mkdocstrings, which does not
  support MkDocs 2.
- **`AGENTS.md`:**
  - **"Docs site":** the commands become `uv run zensical serve` (preview at `http://localhost:8000`) and
    `uv run zensical build --strict`. A note says that `serve` does not support `--strict`, and that CI also fails on `griffe:`
    warnings, so a build that prints one is not clean. The `NO_MKDOCS_2_WARNING` sentence goes.
  - **"Project structure":** the docs entry says Zensical (classic look) with mkdocstrings. The `mkdocs build --strict` mention becomes
    `zensical build --strict`, followed by the tests of §3. A sentence says the config stays in `mkdocs.yml`.
  - **The CI list:** the "Docs" entry says Zensical and the docstring-warning check.
- **`CONTRIBUTING.md`:** the preview command becomes `uv run zensical serve`. Run `tests/test_community_files.py` afterwards; it checks
  only `pytest` and `ruff` lines, so nothing there needs changing.
- **Other pages.** A grep of `docs/`, `README.md` and `RELEASING.md` finds no other mention of MkDocs or Material. The plan reruns that
  grep.
- **`CHANGELOG.md`.** The docs site has not been released yet. Its entry is under `[Unreleased]` → `### Added` on `main`, and under
  `[0.1.0]` in #110 if that merges first. So the existing entry is edited rather than a new one added: "Documentation site (Zensical, with
  Material's classic look, and mkdocstrings)", and "`docs.yml` builds it with `zensical build --strict`".
- **The milestone-7 shared instructions** for subagents (`/tmp/claude-0/specs7/common.md`): the docs check becomes
  `uv sync --group docs && uv run zensical build --strict 2>&1 | tee /tmp/claude-0/build.log && ! grep -E '^(griffe|mkdocstrings|mkdocs_autorefs):' /tmp/claude-0/build.log && uv sync`.

## 3. Tests that replace the checks Zensical does not make

In `tests/test_docs.py`:
- **`test_every_page_is_in_the_nav_or_listed_as_not_in_the_nav`.**
  - Every `docs/**/*.md` is either in the nav (via the existing `_nav_pages`) or in `not_in_nav`, except the paths `exclude_docs`
    excludes.
  - The `exclude_docs` and `not_in_nav` lists are read from `mkdocs.yml`, not hard-coded.
  - Both use gitignore-style patterns. The test supports what the repository uses today: a directory prefix (`specs/`) and an exact file
    name (`theming.md`). It fails with a clear message on any other pattern, so a future pattern needs the test extended.
- **`test_every_relative_link_on_a_site_page_resolves_to_a_file_under_docs`.**
  - It covers every Markdown link and image target on a page that is built (every `docs/**/*.md` outside `exclude_docs`, fenced code
    skipped) that is not a URL with a scheme (`http:`, `https:`, `mailto:`) and not a pure `#anchor`.
  - Such a target must not start with `/`. Without its `#anchor`, it must resolve, relative to the page, to an existing file under
    `docs/`.
  - It reuses the module's existing link regex.
  - It replaces `validation.links.absolute_links` and `unrecognized_links`. The anchor part is still checked by Zensical's strict build.
- **Each test fails on a broken tree.** The plan checks this with an orphan page, a `/absolute` link, a `[x](gallery/)` link and a
  `[x](some-dir)` link, each added and removed again.
- **The docstring-warning check of §2.** The plan checks it once by hand: add a bogus `Args:` entry, see the step fail, and revert.

## 4. Verification before the pull request

- **Strict build and the warning check.** `uv sync --group docs` and the §2 build step pass. The negative cases of §0 each abort it: a
  missing page, a missing anchor, a missing snippet, a bad `:::` line and a docstring warning, each tried and reverted.
- **In a browser,** with Playwright against a local server on `site/` under a `/pyside6-storybook/` prefix:
  - screenshots in light and dark of the home page, "The gallery", "Finding stories" and "API reference", next to the same pages from
    today's MkDocs build;
  - search for "theme provider" returns results;
  - the toggle switches the scheme.

  The screenshots and the list of visible differences from §0 go into the pull request.
- **Tests.** The full test suite passes, including the new tests in `tests/test_docs.py`.

## 5. Risks

- **Zensical is 0.1.x.** Releases came fast: 0.1.0 to 0.1.3 within 15 days. The `<0.2` pin, the 7-day Dependabot cooldown and the strict
  build in CI catch most regressions. If one blocks a docs change, pin the last good 0.1.x release.
- **Zensical may add its own checks later.** The tests of §3 and the warning check stay either way; they are cheap.
- **Rollback.** Revert the pull request. Material keeps working until May 2027.

## 6. Out of scope

- Moving the configuration to `zensical.toml`.
- Restyling the site.
- Versioned docs.
