# Theming hook (milestone 4): design spec

Status: draft. Covers issues #26 (`ThemeProvider` protocol), #27 (design tokens), #30 ("System" theme), #28 (choosing a provider),
#29 (chrome under an application style sheet) and #31 (guide and worked example). The issues hold the scope and acceptance
criteria; this document fixes the decisions they leave open and how the six pull requests fit together. Where this spec and an
issue differ, the issue is updated to match.

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
   - After `deactivate`, no callback is called again.
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
`ThemeProvider`):
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
- **Applying System.** It restores the style, palette and style sheet found at `activate`, and unsets the colour-scheme override
  (`QStyleHints.unsetColorScheme()`) so the platform decides.
  - It connects `QStyleHints.colorSchemeChanged` while System is active, and disconnects it when switching away and on
    `deactivate`.
  - A scheme change calls the callbacks, so the gallery re-renders.
  - On some platforms Qt then also updates the application palette. The tokens are re-read in the callback, so they follow.
- **Switching back** to Light or Dark reapplies Fusion and the theme's palette, exactly as today.
- **`StoryContext.color_scheme`.** A keyword-only `Qt.ColorScheme` field, default `Qt.ColorScheme.Unknown`. The window fills it
  from the provider's optional `color_scheme()`, or else from a heuristic: `Dark` when the application palette's `Window` colour
  has lightness below 128, otherwise `Light`. The built-in provider returns:
  - `Light` and `Dark` for those themes;
  - `QStyleHints.colorScheme()` for System, which can be `Unknown`.
- **Limitation, documented:** on the offscreen platform, and on platforms without a colour-scheme setting, System is whatever Qt
  defaults to.

## 4. Choosing a provider (#28)

**Sources, highest first**
1. `--theme-provider module:attribute` on the command line.
2. `theme_provider = "module:attribute"` in `[tool.pyside6-storybook]`.
3. `BuiltinThemeProvider()`.

`--theme NAME` and `theme = "NAME"` choose the starting theme the same way; the command line wins. `_KNOWN_KEYS` in
`discovery/sources.py` gains `theme_provider` and `theme`, validated as non-empty strings.

**Loading** (`themes/provider_loader.py`): `load_theme_provider(spec: str) -> ThemeProvider`.
- The spec is `module:attribute`, and the attribute may be dotted (`app.theming:Theme.provider`).
- The module is imported after `put_on_sys_path` and after the `QApplication` exists, so the configured `pythonpath` and the
  working directory apply, as for stories.
- The attribute is an instance, or a callable taking no arguments that returns one. A callable is called once the
  `QApplication` exists.
- The result must pass `isinstance(obj, ThemeProvider)`.

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

**Reload.** The provider is not reloaded (#24's reload does not recreate it), even when its module is under the project. The README
says to restart the gallery after editing the provider.

**`run` from code** takes `theme_provider=` (§1). The three ways (code, command line, `pyproject.toml`) are documented together.

## 5. The chrome under an application style sheet (#29)

**Policy.** The chrome accepts the application's styling, so it looks like the application. It guarantees only that its own text,
selection and focus indicators stay readable. Qt cannot exempt a subtree from an application style sheet, and the gallery does not
try.

**Marking the chrome**
- Every chrome widget the gallery creates (window, sidebar, search, tree, tabs, canvas controls, scroll areas, side pane, theme
  switch, controls panel, Docs and Actions panels, status bar) gets:
  - an object name with the prefix `sbk`, in camel case: today's `storySidebar` becomes `sbkStorySidebar`, `previewSurface`
    becomes `sbkPreviewSurface`, and so on;
  - the dynamic property `sbkChrome = True`.
- A style sheet cannot match an object-name prefix, but it can match a property. `*[sbkChrome="true"]` is the documented selector
  for "the gallery's chrome", and a rule with it outweighs the application's plain type selectors, so an application can exclude
  the chrome from one of its rules by restating it for the chrome.
- The preview surface's descendants (the story's widget) never get the property, and `sbkPreviewSurface` itself keeps the
  property but is styled by no gallery rule.
- The renamed object names are listed in the README. The tests move to the new names; the change is mechanical.

**Colours the gallery sets itself**, computed at paint time against the background actually drawn:
- **Sidebar selection.** A `QStyledItemDelegate` paints selected rows' text in `pick_contrasting_text(<the selection background
  the style will paint>)`. That background comes from the option's palette `Highlight`, which `QStyleSheetStyle` updates from
  `selection-background-color`.
- **Error panel title** and **checkerboard size label**, and any other gallery-set text: the same rule.
- **The checkerboard** keeps its palette colours (`Base` and `Mid`).

**Test style sheet.** `tests/fixtures/aggressive.qss` restyles `QWidget`, `QComboBox`, `QListView`, `QTreeView`, `QPushButton`,
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
- **Tests**, `tests/test_themed_app.py`, which run the example the way CI does:
  - `pyside6-storybook --list` in that folder, in a subprocess with a timeout. Its output names the provider and both themes.
  - In-process, through the `stories` fixture: each story renders in both themes, and switching theme restyles both widgets
    (pixel checks).
  - The subprocess test is `full`; the in-process test is core.
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

Six stacked PRs, one per issue:

| # | Issue | Branch | Adds |
| --- | --- | --- | --- |
| 1 | #26 | `claude/pyside6-storybook-theme-provider` | protocol, `BuiltinThemeProvider`, window and `run` integration, public `run` |
| 2 | #27 | `claude/pyside6-storybook-design-tokens` | `StoryContext.tokens`, built-in tokens, Token Badge example |
| 3 | #30 | `claude/pyside6-storybook-system-theme` | System theme, `StoryContext.color_scheme` |
| 4 | #28 | `claude/pyside6-storybook-provider-config` | `--theme-provider`, `theme_provider`/`theme` keys, loader, `--list` |
| 5 | #29 | `claude/pyside6-storybook-chrome-styling` | `sbk` names and property, contrast delegate, aggressive style sheet tests |
| 6 | #31 | `claude/pyside6-storybook-themed-app` | `examples/themed_app/`, `docs/theming.md`, README links |

**Merging.** Squash-merging a stacked PR hides the commits the next branch already contains, and the next PR then conflicts.
Every PR description therefore asks for a merge commit ("Create a merge commit") for the whole stack.

## 8. Out of scope

The issues' own out-of-scope lists apply, plus:
- reloading the provider on file changes;
- several providers at once;
- editing tokens in the gallery;
- a token schema.
