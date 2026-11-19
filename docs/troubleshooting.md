# Troubleshooting

## A story module fails to load

A story module that fails to import is listed in the gallery under "Load errors (N)" with its traceback, and the gallery opens with the
stories that did load. Fix the file and the hot reload loads it again (see [Hot reload](gallery.md#hot-reload)).

- With `--list`, the failure is printed on standard error and the exit code is 1 (see [Command line](command-line.md#exit-codes)).
- A target that does not exist, a configuration that is not valid, or a project that has no story at all is an error with exit code 1,
  and a configured source that fails never falls back to the built-in examples (see
  [Finding stories](finding-stories.md#where-your-stories-come-from)).
- Under pytest, a story file that fails to import is a failing test, `storybook::load-error[<file>]`, and the other stories still run
  (see [What runs](testing.md#what-runs)). A story module that a test module or a `conftest.py` already imported is not executed
  again, so its stories cannot be tested: import story modules inside the tests that use them.
- A theme provider that cannot be loaded, or an unknown theme, prints an error and exits with code 1 instead of using the built-in
  themes (see [Choosing a theme provider](themes.md#choosing-a-theme-provider)).

## Duplicate story ids

A story id is unique. Registering an id that another function already registered raises a `ValueError` that names both places:
`Story id 'Buttons/Greeting' is already registered by ...; cannot register it again from ...`. The second story module is listed under
"Load errors". Give one of the stories another id. Registering the same id again from the same module and function, which a reload does,
replaces the earlier story and keeps its position, so it is not an error.

## Running headless

There is no display in CI or on a server. Set `QT_QPA_PLATFORM=offscreen` for anything that starts Qt:

```bash
QT_QPA_PLATFORM=offscreen pytest --storybook
```

`pyside6-storybook --list` needs no display: it uses the offscreen platform unless `QT_QPA_PLATFORM` says otherwise. The pytest plugin
does the same for the story tests (see [What runs](testing.md#what-runs)). Opening the gallery window needs a display.

## Fonts and subpixel text in CI

The text-contrast check measures pixels, and it renders the story with greyscale anti-aliasing even where the system draws subpixel
(coloured) text, so the colours it measures are the text's own (see [Text contrast](testing.md#text-contrast)). A result near the
threshold is an estimate, especially for thin, small text, and the fonts of a CI runner differ from yours.

Screenshot baselines differ between systems for the same reason: make them on the machine that CI uses, and install the same fonts
everywhere (see [Screenshot snapshots](testing.md#screenshot-snapshots)).

The first use of fonts in a process can log a warning about the system, not about a story: on Windows the offscreen platform reports
"Cannot find font directory", on macOS "Populating font family aliases took N ms". The plugin loads the fonts before the first story
test, so these messages do not fail a story.

## The System theme in contrast checks

System is Qt's own palette, which is not the palette your application ships, so a contrast failure under it may not be one your users
see. List the themes you want with `--storybook-themes`:

```bash
pytest --storybook --storybook-a11y --storybook-themes Light,Dark
```

or set `storybook_themes = "Light,Dark"` in the pytest ini options (see [Options](testing.md#options)).

## The theme switch does nothing, or the gallery is unreadable

See [Common problems](themes.md#common-problems) in Themes.
