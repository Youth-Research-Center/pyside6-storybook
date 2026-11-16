# Gallery UI (milestone 3): design spec

Status: draft. Covers issues #45 (icons), #19 (sidebar tree and search), #23 (Docs tab), #20 (canvas toolbar), #21 (zoom), #22
(Actions panel), #24 (hot reload) and #25 (keyboard and accessibility). The issues hold the user-facing scope and acceptance
criteria; this document fixes the decisions they leave open, records the decisions three of them ask for (#21, #22, #24), and
defines how the eight pull requests fit together. Where this spec and an issue differ, the issue is updated to match.

## Goals and constraints

- **Stories written for milestones 1 and 2 keep working unchanged.** New public parameters are keyword-only and come after the
  existing ones (`AGENTS.md`).
- **Stock Qt widgets and `PySide6-Essentials` only.** QtSvg, which the icons need, is part of it. No new runtime dependency.
- **Chrome colours come from palette roles**, so everything follows the theme. Icons are tinted from palette roles too (#45).
- **The window stops growing in one file.** `gui/window.py` today builds every pane itself. Each new pane is its own widget in
  `gui/`, one module per widget, and the window only assembles them and routes signals.
- **Library code takes a `StoryRegistry` as an argument** (`AGENTS.md`). Hot reload replaces the window's registry through a
  method, it does not read the global.
- **Accessibility from the start.** Every new interactive control gets an accessible name, is reachable with Tab, and has its
  contrast checked in both built-in themes. #25 then audits the whole window.

## Window layout after milestone 3

```
+--------------------------------------------------------------------------------------------------+
| Help                                                                                             |
+--------------------+----------------------------------------------------+------------------------+
| [search........ x] | [ Canvas | Docs ]                                    | Theme [Light   v]      |
| v Buttons          | Background [Window v] Size [Fit v] 320x480  - 100% + | [ Controls | Actions ] |
|   v Push Button    | +------------------------------------------------+ | Text      [Push me  ]  |
|       Default      | |                                                | | Enabled   [x]          |
|       Disabled     | |                story preview                   | | ...                    |
|   Check Box        | |                                                | |                        |
| > Display          | +------------------------------------------------+ |                        |
+--------------------+----------------------------------------------------+------------------------+
| Reloaded 14:02:11                                                                                 |
+--------------------------------------------------------------------------------------------------+
```

- **Sidebar** (`gui/sidebar.py`, #19): search field and story tree.
- **Preview pane**: a `QTabWidget` with "Canvas" (`gui/canvas.py`: toolbar, scrolled surface, zoom; #20, #21) and "Docs"
  (`gui/docs_panel.py`, #23). The heading with the story id stays above the tabs.
- **Side pane**: the theme switch, then a `QTabWidget` with "Controls" (today's controls panel) and "Actions"
  (`gui/actions_panel.py`, #22).
- **Status bar**: reload status (#24).
- **Menu bar**: one "Help" menu with "Keyboard shortcuts" (#25). Menus are plain text, without icons (#45 conventions).

## 1. Icons (#45)

PandaPlot's pipeline is ported, as the issue lists, with these decisions:

- **Locations.**
  - The manifest, bundle and licence live in `src/pyside6_storybook/resources/icons/`: `icon_manifest.toml`, `icon_bundle.json`
    and `licenses/phosphor-LICENSE.txt`.
  - `THIRD_PARTY_NOTICES.md` goes at the repository root.
  - The build script is `scripts/icons/build_icon_bundle.py` plus the `scripts/icons/icon_bundle/` package. It is development
    only: hatchling's wheel target already includes only `src/pyside6_storybook`, so the script stays out of the wheel. The
    manifest also ships in the wheel; it is small and documents the bundle.
- **Pinning.** Phosphor `@phosphor-icons/core` 2.1.1 with PandaPlot's sha512 integrity, `weights = ["regular"]`, no
  `[overrides]` section and no Lucide support.
- **Renderer** `src/pyside6_storybook/gui/icons.py`, internal. It ports `icon_library.py` and `themed_icons.py` into one
  module:
  - `icon_svg(name)`: raises `KeyError` naming the manifest path and the script.
  - `build_icon(name, color, *, size=16, disabled_color=None, selected_color=None) -> QIcon`.
  - `clear_icon_cache()`.
  - `IconRole`: an enum whose values are `QPalette.ColorRole` members, `TEXT=WindowText`, `MUTED=PlaceholderText`,
    `ACCENT=Highlight`, `ON_ACCENT=HighlightedText`.
  - `palette_icon(name, *, role=IconRole.TEXT, palette=None, size=16) -> QIcon`: the Normal state uses the role's Active colour,
    Disabled uses the role's Disabled-group colour, Selected uses `HighlightedText`. `palette` defaults to `QApplication.palette()`.
  - `ActionIcons(*, size=16)`: `bind(target, name, *, role=IconRole.TEXT)` and `retint(palette=None)`. Targets are `QAction` or
    `QAbstractButton`. Deleted targets (`shiboken6.isValid`) are dropped on `retint`.
- **When icons retint.** `GalleryWindow` owns one `ActionIcons`. It calls `retint()` from `changeEvent` on
  `QEvent.Type.ApplicationPaletteChange` and on `QEvent.Type.PaletteChange`. So a switch through `BuiltinThemes`, or later a
  theme provider (#26), retints every chrome icon without the window being told by name.
- **Contrast.** Each chrome icon is drawn on a known background: a tool button on `Window`, the search field's icon on `Base`.
  Its tint must reach 3:1 against that background in both themes. A test checks every `ActionIcons` binding of a shown window.
  `MUTED` (`PlaceholderText`) is only for decorative icons next to text that carries the meaning (the search field's
  magnifying glass); the contrast test still requires 3:1 for them.
- **Initial icon set.** Exactly the icons milestone 3 uses: `magnifying-glass`, `x`, `copy`, `trash`, `warning`,
  `arrows-clockwise`, `magnifying-glass-plus`, `magnifying-glass-minus` and `arrow-counter-clockwise` (reset zoom), plus `question`
  for Help if it gets a button. PR 1 bundles all of them, so later PRs do not regenerate the bundle.
- **CI.** The lint job runs `uv run --no-sync python scripts/icons/build_icon_bundle.py --check`, with `.icon-cache/` cached by
  `actions/cache` keyed on the manifest's hash. `.icon-cache/` is git-ignored.
- **Tests.**
  - `tests/icon_testing.py`: `strongest_pixel(icon, size)` and `assert_tinted(icon, color)`, ported from PandaPlot.
  - The build script gets its own tests, with an injected fetcher; no network in tests.
- **Error panel.** It gets a `warning` icon next to its title, tinted `TEXT`. Error is not a palette role (the issue says so).

## 2. Sidebar tree and search (#19)

`gui/sidebar.py` holds `StorySidebar(QWidget)`.

**Contents**
- A `QLineEdit` with a `magnifying-glass` leading action and Qt's own clear button (`setClearButtonEnabled`).
- A `QTreeView` over a `QStandardItemModel`, filtered by a `QSortFilterProxyModel` subclass.
- A placeholder label shown instead of the tree when nothing matches: "No stories match 'xyz'."

**Tree shape**
- One branch per id segment except the last; stories are leaves, in registration order within each branch. Branches appear in
  the order their first story registered.
- **Collapsing a one-story component.** A branch below the top level whose only child is a story leaf is shown as that story's
  row, with the branch's label. So `Forms/Sign-in Form/Default` alone shows as Forms > Sign-in Form, which opens the story. The
  rule never applies to top-level branches: `Forms/Sign-in Form` stays Forms > Sign-in Form.
- **Load errors.** "Load errors (N)" is a top-level row at the end when there are load errors.
- **Item data.**
  - Story rows hold the story id in a custom role; branch rows hold none.
  - The full id is each story row's tooltip and accessible description.
- Branches start expanded.

**Filtering**
- The filter is a case-insensitive substring match on the full id of story rows.
- Branches never match by themselves. Recursive filtering (`setRecursiveFilteringEnabled(True)`) shows the ancestors of matching
  rows, and the filter expands them.
- **Expansion state.** It is saved when the search text goes from empty to non-empty, and restored when it is cleared. The saved
  set is of branch paths (`"Buttons/Push Button"`), not of model indexes.
- **Acceptance correction.** #19's example, "typing 'spin' leaves only `Inputs/Spin Box`", no longer holds: `Inputs/Double Spin
  Box` also contains "spin". The criterion becomes: typing "double" leaves only `Inputs/Double Spin Box` visible, with Inputs
  expanded, and Enter opens it. The issue is updated.

**Selection and signals**
- `storySelected(str)` is emitted with a story id, and `loadErrorsSelected()` when the "Load errors" row is chosen.
- `select_story(story_id)` selects a row without being told by a click. It returns `False` when the id is not shown.
- If the filter hides the selected story, the selection is kept in the source model and the preview stays. When it matches
  again, it is shown selected.
- `set_registry(registry, *, load_errors=())` rebuilds the model and keeps the selected id selected if it still exists (#24).

**Keyboard**
- `Ctrl+K` focuses the search field and selects its text.
- `/` does the same, but only reaches the window when the focused widget did not accept the key (section 8).
- In the search field, Down moves focus to the first visible story; Enter opens the first visible story; Escape clears the text
  and, when it is already empty, moves focus to the tree.
- In the tree, Up and Down move between visible rows, Enter opens the current story, Left and Right collapse and expand
  (`QTreeView` default), and Escape clears the search.

**Accessibility**
- Accessible names: the field "Search stories", the tree "Stories".
- `Highlight` and `HighlightedText` already reach 4.5:1 in both themes, and the built-in palettes set the same colours in the
  Active and Inactive groups, so an unfocused tree keeps a readable selection. A test checks the Inactive pair.

## 3. Docs tab (#23)

`gui/docs_panel.py` holds `DocsPanel(QWidget)`, inside a `QScrollArea`.

**`show_story(story, registry)`** builds, top to bottom:
1. **Component description**: the story module's docstring, if any, as a `QLabel` with `PlainText` format, word wrap and
   selectable text.
2. **Story docstring** (`story.doc`): same widget. There is no heading when it is empty, so no empty sections appear.
3. **Controls table**: a read-only `QTableWidget` with columns Name, Type, Default and Range or options. The values come from a
   pure function `controls_rows(controls) -> list[tuple[str, str, str, str]]` in `docs_panel.py`, which the tests check directly.
   A story without controls shows "No controls." instead of a table.

   | Control | Type | Default | Range or options |
   | --- | --- | --- | --- |
   | `TextControl` | `text` (`multiline text`) | `repr` of the string | empty |
   | `BoolControl` | `bool` | `True`/`False` | empty |
   | `ChoiceControl` | `choice` | the option | options joined with ", " |
   | `IntControl` | `int` | the number | `minimum..maximum`, plus `step N` when not 1 |
   | `FloatControl` | `float` | the number | `minimum..maximum`, `step` and `decimals` |
   | `ColorControl` | `colour` | the hex string | `with alpha` when `alpha` |
   | `EnumControl` | the enum class's qualified name | the member name | member names joined with ", " |
   | `FileControl` | `file` | the path, or "(none)" | the filter, when set |

   A variant shows its own starting values (`story.default_args()`), not the control defaults, and says so in a caption:
   "Starting values of this variant."
4. **Variants**: for a story with a component (#14), a "Stories of <component>" list of its sibling stories, each a link (a
   `QLabel` with rich text and `LinksAccessibleByKeyboard | LinksAccessibleByMouse`). Activating a link emits
   `storyRequested(str)`, and the window selects that story through the sidebar.
   - Siblings are the registry's stories with the same component that are the base or a variant of the same base.
   - The current story is listed but not linked.
5. **Source**: `inspect.getsource` of the story function, in a read-only `QPlainTextEdit` with the system fixed font
   (`QFontDatabase.systemFont(FixedFont)`) at the application font's point size, no wrap, plus a "Copy" button (`copy` icon and
   text) that puts it on the clipboard.
   - When `inspect.getsource` raises `OSError` or `TypeError`, the panel shows "Source not available for this story." instead.
   - Variants share their base's source.

**Updates.** The window calls `show_story` on every story selection and after a reload, not on control changes: the Docs content
does not depend on control values.

**Text.** Every label and the source view follow the application font; there are no fixed point sizes.

## 4. Canvas toolbar (#20)

`gui/canvas.py` holds `Canvas(QWidget)`. It takes over the preview scroll area, the surface and `_place_preview` from
`gui/window.py`, unchanged in behaviour, and adds a `QToolBar` above them.

**Background**
- A `QComboBox` labelled "Background" with Window (the default, today's look), Base, Alternate Base and Checkerboard.
- The first three set the surface's `backgroundRole`.
- Checkerboard sets the surface's `Window` brush to a texture: 8-pixel squares of the active palette's `Base` and `Midlight`. It
  is rebuilt on `PaletteChange`, so it follows the theme.
- The choice is stored as an enum `CanvasBackground`, not as colours, so a theme switch keeps "Base" meaning the new theme's
  base. That is #20's second acceptance criterion.

**Size**
- A `QComboBox` labelled "Size", in this order:
  1. "Fit": today's behaviour.
  2. The built-in presets: Phone portrait 320 × 480, Phone landscape 480 × 320, Dialog 800 × 600.
  3. The registry's presets.
  4. "Custom…".
- "Custom…" shows two `QSpinBox`es, Width and Height (range 1–10 000), in the toolbar, with an accessible name each.
- **Meaning of a size.** With a size active, the area inside the surface margins is exactly W × H.
  - The surface gets a fixed size of W × H plus its margins, and a `StyledPanel` frame as the visible outline.
  - The scroll area centres it (`setAlignment(AlignCenter)`, `widgetResizable(False)`) and scrolls when it does not fit.
  - The story's layout (§3 of the milestone 2 spec) still applies inside that area. So a `FILL` story is exactly W × H, which is
    #20's acceptance criterion.
- **Size label.** A label shows "W × H" while a size is active, and is hidden for Fit.
- **Registry presets.** New public `SizePreset(name: str, width: int, height: int)`, a frozen dataclass that validates
  positive sizes and a non-blank name, and `StoryRegistry.size_presets: list[SizePreset]`, empty by default and read when the
  window builds the toolbar. A project appends to it, as with `StoryRegistry.decorators`. Both are listed in the changelog.

**Persistence.** The choices live on the `Canvas` for the window's lifetime: switching story, switching theme and reloading
(#24) keep them. They are not saved between runs.

**Toolbar accessibility.**
- The toolbar's controls are widgets added with `addWidget`, which keep their own focus policy.
- The few actions (zoom, §5) use `QToolButton`s with `setFocusPolicy(Qt.FocusPolicy.TabFocus)`, because
  `QToolBar.addAction()` buttons are `NoFocus`.
- Every control has visible text or an accessible name.
- The toolbar is not movable or floatable (`setMovable(False)`), and its `objectName` is "canvasToolbar".

## 5. Zoom (#21)

**Decision: render to a pixmap (option b).**
- The proxy approach (option a) breaks popups, native child windows and some styles inside a `QGraphicsProxyWidget`, and it
  would change the widget the story builds.
- A pixmap keeps the story exactly as it is at 100% and gives exact, sharp pixels when zoomed, which is what zoom is for.
- **The cost:** a zoomed preview is not interactive. The canvas says so in a line under the toolbar while zoomed: "Zoomed
  previews are images; return to 100% to interact."

**Mechanics**
- The scroll area's widget is a `QStackedWidget` with the live surface (page 0) and a zoom label (page 1).
- At 100% page 0 is shown and nothing else changes: no proxy, no image. That is #21's second acceptance criterion.
- At any other level:
  - The canvas grabs the live surface with `QWidget.grab()` at its current size, after `ensurePolished()` and activating its
    layout.
  - It scales the pixmap by the zoom factor with `Qt.TransformationMode.FastTransformation`, so 400% turns a one-pixel border into
    four sharp device pixels, and shows it on page 1.
  - The grab and the label take the device pixel ratio into account: zoom is relative to logical pixels.
- **Updates.** The canvas re-grabs after every preview rebuild (control change, theme change, reload) and on resize of the scroll
  area in Fit mode.

**Levels and controls**
- Levels: 50, 67, 100, 150, 200, 300 and 400%.
- Zoom out, a level label (for example "200%") and Zoom in buttons (`magnifying-glass-minus`, `magnifying-glass-plus`), plus
  "Reset zoom" (`arrow-counter-clockwise`), all in the canvas toolbar.
- The shortcuts `Ctrl++` (also `Ctrl+=`), `Ctrl+-` and `Ctrl+0` work while focus is in the preview pane. `Ctrl`+wheel over the
  canvas zooms one level per 120 units of accumulated `angleDelta().y()`, keeping the remainder.

## 6. Actions panel (#22)

**Public API.** `StoryContext` gains two methods, `log_signal(signal, name=None)` and `log(name, *args)`, and one keyword-only
field `actions: ActionSink | None = None`.
- `ActionSink` is a `Protocol` with `record(name: str, args: tuple[object, ...]) -> None`. It is exported for typing only.
- Without a sink (a plain `StoryContext`, the pytest plugin in milestone 5), both methods do nothing.
- `log_signal` connects the signal to a small slot that calls `record(name or <signal name>, args)`.
  - The signal name comes from `SignalInstance`'s repr when `name` is omitted. When it cannot be found, `log_signal` raises
    `TypeError` asking for `name=`.
  - It returns `None`.

**Decision: no automatic logging in this milestone.** Connecting every signal declared on the widget's class
(`log_signals=True`) floods the panel with `objectNameChanged`, `windowIconChanged` and `customContextMenuRequested` noise from
stock widgets. It also needs per-signature slot handling through `QMetaMethod`. Stories opt in signal by signal, as in the
issue's example. A follow-up issue records the idea.

**The panel** (`gui/actions_panel.py`, `ActionsPanel(QWidget)`)
- A `QTreeWidget` with columns Time (`HH:MM:SS.mmm`), Action and Arguments, newest first.
  - Arguments are shown with `reprlib.Repr` limited to 200 characters per entry.
  - The cap is 500 entries; older ones are dropped.
- A Clear button (`trash` icon and text).
- **Stale entries.** The window passes each render a sink bound to a generation number. Entries from an older generation, from a
  widget awaiting deferred deletion, are ignored.
- **Clearing.** The log is cleared when another story is selected (or after a reload selects a different one), and kept when the
  same story re-renders after a control or theme change.
- **Connections.** PySide disconnects a signal connected to a Python callable when the sender is destroyed. The sink keeps no
  reference to the widget, so nothing stays connected to a dead preview. A test checks that a deleted widget leaves no
  connection by emitting through a surviving object.
- **Announcements.** A `QLabel` under the tree with `setAccessibleName("Actions status")` holds "N actions logged". It is updated
  at most once per 500 ms by a single-shot timer, and sends `QAccessibleEvent(QAccessible.Event.NameChanged)`, so a burst is
  announced once.
- **Example.** `Buttons/Push Button/Default` logs `clicked`, and `Inputs/Slider` logs `valueChanged`.

## 7. Hot reload (#24)

**Decision: drop the project's modules and load again into a fresh registry (option b).**
- `importlib.reload` (option a) leaves old classes alive in modules that imported them, and does not reload dependents in order.
- A child process (option c) cannot show the preview inside this window without a cross-process widget mechanism.
- Option b re-executes everything the project owns, in import order, so an edited widget class is picked up the same way as an
  edited story.

**Mechanics** (`discovery/reload.py`, internal, Qt-free and testable without a window)
- `ReloadSession(targets, *, cwd, pythonpath)` records what to reload. `reload() -> LoadResult`:
  1. **Find the project modules.** These are every `sys.modules` entry whose `__file__` resolves under `cwd` or a `pythonpath`
     entry, excluding:
     - files under the library's own package;
     - paths with a part named `site-packages`, `dist-packages`, `.venv`, `venv`, `node_modules`, or starting with `.`.
  2. **Snapshot** those entries and `registry_module.default_registry`.
  3. **Reset.** Remove the entries from `sys.modules`, set `registry_module.default_registry = StoryRegistry()`, call
     `importlib.invalidate_caches()`, and run `load_stories(targets, cwd=cwd)`.
  4. **Decide.** The reload is accepted when every source in the new result's errors was also failing in the last accepted
     result. Otherwise it is rejected: the snapshot is restored (modules and `default_registry`), and the result is returned with
     `accepted=False`.
- **Return value.** `ReloadResult(load: LoadResult, accepted: bool, new_errors: tuple[LoadError, ...])`.

**Watching** (`gui/reload_watcher.py`, `ReloadWatcher(QObject)`)
- A `QFileSystemWatcher` on the files of the project modules, plus the folders of folder targets, so a new story file triggers a
  reload.
- After every event it re-adds the paths that still exist, because editors that save by renaming drop the watch.
- Events are debounced with a 300 ms single-shot `QTimer`. One reload runs per burst, never two at once.
- It emits `reloaded(ReloadResult)`.

**Applying a reload** (window)
- **Accepted:** `GalleryWindow.set_registry(registry, *, load_errors)` refreshes the sidebar.
  - It re-selects the same story id. If the id is gone, it selects the story that took its row position, else the previous row,
    else nothing.
  - It rebuilds the controls panel with the previous values where a control of the same name exists and accepts the value
    (`coerce`), and the story's starting values otherwise.
  - It re-renders. Theme and canvas settings are window state and are untouched.
  - The Docs tab is refreshed.
- **Rejected:** the registry is unchanged. The preview shows the new errors in the error panel (the existing load-errors format),
  and the next accepted reload replaces the error panel with the story.
- **Status bar.** A `QLabel` in the status bar shows "Reloaded 14:02:11" or "Reload failed 14:02:11: 1 story source failed to
  load". It has an `arrows-clockwise` or `warning` icon and an accessible name, "Reload status".

**Command line**
- The command line passes a `ReloadSession` to `run()` through a new keyword-only parameter, internal like `run`. `--no-reload`
  turns it off. `--list` never reloads.
- Code that calls `run(registry)` directly gets no reload, because there are no targets to reload.

**Tests**
- `tests/test_reload.py` uses the `stories` fixture and a temporary project. It covers:
  - editing a story's text;
  - adding a story;
  - removing a story;
  - editing a widget class in an imported module;
  - a syntax error, then the fix.
- The watcher is driven through `ReloadWatcher.trigger_now()`, a test hook that skips the debounce, in most tests. One test
  edits a file and waits for the watcher with `qtbot.waitUntil(..., timeout=5000)`.
- File modification times are bumped explicitly (`os.utime`), because some file systems have one-second resolution.

## 8. Keyboard navigation and accessibility (#25)

The last PR audits the whole window. The earlier PRs already follow the rules below for what they add.

**Tab order and panes**
- The tab order is: search, tree, canvas tabs, canvas toolbar, preview, side pane (theme switch, side tabs, controls).
- `F6` and `Shift+F6` cycle focus between the panes (sidebar, preview pane, side pane): to the pane's last focused widget, or
  else its first.
- **Accessible names.**
  - Panes: "Stories", "Preview" and "Controls and actions".
  - The preview surface: "Preview of <story id>".
  - Every chrome control has a name. A test walks all focusable chrome widgets, everything outside the story's own widget, and
    fails on an empty name.

**Shortcuts**
- `Ctrl+K` and `/`: focus search.
- `Alt+Down` and `Alt+Up`: next and previous story (visible rows only).
- `Ctrl+T`: next theme.
- `F6` and `Shift+F6`: switch pane.
- The zoom shortcuts of §5.
- Help > "Keyboard shortcuts" (`F1`) opens a `QDialog` listing them, parented to the window and deleted after it closes.
- **`/` is not a `QShortcut`.**
  - The window handles it in `keyPressEvent`, which Qt reaches only when the focused widget did not accept the key. A
    `QLineEdit`, spin box or editable combo box types the character, including editors inside the previewed story.
  - It also checks the focus widget's class before acting.
  - The other shortcuts use a modifier, so they cannot collide with typing.

**Focus**
- A preview rebuild never moves focus. When a control edit rebuilds the preview, focus stays on the editor.
- The old preview widget is hidden before it is deleted, so if it had focus, focus goes to the canvas, not to a random widget.

**Contrast**
- Tests check `contrast_ratio` in both themes:
  - focus ring, which Fusion draws in `Highlight`: at least 3:1 against `Window` and `Base`;
  - selected-row text against its highlight (Active and Inactive): at least 4.5:1;
  - every chrome icon against its background: at least 3:1.

**Font scaling.** A test sets the application font to 24 pt, shows the window and checks that no chrome widget's text is
clipped: each label's `sizeHint().height() <= height()`, and toolbar and tab heights follow the font. No chrome widget has a
fixed pixel height.

## 9. Pull requests

They are stacked in this order. Each PR's branch starts from the previous one.

| # | Issue | Branch | Adds |
| --- | --- | --- | --- |
| 1 | #45 | `claude/pyside6-storybook-icons` | icon bundle, script, `gui/icons.py`, error panel icon, CI check |
| 2 | #19 | `claude/pyside6-storybook-sidebar` | `gui/sidebar.py`, `GalleryWindow.set_registry` |
| 3 | #23 | `claude/pyside6-storybook-docs-tab` | Canvas and Docs tabs, `gui/docs_panel.py` |
| 4 | #20 | `claude/pyside6-storybook-canvas-toolbar` | `gui/canvas.py`, `SizePreset`, `StoryRegistry.size_presets` |
| 5 | #21 | `claude/pyside6-storybook-zoom` | zoom in `gui/canvas.py` |
| 6 | #22 | `claude/pyside6-storybook-actions` | `StoryContext.log_signal`/`log`, `ActionSink`, `gui/actions_panel.py` |
| 7 | #24 | `claude/pyside6-storybook-hot-reload` | `discovery/reload.py`, `gui/reload_watcher.py`, status bar, `--no-reload` |
| 8 | #25 | `claude/pyside6-storybook-accessibility` | shortcuts, Help menu, F6, the audit tests |

**Merging.** The stack must be merged bottom-up, and each PR retargeted to `main` before it merges. With "Automatically delete
head branches" on, GitHub retargets the next PR when its base branch is deleted. Every PR description says this.

## 10. Testing and documentation

**Testing**
- Each PR adds tests next to its code (`tests/test_<module>.py`), follows `AGENTS.md`'s test rules, and keeps the existing tests
  green.
- Changed existing tests are listed in the PR. For example, the window tests that read `storySidebar` as a `QListWidget` change
  in PR 2, to read the sidebar's tree.
- The screenshots in the last PR's description show the finished window in both themes.

**Documentation**
- Each PR updates the README section for what it adds:
  - "The gallery window", a new section with the panes and the shortcuts;
  - "Logging actions";
  - "Hot reload";
  - the `SizePreset` example.
- It also updates the changelog and the `AGENTS.md` project structure, plus the icon conventions from #45.
- PR 8 replaces `docs/images/gallery.png` with a new screenshot.

## 11. Out of scope

The issues' own out-of-scope lists apply, plus:
- remembering any window state between runs;
- an icon API for story authors;
- automatic signal logging (§6);
- zooming the chrome;
- a separate reload process.
