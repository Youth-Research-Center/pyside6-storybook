# Log every signal of a widget (#66): design and plan

Status: draft. One pull request. Section numbers (§1) are used by the review.

## 0. Starting point and decisions

**Starting point.**
- `StoryContext.log_signal(signal, name=None)` connects one bound signal to `_forward(sink, name)`, a closure that holds the sink and
  the name, never the widget (`registry/story_context.py`). The connection ends when the widget is deleted. Without a sink
  (`actions is None`) it does nothing.
- The Actions panel shows each emission as `name(args)`, newest first, keeps 500 entries, and drops entries from an older render
  (`gui/actions_panel.py`).
- #22 deferred "log every signal", for two reasons: the noise of the inherited signals, and the work of handling every signature.

**What I tried** (23 November 2026, PySide6 6.12.0 on Python 3.14, and 6.8.0, the oldest allowed, on Python 3.11, offscreen):
- **Listing.** Iterating `metaObject()` from `QWidget.staticMetaObject.methodCount()` up, and keeping `MethodType.Signal`, lists exactly
  the signals declared below `QWidget`, with no `objectNameChanged`, `destroyed`, `windowTitleChanged`, `windowIconChanged`,
  `windowIconTextChanged` or `customContextMenuRequested`:
  - `QPushButton`: `pressed`, `released`, `clicked`, `toggled`;
  - `QSlider`: `valueChanged`, `sliderPressed`, `sliderMoved`, `sliderReleased`, `rangeChanged`, `actionTriggered`;
  - `QComboBox` and `QLineEdit`: their own signals;
  - a Python `Signal` declared on a `QWidget` subclass, which is listed too.
- **Signatures and overloads.** A signal with default arguments has cloned entries (`clicked(bool)` and `clicked()`), so names are
  deduplicated, keeping the first. `getattr(widget, name)` returns the bound signal, and the closure slot (`*args`) receives what that
  bound signal delivers. That is `clicked()` with no arguments, the same as `log_signal` today.
- **Enum arguments.** A signal that delivers an enum fails in a fresh process, for example `QCheckBox.checkStateChanged(Qt::CheckState)`.
  The cause is that PySide6 creates enum types lazily, and until the type exists Qt cannot convert the argument:
  - PySide6 6.12 prints `TypeError: Cannot call meta function "slot(Qt::CheckState)" ... cannot be converted` and drops the emission;
  - 6.8 raises the error out of the code that emitted, for example `QCheckBox.click()`.

  Once the Python enum type exists, the emission is delivered on both versions, as `<CheckState.Checked: 2>`. Importing
  `PySide6.QtCore.Qt` creates the `Qt::` enums, and `registry/story_context.py` already imports it. So a `Qt::` enum works, but an enum
  scoped to a class, such as `QSystemTrayIcon::ActivationReason`, may not exist yet. Declaring a typed `@Slot`, or connecting a receiver
  whose slot has the signal's types, did not help.

**Decisions.**
- **API: a method, `ctx.log_signals(widget, *, exclude=())`, next to `log_signal`.** The issue's example, `@story(..., log_signals=True)`,
  was offered as one option. I recommend the method:
  - it works on any widget the story builds, including a child inside a wrapper, which is often the one that matters;
  - it needs no change to `Story`, variants, rendering or the gallery;
  - it reads like `log_signal`, so a story can mix both.

  A story option could be added later on top of the method.
- **Which signals:** those declared by the widget's own class and its bases below `QWidget`. For a `QObject` that is not a `QWidget`,
  those below `QObject`. This answers the issue's noise question with "the class's own signals, not `QObject`'s or `QWidget`'s".
- **Excluding:** `exclude` takes signal names. A name the widget does not have is an error (`ValueError` listing it), so a typo does not
  silently log everything.
- **Arguments:** each signal is connected once by name, through the bound signal `getattr` returns, to the same `_forward` closure
  `log_signal` uses. What the row shows is therefore exactly what `log_signal` would show.
- **Enum arguments:** before connecting a signal, resolve each enum parameter type, so that it can be converted (§1.2). A signal with a
  parameter type that cannot be resolved is not connected. Instead it is listed once in the Actions panel as an action named
  `log_signals`, with the skipped signal names as its arguments, and logged at debug level. A story author sees why a signal is missing;
  nothing raises.

## 1. Design

### 1.1 `StoryContext.log_signals`
```python
def log_signals(self, widget: QObject, *, exclude: Iterable[str] = ()) -> None:
```
- **Without a sink** it does nothing. It neither validates `exclude` nor touches the widget, like `log_signal`.
- **The signals.** The names are those of §0: the widget's `metaObject()` signals from the base offset up, deduplicated, in declaration
  order. The base offset is `QWidget.staticMetaObject.methodCount()` for a `QWidget`, else `QObject.staticMetaObject.methodCount()`.
- **`exclude`** is checked against those names first. Unknown names raise `ValueError("... has no signal(s) named ...; its signals are:
  ...")`.
- **Each remaining name** is connected with `getattr(widget, name).connect(_forward(self.actions, name))`, unless its parameter types
  cannot be resolved (§1.2).
- **Calling it twice** connects twice, like calling `log_signal` twice. The docstring says so.
- **The docstring** (Google style) names the default selection, `exclude`, the skipped-signal action, and that the connections end with
  the widget.
