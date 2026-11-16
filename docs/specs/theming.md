# Theming hook (milestone 4): design spec

Status: reviewed; ready for implementation. Covers issues #26 (`ThemeProvider` protocol), #29 (chrome under an application style
sheet), #27 (design tokens), #30 ("System" theme), #28 (choosing a provider) and #31 (guide and worked example). The issues hold
the scope and acceptance criteria; this document fixes the decisions they leave open and how the six pull requests fit together.
Where this spec and an issue differ, the issue is updated to match.

## Goals and constraints

- **Stories and code written for milestones 1–3 keep working.** New public parameters are keyword-only and come after the existing
  ones; `StoryContext` gains fields with defaults.
- **The library stays generic.** It knows nothing about any application's theme manager; a provider adapts one.
- **Chrome colours come from palette roles.** That is why a provider must keep `QApplication.palette()` in step with any style
  sheet it sets (#26's contract).
- **A failing provider never closes the gallery.** Every call into a provider is guarded.
- **Library code takes its collaborators as arguments.** The window receives the provider; nothing reads a global provider.

## 1. The `ThemeProvider` protocol (#26)

`themes/provider.py` defines a `typing.Protocol`, decorated `@runtime_checkable`, exported from the package root:

```python
class ThemeProvider(Protocol):
    def theme_names(self) -> Sequence[str]: ...
    def current_theme(self) -> str: ...
    def activate(self, app: QApplication) -> None: ...
    def set_theme(self, name: str) -> None: ...
    def on_changed(self, callback: Callable[[], None]) -> None: ...
    def deactivate(self) -> None: ...
```

**Optional methods**, looked up with `getattr` and not part of the protocol, so a minimal provider does not need them:
- `tokens() -> Mapping[str, object]` (#27);
- `color_scheme() -> Qt.ColorScheme` (#30).

**Lifecycle and contract.** These are the rules the guide (#31) documents and `tests/fake_providers.py` exercises:
1. `theme_names()` and `current_theme()` work before `activate`, so the command line can validate `--theme` and `--list` can print
   the themes. `theme_names()` is non-empty and does not change while the provider is active.
2. `activate(app)` is called once, before the window is built. It records whatever it will change (style, palette, style
   sheet, font, colour scheme) and applies the current theme. An application builds its theme manager here.
3. `set_theme(name)` applies a theme. It raises `ValueError` for a name not in `theme_names()`. The gallery calls it only
   with names from `theme_names()`.
4. **Notifications.**
   - `on_changed(callback)` registers a callback, called with no arguments after every theme change: one the gallery asked for,
     and one the provider made itself (an application manager following the system).
   - Several callbacks may be registered; the provider calls them in order.
   - The gallery re-renders from this notification, not from its own switch.
5. `deactivate()` undoes everything `activate` and `set_theme` changed: style, palette, style sheet **and font**, plus the
   colour scheme if it set one.
   - The original style is read in `activate`. While an application style sheet is set, `QApplication.style().name()` is empty,
     so it is read with the style sheet briefly cleared, as `BuiltinThemes` already does.
   - The built-in provider calls its callbacks synchronously inside `set_theme`, so `GalleryWindow.set_theme` has re-rendered by
     the time it returns, as the existing tests expect. A provider may also call them later; the window does not rely on timing.
   - `deactivate` clears the registered callbacks, so no callback is called again; a provider reused by a second `run()` starts
     with none.
6. **A style sheet needs a palette.** A provider that sets an application-wide style sheet also sets a matching `QPalette`. The
   gallery chrome is drawn from palette roles, and a style sheet alone leaves `QApplication.palette()` unchanged.
7. Every method is called on the main thread, and callbacks must be called on it too.

**`BuiltinThemeProvider`** (`themes/builtin_theme_provider.py`) replaces `BuiltinThemes`. It is the same code with the protocol's
method names, plus:
- the callback list;
- the System theme of §3;
- `tokens()` (§2) and `color_scheme()`.

It is exported from the package root. `BuiltinThemes` is removed, since it was never public; the tests move to the new class
with a mechanical rename, and `themes.names`/`themes.current` become `theme_names()`/`current_theme()`.

**The window** (`GalleryWindow(registry, theme_provider, ...)`; the second positional parameter keeps its position, now typed
`ThemeProvider`). It registers one callback, which checks `shiboken6.isValid(self)` first and never raises, because a provider can
outlive a window (two windows in one test, or `run()` twice with one provider):
- **Theme switch.** It fills the switch from `theme_names()` and selects `current_theme()`.
  - Choosing a theme calls `set_theme`.
  - The provider's notification then sets the switch to `current_theme()` inside a `QSignalBlocker`, reads the tokens and colour
    scheme, and re-renders the preview.
- **A failing provider.** Every provider call (`set_theme`, `tokens`, `color_scheme`, `current_theme`) is wrapped. An exception is
  logged with `exc_info`, and the window then:
  - shows the error panel titled "Theme provider failed: <Type>: <message>", with the traceback;
  - resets the switch to the provider's current theme, or leaves it as it was if that also fails;
  - keeps running.
- `Ctrl+T` (next theme) goes through the same path.
- `set_theme(name)` on the window is unchanged for callers.

**`run`** (`app.py`) becomes public and is exported from the package root:

```python
def run(registry=None, argv=None, *, theme=None, load_errors=(), reload=None, theme_provider: ThemeProvider | None = None) -> int
```

`reload` stays internal and is documented as such; `theme_provider` is new and public. The changelog lists `run`, `ThemeProvider`
and `BuiltinThemeProvider` under `### Added`, and `BuiltinThemes`' removal needs no entry because it was never public.

- The provider defaults to a new `BuiltinThemeProvider()`.
- If `theme` is given, it must be in `theme_provider.theme_names()`; otherwise `run` raises `ValueError` listing the names. It is
  applied with `set_theme` after `activate`.
- Before `activate`, `run` snapshots the application's style name (read under any style sheet as above), palette, style sheet and
  font. After `deactivate` (in `finally`, guarded), it compares and logs a warning naming each property the provider did not
  restore. It does not fix them: that would hide a provider bug.
- If `activate` raises, `run` logs the error, deactivates and re-raises. The gallery cannot open without a theme.

## 2. Design tokens (#27)

- **`StoryContext.tokens`** is a keyword-only field after `actions`, `Mapping[str, Any]`, defaulting to an empty mapping. It is
  stored as a `MappingProxyType` copy in `__post_init__`, as `args` is, and is excluded from `repr`.
- **Reading tokens.** The window calls `provider.tokens()` after activation and after every change notification, and passes the
  result on every render until the next one. A provider without `tokens` yields `{}`; a failing `tokens()` is reported as in §1
  and yields `{}`.
- **No implicit calls.** The gallery never calls anything on the story's widget. A widget with a `set_tokens`-style method gets
  its tokens from the story: `widget.set_tokens(ctx.tokens)`. The README and the guide show this.
- **Built-in tokens.** `BuiltinThemeProvider.tokens()` returns `#rrggbb` strings taken from the current application palette's
  Active group:

  | Token | Palette role |
  | --- | --- |
  | `window` | `Window` |
  | `window_text` | `WindowText` |
  | `base` | `Base` |
  | `alternate_base` | `AlternateBase` |
  | `text` | `Text` |
  | `button` | `Button` |
  | `button_text` | `ButtonText` |
  | `highlight` | `Highlight` |
  | `highlighted_text` | `HighlightedText` |
  | `accent` | `Accent` |
  | `border` | `Mid` |
  | `placeholder_text` | `PlaceholderText` |

  Reading the application palette means System (§3) gets real values too. The table is documented in the README.
- **Example.** `Display/Token Badge`, in `examples/display_stories.py`: a small `QWidget` subclass defined in the module, which
  paints a rounded badge in `accent` with `highlighted_text` text and a `border` outline. The story passes `ctx.tokens` to it, and
  it repaints on a theme switch because the story re-renders.

## 3. The System theme (#30)

- **The theme.** `BuiltinThemeProvider.theme_names()` returns `("Light", "Dark", "System")`. Light stays the default.
- **Applying System.** It restores the style, palette and style sheet found at `activate`, and puts back the colour scheme found
  at `activate` with the existing `_restore_color_scheme` (unset the override, then force the original only if it differs), so a
  scheme the application forced stays forced and one that followed the system follows it again.
  - It connects `QStyleHints.colorSchemeChanged` while System is active, and disconnects it when switching away and on
    `deactivate`.
  - A scheme change calls the callbacks with `QTimer.singleShot(0, ...)`, not directly: Qt emits `colorSchemeChanged` before it
    updates the application palette on platforms that do, so tokens read inside the signal would be stale.
  - Offscreen, `setColorScheme` does nothing, `colorScheme()` is `Unknown` and the signal never fires. Tests simulate a change with
    `app.styleHints().colorSchemeChanged.emit(Qt.ColorScheme.Dark)` (available on 6.8), and set a non-Fusion style
    (`app.setStyle("Windows")`) before `activate`, because the offscreen default is already Fusion.
- **Switching back** to Light or Dark reapplies Fusion and the theme's palette, exactly as today.
- **`StoryContext.color_scheme`.** A keyword-only `Qt.ColorScheme` field, default `Qt.ColorScheme.Unknown`. The window fills it
  from the provider's optional `color_scheme()`, or else from a heuristic: `Dark` when the application palette's `Window` colour
  has lightness below 128, otherwise `Light`. The built-in provider returns:
  - `Light` and `Dark` for those themes;
  - `QStyleHints.colorScheme()` for System, and the palette heuristic when that is `Unknown`.
- **Limitation, documented:** on the offscreen platform, and on platforms without a colour-scheme setting, System is whatever Qt
  defaults to.

## 4. Choosing a provider (#28)

**Sources, highest first**
1. `--theme-provider module:attribute` on the command line.
2. `theme_provider = "module:attribute"` in `[tool.pyside6-storybook]`.
3. `BuiltinThemeProvider()`.

`--theme NAME` and `theme = "NAME"` choose the starting theme the same way; the command line wins. `--theme` loses its argparse
`choices` and is validated after the provider loads.

`discovery/sources.py`: `_KNOWN_KEYS` gains `theme_provider` and `theme`, validated as non-empty strings, and `StorySources` gains
keyword-only `theme_provider: str | None = None` and `theme: str | None = None`. Unlike `stories`, these two keys are read from
`pyproject.toml` **also when the command line names targets**: the project's theme applies to whatever stories are opened.

**Loading** (`themes/provider_loader.py`): `load_theme_provider(spec: str) -> ThemeProvider`.
- The spec is `module:attribute`, and the attribute may be dotted (`app.theming:Theme.provider`).
- The module is imported after `put_on_sys_path` and after the `QApplication` exists, so the configured `pythonpath` and the
  working directory apply, as for stories.
- The attribute is an instance, or a callable taking no arguments that returns one. A callable is called once the
  `QApplication` exists. A class passes `isinstance(cls, ThemeProvider)` (its methods are attributes), so the loader calls the
  attribute when it is a class (`isinstance(obj, type)`) or when it fails the check, and checks the result.
- `isinstance` only says yes or no, so the "missing methods" message is built by checking `callable(getattr(obj, name, None))` for
  each protocol method.
- The loader records the `sys.modules` names that importing and calling the provider added, and returns them with the provider.

**Errors.** Each is a `ThemeProviderError` whose message names the spec. The command line prints it and exits 1, and never falls
back to the built-in themes.

| Failure | Message |
| --- | --- |
| Malformed spec | "expected 'module:attribute'" |
| Module not found, or raises while importing | names the module, with the exception's message |
| Missing attribute | names the attribute and the module |
| Callable raises | names the callable, with the exception's message |
| Result is not a `ThemeProvider` | names the missing methods |
| Unknown `--theme` or `theme` | lists the provider's theme names |

**`--list`** prints `pyside6-storybook: theme provider <spec or "built-in"> (themes: A, B)` on standard error, after the line about
where the stories came from. Reading the names does not activate the provider (§1, rule 1).

**Reload.** The provider and its modules are not reloaded. Otherwise a story edit would re-import the application's theme module,
and the stories and the provider would hold different copies of its singletons (the theme manager). `ReloadSession` gains a
keyword-only `keep: Collection[str] = ()`: the module names the provider loader recorded. They are excluded from the modules a
reload drops and from the watched files, so editing the provider triggers nothing. The README says to restart the gallery after
editing the provider.

**`run` from code** takes `theme_provider=` (§1). The three ways (code, command line, `pyproject.toml`) are documented together.

## 5. The chrome under an application style sheet (#29)

**Policy.** The chrome accepts the application's styling, so it looks like the application. It guarantees only that its own text,
selection and focus indicators stay readable. Qt cannot exempt a subtree from an application style sheet, and the gallery does not
try.

**Marking the chrome**
- **Names.** Every widget the gallery creates gets an object name with the prefix `sbk`, in camel case: `storySidebar` becomes
  `sbkStorySidebar`, `previewSurface` becomes `sbkPreviewSurface`, and so on. That is about 40 names and some 170 test references,
  renamed in one mechanical commit. The README lists them, and a test checks the README list against the widgets of a shown
  window. `#sbkName` is the strongest selector an application can use.
- **The property.** The dynamic property `sbkChrome = True` goes only on widgets an application might style and that contain no
  story widget:
  - the sidebar and its children: search field, tree, the tree's viewport;
  - the canvas control rows and their combo boxes, spin boxes, buttons and labels;
  - the tab bars, but not the tab widgets;
  - the side pane and everything in it: theme switch, side tab bar, controls panel and every editor, Actions panel;
  - the Docs panel's widgets, the status bar's widgets, the error panel and the empty-state label.
  The error panel and the empty-state label live inside the surface but are chrome.
- **Never on the surface's ancestors.** The window, the splitter, the preview pane, the preview tab widget, the canvas, the scroll
  area and its viewport, the stack and the surface get names only. Otherwise `*[sbkChrome="true"] QPushButton` would match a
  story's buttons.
- **Setting it.** One helper, `gui/chrome.py::mark_chrome(widget, name)`, sets the name and the property. Widgets made after
  polish (editors, Docs content, the error panel) call it in their constructors. When the property is set after polish, the helper
  calls `style().unpolish(widget)` and `style().polish(widget)`. The property is not inherited, so internal children (tab bars,
  viewports) are marked explicitly.
- **Specificity, documented.** `QPushButton[sbkChrome="true"]` beats `QPushButton` and `QWidget QPushButton`, but loses to
  `QPushButton[flat="false"]` and to pseudo-state rules such as `:hover` or `::tab:selected`. The guide therefore recommends
  type-plus-property selectors or `#sbkName`, and restating the same pseudo-states.

**Inventory of colours.** The chrome sets no colours of its own today; everything is a palette role. Only one place needs code:
- **Sidebar selection.** An application rule may set the selected row's background with `selection-background-color` (which does
  reach the option palette's `Highlight`) or with `QTreeView::item:selected { background: ... }` (which does not: the option still
  holds the old `Highlight`). A `QStyledItemDelegate` therefore finds the real background by drawing `PE_PanelItemViewItem` with the
  option into a small `QImage` and sampling its centre, cached per (palette key, state, size). It paints the selected text in
  `pick_contrasting_text(<that colour>)`. When the application's rule also sets `color` for selected items, the style sheet wins
  and the delegate's colour is ignored; the guide says so.
- **Everything else** (the error panel, labels, the checkerboard in `Base` and `Mid`) is covered by the palette contract and checked
  by the grab tests. No widget-local style sheet is added: the library's rules forbid them.

**Test style sheet.** `tests/fixtures/aggressive.qss` sets the selection both ways (`selection-background-color` on the views
and `::item:selected { background }` on the tree) and restyles `QWidget`, `QComboBox`, `QListView`, `QTreeView`, `QPushButton`,
`QTabBar`, `QLineEdit`, `QLabel` and `QScrollArea`: dark backgrounds, a saturated selection colour, and an 18 pt font. A test
provider (`tests/fake_providers.py`) applies it with a matching palette in two themes. Under it, in each theme:
- sidebar selection text, control labels and the error panel title reach 4.5:1, measured on grabs;
- no chrome label is clipped;
- a rule written with `*[sbkChrome="true"]` restyles a chrome widget and leaves a story widget alone.

**Docs.** The README's theming section shows the palette requirement with two screenshots: a provider without a palette, where the
chrome is unreadable, and with one. They are rendered by a script and committed to `docs/images/`.

## 6. Guide and worked example (#31)

- **`examples/themed_app/`** at the repository root. It is not in the wheel, and nothing in `src/` imports it. It contains:
  - `themed_app/theme_manager.py`: two themes, Paper and Ink, each a style sheet, a `QPalette` and a token dict. Signals:
    `themeChanged`.
  - `themed_app/widgets.py`: `PillButton`, styled by the style sheet through an object name, and `Gauge`, custom-painted from
    tokens with a `set_tokens` method.
  - `themed_app/stories/`: `pill_stories.py` and `gauge_stories.py`.
  - `themed_app/storybook.py`: `ThemedAppProvider`, about 40 lines, adapting the manager to `ThemeProvider`. Its `provider`
    attribute is a callable returning one.
  - `pyproject.toml` with `[tool.pyside6-storybook]`: `stories`, `pythonpath = ["."]` and
    `theme_provider = "themed_app.storybook:provider"`.
- **Tests**, `tests/test_themed_app.py`, so CI runs the example on every push:
  - core, in-process: `cli.main(["--list"])` with `monkeypatch.chdir(<the example folder>)` and the `stories` fixture; the output
    names the provider and both themes;
  - core, in-process: each story renders in both themes, and switching theme restyles both widgets (pixel checks);
  - `full`: the installed `pyside6-storybook --list` in that folder, in a subprocess with a timeout.
- **`docs/theming.md`**, the guide:
  - the built-in themes;
  - when to write a provider;
  - the protocol method by method, and the contract (§1);
  - tokens in stories;
  - the System theme;
  - selecting a provider;
  - the chrome policy (§5);
  - troubleshooting:
    - the switch does nothing: an application style sheet overrides the built-in palettes;
    - the chrome is unreadable: the provider sets a style sheet but no palette;
    - the font stays changed after closing: teardown doesn't restore it;
    - a provider change doesn't re-render: `on_changed` is never called.
- The README links the guide.

## 7. Pull requests

Six stacked PRs, one per issue. The mass rename comes second, so later review fixes do not have to be merged through it:

| # | Issue | Branch | Adds |
| --- | --- | --- | --- |
| 1 | #26 | `claude/pyside6-storybook-theme-provider` | protocol, `BuiltinThemeProvider`, window and `run` integration, public `run` |
| 2 | #29 | `claude/pyside6-storybook-chrome-styling` | `sbk` names, `mark_chrome`, selection delegate, aggressive style sheet tests |
| 3 | #27 | `claude/pyside6-storybook-design-tokens` | `StoryContext.tokens`, built-in tokens, Token Badge example |
| 4 | #30 | `claude/pyside6-storybook-system-theme` | System theme, `StoryContext.color_scheme` |
| 5 | #28 | `claude/pyside6-storybook-provider-config` | `--theme-provider`, `theme_provider`/`theme` keys, loader, `keep=`, `--list` |
| 6 | #31 | `claude/pyside6-storybook-themed-app` | `examples/themed_app/`, `docs/theming.md`, README links |

**Changelog.** Every PR adds its entries under `## [Unreleased]`: the new public names (`ThemeProvider`, `BuiltinThemeProvider`,
`run`, `StoryContext.tokens` and `color_scheme`), the command-line flag and keys, the System theme, and the renamed object names
(`### Changed`).

**Merging.** Squash-merging a stacked PR hides the commits the next branch already contains, and the next PR then conflicts.
Every PR description therefore asks for a merge commit ("Create a merge commit") for the whole stack.

## 8. Out of scope

The issues' own out-of-scope lists apply, plus:
- reloading the provider on file changes;
- several providers at once;
- editing tokens in the gallery;
- a token schema.
