# Story API (milestone 2): implementation plan

Status: draft. Implements `docs/specs/story-api.md` (the spec) in five pull requests, one per issue. Section numbers below
(§1.2, §4.3) refer to the spec.

## Order and branches

| # | Issue | Branch | Base | Why this position |
| --- | --- | --- | --- | --- |
| 1 | #16 control options | `claude/pyside6-storybook-control-options` | `main` | Adds `coerce`, `display_label` and the `gui/editors/` package, which every later PR builds on. |
| 2 | #14 variants | `claude/pyside6-storybook-variants` | PR 1 | Needs `coerce` (validating `args`) and `ControlsPanel(values=...)`. |
| 3 | #15 new controls | `claude/pyside6-storybook-new-controls` | PR 2 | Needs the editors package; independent of variants, but placed after them to avoid conflicts in the same files. |
| 4 | #18 layout | `claude/pyside6-storybook-layout` | PR 3 | Adds `layout=` to `@story` and `Story.variant()`. |
| 5 | #17 decorators | `claude/pyside6-storybook-decorators` | PR 4 | Adds `decorators=` to both, and replaces the window's render path, which PR 4 has just reshaped. |

The five PRs touch the same files (`controls/__init__.py`, `story_definition.py`, `controls_panel.py`, `window.py`, the examples,
README and changelog), so they are stacked rather than parallel: each branch starts from the previous one, and each PR targets the
previous branch so its diff shows only its own change. When a PR merges, the next one is retargeted to `main` (and merged with
`main` if GitHub reports a conflict). The spec PR (#55) is documentation only and does not need to merge first.

Each PR says "Closes #N" for its issue, lists the public names it adds, and updates `CHANGELOG.md` (`### Added`, plus
`### Changed` where behaviour changes), the README section it affects, and `AGENTS.md`'s project structure when modules are added.

## Process per PR

1. A Sonnet subagent implements the PR on its branch in `/home/user/pyside6-storybook`, following the spec, this plan,
   `AGENTS.md` and `CLAUDE.md`. It commits locally and does not push.
2. I review the diff against the spec and the checklist below, and run every check:
   - `uv run ruff check .`
   - `uv run ruff check --select W291,W292,W293 <changed files>`
   - `uv run ty check`
   - `QT_QPA_PLATFORM=offscreen uv run pytest -q`
   - `QT_QPA_PLATFORM=offscreen uv run --isolated --python 3.11 --resolution lowest-direct pytest -q`
3. Problems go back to the same subagent (SendMessage) or are fixed directly when small.
4. I push the branch and open a draft PR. Nobody watches it; review comments are handled when the user asks.

Review checklist for every PR: keyword-only new parameters after the existing ones; no zero-argument `super()` in slotted
dataclasses; `QSignalBlocker` for linked editors; every new widget has a parent; accessible names on every editor part; colours
only from palette roles; docstrings match the code; `__all__` and the changelog list exactly the new public names; existing
assertions are not weakened (changed tests are called out in the PR description).

## PR 1: control options and `coerce` (#16)

Code:
- `controls/_options.py`: `derive_label(name)` (today's `name.replace("_", " ").title()`), and the float helpers moved from
  `gui/controls_panel.py` (`float_step_and_decimals`, `decimals_needed`), now taking the explicit `step` and `decimals`.
- Every existing control (§1.1): keyword-only `label` and `description`, `display_label`, `coerce`. `__post_init__` validates the
  default through `coerce` and stores nothing new beyond the fields (derived values such as `effective_decimals` are properties).
- Options (§1.2): `TextControl.multiline`; `IntControl.step`, `IntControl.slider`; `FloatControl.step`, `decimals`, `slider`
  and `effective_decimals`, with the slider-position rule and the 10 000-position limit.
- `Story.default_args()` returns `coerce(control.default)` per control.
- `gui/editors/`: `ControlEditor` base (`QWidget`, `valueChanged = Signal(object)`, `value()`), and one module per editor:
  `text_editor.py` (line edit or plain-text edit), `bool_editor.py`, `choice_editor.py`, `int_editor.py`, `float_editor.py`
  (spin box, optional slider, mirrored with `QSignalBlocker`). `_wheel.py` holds the wheel filter (§1.4). `__init__.py` holds the
  control-type-to-editor dict and a `create_editor(control, value, parent)` function.
- `gui/controls_panel.py`: the form over the editors, `ControlsPanel(controls, parent=None, *, values=None)`, `display_label`,
  buddy, `description` as tooltip and accessible description, focus proxies; `values()` coerces.
- `gui/window.py`: the controls section is a `QScrollArea` (`widgetResizable`, no horizontal scroll bar); the window passes
  `values=story.default_args()`.
- Examples: use `label`, `description`, `multiline` and `slider` at least once each; `tests/test_examples.py` checks that
  every option field is used by some example, the way it checks control types.

Tests:
- `tests/test_controls.py`: the `coerce` table, per control, accepted and rejected values (bool rejects `1`, int rejects `True`,
  float rejects `nan`, out-of-range values and values finer than `effective_decimals`); each new field's validation; `display_label`;
  the decimals derivation and the explicit-`decimals` error; slider positions (`ceil`, last position is `maximum`, the limit).
- `tests/test_editors.py`: each editor driven like a user (typing, clicking, `setValue` on the spin box or slider) emits exactly one
  `valueChanged` with the coerced value; slider and spin box mirror each other; the last slider position gives `maximum`; a wheel
  event sent to an unfocused spin box, slider or combo box leaves the value unchanged and is not accepted; focus proxy and accessible
  names on composite editors; multiline text.
- `tests/test_controls_panel.py`: keeps passing; adds `values=`, labels and descriptions, buddies, `values()` returning coerced
  values.
- `tests/test_window.py`: the controls section scrolls (a story with many controls gets a vertical scroll bar).

Docs: README "Controls" table gains the shared fields and the options; changelog `### Added` (options, label, description) and
`### Changed` (defaults must have the control's value type); `AGENTS.md` structure (`gui/editors/`, `controls/_options.py`).

## PR 2: variants (#14)

Code (§2):
- `Story`: `component`, `variant_of`, `args` (read-only mapping, `types.MappingProxyType`), internal `_registry`,
  `variant(name, *, args=None)`. `default_args()` uses the variant's `args` first. The variant shares the base's function,
  controls, doc and origin. Validation errors as §2.2 lists them.
- `StoryRegistry.register` sets `story._registry`; the registration rules of §2.3 already hold through the origin check, so only
  ordering needs checking (a variant registers after its base, by construction).
- Examples (§2.4): `Buttons/Push Button/Default` with `Disabled` and `Checkable`; `Inputs/Line Edit/Default` with `Password`
  and `Read-only`. `EXPECTED_IDS` in `tests/test_examples.py` changes, and the PR description says so.

Tests (`tests/test_registry.py`, `tests/test_window.py`):
- ids and `component`; `variant_of`; `args` reach the render function and the panel's starting values, and stay editable;
- errors: unknown key, invalid value, no component, blank name, name with `/`, same name as the base, variant of a variant,
  `.variant()` on an unregistered story;
- `Story.args` cannot be mutated; `default_args()` returns fresh values each call;
- reloading a story module (through the `stories` fixture) replaces the base and its variants, with no duplicates, in order;
- a variant id colliding with another function's story raises.

Docs: README "Variants" section with the component-id advice; changelog `### Added` (variants) and `### Changed` (renamed example
ids).

## PR 3: colour, enum and file controls (#15)

Code (§1.3):
- `controls/color_control.py`, `enum_control.py`, `file_control.py`, each with `label`, `description`, `display_label` and
  `coerce` like the others; the `Control` union and `__all__` (package root too) grow.
- `gui/editors/color_editor.py` (swatch button with icon and hex text, hex line edit, `_ask_color`), `enum_editor.py`,
  `file_editor.py` (line edit, "Browse…" button, `_ask_file`); registered in the editor dict.
- Examples: a story using each new control (for example a colour swatch label, an alignment enum on a `QLabel`, a file path
  shown in a label); `test_the_examples_use_every_control_type` grows to eight types.

Tests:
- `tests/test_controls.py`: the colour grammar (accepted and rejected strings, case, 8 digits only with `alpha`), `QColor` input
  (invalid, translucent without `alpha`), a new object on every `coerce`; enum options from `__members__` with aliases removed,
  `Qt.AlignmentFlag.AlignCenter` accepted, `AlignLeft | AlignTop` rejected, a Python `Enum` and a Qt enum; file `str`, `Path`,
  `None`, empty string.
- `tests/test_editors.py`: the colour editor with `_ask_color` monkeypatched (chosen colour, cancelled dialog), typing a valid and an
  invalid hex value; the enum combo; the file editor with `_ask_file` monkeypatched (chosen, cancelled) and typed paths; one
  `valueChanged` per edit; accessible names on the swatch and browse buttons; focus proxies.

Docs: README controls table; changelog `### Added`.

## PR 4: layout (#18)

Code (§3):
- `registry/layout.py` with `Layout`; exported from the package root.
- `layout=` on `StoryRegistry.story`, the module-level `story` and `Story.variant()`; `Story.layout`; validation at registration.
- `StoryRegistry.default_layout` property.
- `gui/window.py`: the preview surface inside a `QScrollArea`; one method that places the root widget for a mode (alignment, the
  surface's minimum size, scroll bar policies) and is called from the story path, the error path and on deselection.
- Examples: Push Button stories CENTERED, a new `Display/Table` (`QTableWidget`) FILL.

Tests (`tests/test_registry.py`, `tests/test_window.py`; the window shown with `qtbot.waitExposed` and a fixed size):
- `Layout` values; `layout=` accepts a member, its string and `None`, rejects anything else; `default_layout` validation and use;
  variants inherit and override.
- Geometry per mode: PADDED top-aligned with the full width for a horizontally expanding widget; CENTERED centred at its natural
  size, still centred after `resize`; FILL fills both directions for an expanding widget, and keeps the natural height, centred, for
  a `QPushButton`.
- An 800×600 fixed-size-hint widget in a small window keeps its natural size and gets scroll bars in PADDED and CENTERED, and no
  scroll bars in FILL.
- The error panel uses FILL whatever the story declares.

Docs: README "Layout and decorators" section (layout part); changelog.

## PR 5: decorators (#17)

Code (§4):
- The `Decorator` type alias is defined in `registry/story_context.py` beside `StoryFunction`, and re-exported from
  `pyside6_storybook.decorators` and the package root. (Defining it in `decorators/` would create an import cycle: the built-ins
  import `StoryContext` from `registry`, and `registry` needs the type for `Story.decorators`.)
- `decorators/padding.py`, `frame.py`, `fixed_size.py`, each a small class with `__call__` and `__repr__` (or a function returning
  one).
- `decorators=` on `StoryRegistry.story`, the module-level `story` and `Story.variant()`; `Story.decorators` (tuple);
  `StoryRegistry.decorators` (list).
- `registry/rendering.py`: `RenderedStory`, `StoryRenderError`, `render_story`, and `_story_traceback` moved from the window.
- `gui/window.py`: renders through `render_story`, keeps `widget` for `current_preview_widget()`, places `root`, deletes `root`
  on rebuild.
- Example: one story uses `padding` or `frame`.

Tests:
- `tests/test_rendering.py`: order with story and registry decorators (record the call order, and check parentage); the 320×200
  inside 24 px example; each failure title of §4.3 and that the error chains the original (`__cause__`); nothing left alive after a
  failure (`shiboken6.isValid` after sending posted deferred deletes); the `QGroupBox` decorator from the issue.
- `tests/test_decorators.py`: each built-in's geometry and validation and `repr`.
- `tests/test_window.py`: `current_preview_widget()` is the undecorated widget; the decorated root and the widget are deleted on
  rebuild; a decorator error shows the error panel and logs with `exc_info`; existing error-title tests unchanged.

Docs: README "Layout and decorators" section (decorators part: the built-ins and a custom decorator); changelog; `AGENTS.md`
structure (`decorators/`, `registry/rendering.py`, `registry/layout.py`).

## After the five PRs

- The milestone's issues are closed by their PRs.
- Run the "Full test suite" workflow on `main` (the user starts it), since PRs 1, 3 and 4 change platform-sensitive GUI code.
