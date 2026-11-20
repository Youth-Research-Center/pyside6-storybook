# Contributing to pyside6-storybook

## Welcome

Thank you for helping. You can contribute code, documentation, example stories, testing on your platform (Windows, macOS and the Linux
desktops), and design feedback on the gallery and the API.

- Questions about using pyside6-storybook go to [GitHub Discussions](https://github.com/Youth-Research-Center/pyside6-storybook/discussions)
  (Q&A).
- Everyone who takes part follows the [code of conduct](CODE_OF_CONDUCT.md).

## Before you start

- **A bug or a well-scoped request:** open an issue with
  [one of the forms](https://github.com/Youth-Research-Center/pyside6-storybook/issues/new/choose). The bug form asks for the output of
  `pyside6-storybook --debug-info` and a minimal story.
- **A bigger change or a design question:** start in Discussions (Ideas), so we can agree on the direction before you write code.
- **Where to start:** issues labelled
  [good first issue](https://github.com/Youth-Research-Center/pyside6-storybook/labels/good%20first%20issue) and
  [help wanted](https://github.com/Youth-Research-Center/pyside6-storybook/labels/help%20wanted).
- **Comment on the issue before you work on it**, so two people do not do the same thing.
- **A security problem is not an issue.** Report it privately, as [SECURITY.md](SECURITY.md) describes.

## Set up

You need Git, Python 3.11 or newer, and [uv](https://docs.astral.sh/uv/). If you do not have write access to the repository, fork it
first and clone your fork.

**Linux.** Qt needs some system libraries. On Debian or Ubuntu:

```bash
sudo apt-get update && sudo apt-get install -y libegl1 libxkbcommon0 libfontconfig1 libdbus-1-3 libxcb-cursor0
```

CI installs the first four. `libxcb-cursor0` is also needed to open the gallery window on X11. A desktop install usually has the rest
(libGL, GLib). If Qt reports `Could not load the Qt platform plugin "xcb"`, the error names the missing library.

Then clone the repository, create the environment and open the gallery on the example stories:

```bash
git clone https://github.com/Youth-Research-Center/pyside6-storybook.git
cd pyside6-storybook
uv sync
uv run pyside6-storybook --examples
```

## Run the checks

There is no display in CI, so the tests run with `QT_QPA_PLATFORM=offscreen`. Run these in the order CI runs them:

```bash
uv run ruff check .
uv run ty check
QT_QPA_PLATFORM=offscreen uv run pytest -q -m "not full"
QT_QPA_PLATFORM=offscreen uv run pytest -q
```

- `ruff check` lints the code: errors, import order, line length (150 characters) and keyword-only boolean parameters.
- `ty check` is the type checker. It must report no diagnostics in `src/` or `tests/`.
- The `-m "not full"` run is the core tests, which CI runs on every push. Run the full suite before you open a pull request.

On Windows PowerShell, set the variable first:

```powershell
$env:QT_QPA_PLATFORM = "offscreen"
uv run pytest -q
```

Three more checks apply only to some changes:

- If you change a workflow, run `actionlint`, as [AGENTS.md](AGENTS.md) describes.
- If you change an icon, run `uv run python scripts/icons/build_icon_bundle.py --check`.
- If you change `docs/`, preview the site with `uv sync --group docs` and `uv run mkdocs serve`. Run `uv sync` afterwards, so the
  environment matches the tests'.

## How the code is laid out

- `src/pyside6_storybook/` is the package, with the sub-packages `registry` (the story model), `controls`, `decorators`, `discovery`
  (finding and loading stories), `gui` (the gallery), `themes`, `testing` (the pytest plugin's implementation) and `checks`.
- `src/pyside6_storybook_pytest.py` is the pytest plugin's entry module.
- `tests/` holds one test module per source module.
- `docs/` holds the pages of the documentation site.

[AGENTS.md](AGENTS.md#project-structure) has the full map.

## Adding a control type

These are the places that list every control. `FileControl` is a small, complete example of each.

1. `src/pyside6_storybook/controls/<name>_control.py`: a frozen dataclass with `name`, `default`, `label`, `description`,
   `display_label` and `coerce`. It uses the helpers in `src/pyside6_storybook/controls/_options.py`.
2. Export it: add it to the imports and to the `Control` union in `src/pyside6_storybook/controls/__init__.py`, to the imports and
   `__all__` of `src/pyside6_storybook/__init__.py`, and to the set of names in `tests/test_package.py`.
3. `src/pyside6_storybook/gui/editors/<name>_editor.py`: a `ControlEditor` subclass, registered in `EDITORS` in
   `src/pyside6_storybook/gui/editors/__init__.py` and added to the set in `tests/test_editors.py`.
4. `src/pyside6_storybook/gui/docs_panel.py`: add a branch to `_control_row`, or the Docs tab raises `TypeError` for the new control.
5. An example story that uses the control and every one of its options, in a `*_stories.py` module under
   `src/pyside6_storybook/examples/`. `tests/test_examples.py` checks both.
6. `docs/controls.md`: the table, the image bullet and "The options".
7. The control's image: add it to `_CONTROLS` in `scripts/docs/render_docs_images.py` and to `_CONTROL_TYPES` in
   `tests/test_docs_images.py`, then run `uv run python scripts/docs/render_docs_images.py` and commit the new image.
8. A `:::` line in `docs/reference.md`.
9. Tests in `tests/test_controls.py`, `tests/test_editors.py` and `tests/test_docs_panel.py`.
10. The module lists in `AGENTS.md`, and a `CHANGELOG.md` entry.

## Adding a built-in decorator

1. `src/pyside6_storybook/decorators/<name>.py`: the decorator, reusing the argument checks in
   `src/pyside6_storybook/decorators/_checks.py`.
2. Export it in `src/pyside6_storybook/decorators/__init__.py`, and add it to the `__all__` test in `tests/test_decorators.py`.
3. Document it in `docs/writing-stories.md`, in the "Decorators" section, where the built-in decorators are shown.
4. Tests in `tests/test_decorators.py`, the module list in `AGENTS.md`, and a `CHANGELOG.md` entry.

`pyside6_storybook.decorators` is documented, but `docs/versions.md` does not list the module as public API yet.

## Pull requests

Keep a pull request to one concern. The [pull request template](.github/pull_request_template.md) has the checklist:

- tests for the change, and a regression test that fails without the fix for a bug;
- a `CHANGELOG.md` entry under `[Unreleased]` for a user-facing change;
- updated docs, and screenshots for a change to the gallery;
- `Closes #N` only when the pull request fully resolves the issue, otherwise `Refs #N`.

CI runs lint, `ty` and the core tests on every pull request, and the package smoke tests when packaging files change. Maintainers merge
with "Create a merge commit".

## Issues, labels and milestones

- The `area:` labels say which part of the project an issue is about, the `effort:` labels give its rough size, and the `priority:`
  labels give the order.
- Maintainers add the labels.
- A milestone groups the issues of one goal. The issue tracker, not the roadmap, is the source of truth for scope.

## Releases

Only maintainers make releases. See [RELEASING.md](RELEASING.md).

## Coding agents

[AGENTS.md](AGENTS.md) and [CLAUDE.md](CLAUDE.md) hold the conventions for people and coding agents alike. A pull request made with a
coding agent follows the same rules.