- **Public API.** It needs no new name in `__all__`: it is a method of `StoryContext`, which is already public.

### 1.2 Resolving parameter types
`_ensure_enum_types(method: QMetaMethod) -> bool`, a private helper in `story_context.py`.
- For each name in `method.parameterTypes()` that contains `::` (`Owner::Enum`, possibly `Owner::Inner::Enum`), it finds `Owner` as an
  attribute of `PySide6.QtCore`, `PySide6.QtGui` or `PySide6.QtWidgets`, in that order, then walks the rest with `getattr`. Touching the
  attribute creates the enum type.
- It returns `False` if any such name cannot be resolved, and `True` otherwise.
- Names without `::` (`int`, `QString`, `bool`, `QModelIndex`, `QAbstractButton*`) are left alone. The plan checks pointer and value
  types on the stock widgets in §3.
- **Imports.** `PySide6.QtGui` is imported lazily, only if needed; `QtCore` and `QtWidgets` are already imported. The library's only
  dependency is PySide6-Essentials, which includes QtGui and QtWidgets.
- **Which method to resolve** for a deduplicated name: every entry with that name that is not cloned. Resolving all of them is harmless
  and avoids guessing which overload `getattr` returns.

### 1.3 Documentation
- **`docs/gallery.md`, "Logging actions":** a paragraph and a short example after the `log_signal` example:
  - `ctx.log_signals(widget)` logs every signal the widget's classes declare below `QWidget`, so the noisy inherited ones are left out;
  - `exclude=` drops names;
  - a typo raises;
  - a signal whose argument types cannot be converted is listed once under `log_signals` instead.

  The example runs in `tests/test_docs.py` like every block, so it carries its imports.
- **An example story** in `src/pyside6_storybook/examples/`. "Inputs/Combo Box" calls `ctx.log_signals(widget, exclude=("highlighted",
  "textHighlighted"))`, which shows both the method and `exclude` on a widget with many signals. No story ids change, so
  `EXPECTED_IDS`, `EXPECTED_STORY_IDS` and the counts stay the same. Confirm that the combo box story has a docstring that still
  describes it, and extend the docstring to mention the logging.
- **`CHANGELOG.md`:** under `[Unreleased]` → `### Added`: "`StoryContext.log_signals(widget, exclude=...)` logs every signal a widget's
  classes declare below `QWidget` in the Actions panel."
- **`AGENTS.md`:** the `story_context.py` entry mentions `log_signals`; the `actions_panel.py` entry names it next to `log_signal`.

## 2. Tests

In `tests/test_registry.py`, next to the `log_signal` tests, using a recording sink as those do:
- **`QPushButton`.** It connects `pressed`, `released`, `clicked` and `toggled`. A `qtbot.mouseClick` records
  `[("pressed", ()), ("released", ()), ("clicked", ())]`, in that order. Changing the object name records nothing.
- **A subclass with a Python `Signal(str, int)`.** Its signal is logged with both arguments, after the inherited signals were connected.
- **`exclude`.** `exclude=("pressed", "released")` leaves only `clicked` after a click. `exclude=("presed",)` raises `ValueError`, and
  the message names `presed` and lists the real signals.
- **Without a sink.** It does nothing: no connection, and no error even for an unknown `exclude` name.
- **Enum argument.** `QCheckBox` with `log_signals` records `("checkStateChanged", (Qt.CheckState.Checked,))` on click, with the
  emission not dropped.
- **A fresh process,** a `full` test with a `subprocess.run` and a timeout, offscreen. A script that imports only `QApplication`,
  `QCheckBox`, `StoryContext` and a recording sink, never `Qt`, logs `checkStateChanged` with its enum argument. It must run in a fresh
  interpreter, because the test process has long since created the enum.
- **An unresolvable type.** Replace `_ensure_enum_types` with one that returns `False` for one signal. That signal is not connected, a
  single `log_signals` action lists it, and the others still log.
- **Lifetime.** After `widget.deleteLater()` and `QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)`, the closures hold no
  widget: a `weakref` to the widget is dead, and the sink records nothing more. This mirrors the existing `log_signal` lifetime test.
- **Stock widgets on both PySide6 versions.** `log_signals` on `QPushButton`, `QCheckBox`, `QSlider`, `QComboBox`, `QLineEdit`,
  `QSpinBox`, `QTabWidget` and `QListWidget` connects without error. This runs in the normal suite, so the lowest-direct run covers
  PySide6 6.8.
- **In the gallery.** In `tests/test_actions_panel.py`, selecting "Inputs/Combo Box" in the gallery and changing the current item records
  `currentIndexChanged`, but not `highlighted`.

## 3. Verification

- **Checks:** full suite, the lowest-direct run, `ruff`, `ty` and the docs build.
- **The plan also checks by hand,** on 6.8 and on the current PySide6, that the `QListWidget` and `QTabWidget` signals carrying
  `QListWidgetItem*` and `int` reach the sink with real arguments.

## 4. Out of scope

- A `@story(log_signals=True)` option. It can be added on top later if wanted.
- Logging signals of child widgets recursively.
- Choosing an overload other than the default one for a name.
