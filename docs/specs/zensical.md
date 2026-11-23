# Build the docs site with Zensical (#100): design and plan

Status: draft. One pull request. Section numbers (§1) are used by the review.

## 0. Starting point

- **Today's build.** The site is built by MkDocs 1.6.1 with Material for MkDocs 9.8 and mkdocstrings, from `mkdocs.yml`.
  `docs.yml` runs `mkdocs build --strict` and deploys `site/` to Pages on `main`.
- **Material's end of life** is 5 May 2027. Its successor, Zensical, is at 0.1.3 (20 November 2026; 0.1.0 came out on
  5 November). It requires Python 3.11 or newer.
- **What I tried.** On 23 November 2026 I built this repository's unchanged `mkdocs.yml` with `zensical build --strict` (0.1.3), next
  to `mkdocstrings[python]` 1.0.8. The build passed in 1.5 s with "No issues found". I then checked the output against the MkDocs
  build:
  - **API reference.** mkdocstrings renders it (`reference/index.html`, with every `doc-heading`).
  - **Changelog.** The `pymdownx.snippets` include of `CHANGELOG.md` works.
  - **Search.** It works in a browser: Ctrl+K and "theme provider" give 36 results, API reference included.
  - **Light/dark toggle.** It switches `data-md-color-scheme` from `default` to `slate`.
  - **`exclude_docs: specs/`** is honoured, and `theming.md` (in `not_in_nav`) is still built.
  - **Look.** With `theme.variant: classic`, the site looks like today's Material site: header, nav, fonts, toggle. Without it,
    Zensical's own "modern" look is used. Screenshots of both builds, light and dark, were compared.
- **Strict mode** (`--strict`) aborts on:
  - a link to a missing page;
  - a missing anchor;
  - a missing snippet;
  - an `:::` identifier mkdocstrings cannot collect.
- **What strict mode does not catch.** MkDocs's `validation:` block catches two cases that Zensical 0.1.3 lets pass:
  - a page that is in neither `nav` nor `not_in_nav` (`validation.nav.omitted_files`);
  - a root-relative link such as `/absolute` (`validation.links.absolute_links`).
- **Dependencies.** With Zensical, `mkdocs-material` is not installed at all. `mkdocs` 1.6.1 is still installed, because
  `mkdocstrings` 1.x depends on it.

## 1. Configuration

- **Keep `mkdocs.yml`.** Zensical reads it, and the tests (`tests/test_docs.py`, `tests/test_readme.py`) parse its `nav`. A move to
  `zensical.toml` is not needed for #100.
- **`theme`.** Add `variant: classic` under `theme:`, so the deployed site looks as before (the issue's acceptance criterion). The
  `palette` block stays as it is.
- **`validation`.** Keep the block. MkDocs no longer reads it, but it documents intent and does no harm. Zensical ignores keys it does
  not use: 0.1.3 reported no issue for it. §3 replaces the two checks Zensical does not make.
- **Everything else is unchanged:** `strict: true`, `exclude_docs`, `not_in_nav`, `nav`, `plugins` (search, mkdocstrings and its
  options) and `markdown_extensions`.

## 2. Dependencies, workflow and docs

- **`pyproject.toml`, the `docs` group:** `["zensical>=0.1.3,<0.2", "mkdocstrings[python]>=1.0.7"]`.
  - `mkdocs` and `mkdocs-material` leave the group. `mkdocs` comes in through mkdocstrings.
  - Zensical is pre-1.0, so the upper bound stops a 0.2 with breaking changes from arriving unreviewed. Dependabot proposes 0.2 as a
    normal update, after the cooldown.
- **`uv.lock`:** run `uv lock`.
- **`.github/workflows/docs.yml`:**
  - the build step becomes `uv run --no-sync zensical build --strict`;
  - the header comment names Zensical;
  - the `NO_MKDOCS_2_WARNING` env block goes, because the warning was Material's;
  - the Pages artifact path stays `site`, which is Zensical's default `site_dir`;
  - the `paths` filters keep `mkdocs.yml`.
- **`.github/dependabot.yml`:** keep the `mkdocs>=2` ignore, with a comment saying it is now transitive through mkdocstrings, which does
  not support MkDocs 2.
- **`AGENTS.md`:**
  - the "Docs site" section's commands become `uv run zensical serve` (preview at `http://localhost:8000`; the plan checks the real
    address in the command's output) and `uv run zensical build --strict`;
  - the `NO_MKDOCS_2_WARNING` sentence goes;
  - "Project structure" says Zensical, with the Material classic look, and mkdocstrings;
  - the CI list's "Docs" entry says Zensical;
  - the `mkdocs build --strict` mention in the `mkdocs.yml` entry becomes `zensical build --strict`, plus the new tests of §3.
- **`CONTRIBUTING.md`:** the preview command becomes `uv run zensical serve`.
- **`docs/roadmap.md`** and any other page that names MkDocs or Material as the site's builder: update the wording. The plan greps
  `docs/`, `README.md`, `RELEASING.md` and `CONTRIBUTING.md`.
- **The milestone-7 shared instructions** for subagents (`/tmp/claude-0/specs7/common.md`): the docs check becomes
  `uv sync --group docs && uv run zensical build --strict && uv sync`.
- **`CHANGELOG.md`:** under `[Unreleased]` → `### Changed`: "The documentation site is built with Zensical instead of MkDocs with
  Material for MkDocs, which reaches end of life in May 2027. It looks and works as before."

## 3. Tests that replace the checks Zensical does not make

In `tests/test_docs.py`:
- **`test_every_page_is_in_the_nav_or_listed_as_not_in_the_nav`.** Every `docs/**/*.md` outside `docs/specs/` is either in the nav (via
  the existing `_nav_pages`) or matched by a line of `not_in_nav`. This replaces `validation.nav.omitted_files`.
- **`test_no_page_links_with_a_root_relative_url`.** No Markdown link or image on a page under `docs/` (outside `docs/specs/` and fenced
  code) has a target that starts with `/`. This replaces `validation.links.absolute_links`. Reuse the module's existing link regex.
- **Both fail on a broken tree.** The plan checks each by adding an orphan page and a `/absolute` link, then removing them.

## 4. Verification before the pull request

- **Strict build.** `uv sync --group docs && uv run zensical build --strict` passes. The negative cases of §0 abort it: a missing page,
  a missing anchor, a missing snippet and a bad `:::` line, each tried and reverted.
- **In a browser,** with Playwright against a local server on the built `site/`, both themes:
  - screenshots of the home page, "The gallery" and "API reference", next to the same pages from today's MkDocs build;
  - search for "theme provider" returns results;
  - the toggle switches the scheme.

  The screenshots go into the pull request.
- **Tests.** The full test suite passes, and so does `tests/test_docs.py` with the new tests.

## 5. Risks

- **Zensical is 0.1.x.** A later 0.1 release may change behaviour. The pin `<0.2` and the strict build in CI catch most of it. If a
  regression blocks a docs change, pin the last good 0.1.x release.
- **MkDocs-only validation.** Zensical may add checks of its own later. The two new tests stay either way, since they are cheap.
- **Rollback.** Revert the pull request. Material keeps working until May 2027.

## 6. Out of scope

- Moving the configuration to `zensical.toml`.
- Restyling the site.
- Versioned docs.
