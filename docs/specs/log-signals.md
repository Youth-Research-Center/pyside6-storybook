# Log every signal of a widget (#66): design and plan

Status: reviewed (findings applied). One pull request. Section numbers (§1) are used by the plan.

## 0. Starting point and decisions

**Starting point.**
- `StoryContext.log_signal(signal, name=None)` connects one bound signal to `_forward(sink, name)`, a closure that holds the sink and
  the name, never the widget (`registry/story_context.py`). The connection ends when the widget is deleted. Without a sink
  (`actions is None`) it does nothing.
- The Actions panel shows each emission as `name(args)`, newest first, keeps 500 entries, and drops entries from an older render
  (`gui/actions_panel.py`). The pytest plugin passes a discarding sink (`testing/storybook_session.py`), so the story items connect
  signals too.
- #22 deferred "log every signal", for two reasons: the noise of the inherited signals, and the work of handling every signature.

**What I tried and the review confirmed** (PySide6 6.12.0 on Python 3.14, and 6.8.0, the oldest allowed, on Python 3.11, offscreen).
- **Listing the signals.** Iterating `metaObject()` from `QWidget.staticMetaObject.methodCount()` up, keeping `MethodType.Signal` and
  deduplicating names, lists the signals declared below `QWidget`. That leaves out `objectNameChanged`, `destroyed`,
  `windowTitleChanged`, `windowIconChanged`, `windowIconTextChanged` and `customContextMenuRequested`. Some examples:
  - `QPushButton`: `pressed`, `released`, `clicked`, `toggled`;
  - `QSlider`: `valueChanged`, `sliderPressed`, `sliderMoved`, `sliderReleased`, `rangeChanged`, `actionTriggered`;
  - `QListWidget`: 18 signals;
  - item views, `QToolBar`, `QDockWidget` and Python subclasses with a `Signal` all give sensible lists, and a non-widget `QObject` does
    too when the offset is `QObject.staticMetaObject.methodCount()`.
- **Arguments.** Every argument type of the stock widgets arrives with real values on both versions: flags, `QAction*`,
  `QListWidgetItem*`, `QModelIndex`, `QItemSelection`, `QDate`, `QRect` and enums. A signal with default arguments has cloned entries
  (`clicked(bool)` and `clicked()`). `getattr(widget, name)` gives the default overload, so `clicked` arrives with no arguments, the same
  as `log_signal` today.
- **Enum arguments.** PySide6 creates a Python enum type when its owner (a class, or the `Qt` namespace) is first used from Python. Until
  then, Qt cannot convert the argument.
  - `Qt::` enums are covered: `registry/story_context.py` imports `Qt`.
  - The widget's own class enums are covered as well, because its class already exists in Python.
  - The case that fails is an enum owned by another class. `QMovie.error` delivers `QImageReader::ImageReaderError`, and it fails even
    with `pyside6_storybook` imported; importing `QImageReader` fixes it.
  - A scan of QtCore, QtGui and QtWidgets finds only that one foreign-owner case among QObjects, plus `QStyleHints` signals with
    `std::chrono` types. No stock widget hits it.
  - When the conversion fails, PySide6 6.12 hands a `TypeError` to `sys.excepthook`. The gallery prints it, and the pytest plugin's
    exception capture and pytest-qt fail the item. PySide6 6.8 leaves a pending exception that surfaces in the next Python slot as a
    `SystemError`.
- **Signal sets differ between Qt versions.** On 6.8, `QSpinBox`, `QDoubleSpinBox` and `QDateEdit` have no `returnPressed`, and
  `QStackedWidget` has no `widgetAdded`.
- **One per-frame signal.** `QPlainTextEdit.updateRequest(QRect, int)` fires on every repaint and cursor blink: 9 emissions in 3 s while
  idle with focus.
- **Lifetime.** With every signal of `QListWidget`, `QTabWidget`, `QComboBox`, `QTreeWidget`, `QTableWidget`, `QToolBox`, `QTreeView` and
  `QPlainTextEdit` connected, deleting the widget frees the sink, and nothing is emitted during destruction, on both versions.

**Decisions.**
- **API: a method, `ctx.log_signals(obj, *, exclude=())`, next to `log_signal`.** The issue's example, `@story(..., log_signals=True)`,
  was offered as one option. The method:
  - works on any object a story builds: a child inside a wrapper, or an item view's `selectionModel()` and `model()`;
  - needs no change to `Story`, variants, rendering or the gallery;
  - reads like `log_signal`.

  A story option could be added later on top of it.
- **Which signals:** those declared by the object's class and its bases below `QWidget`, or below `QObject` for a non-widget, minus a
  small built-in set of per-frame signals: `_NOISY_SIGNALS = frozenset({"updateRequest"})`. A story that wants one of those connects it
  with `log_signal`.
- **`exclude`** takes signal names. A name the object does not have is logged as a warning, naming the object's class and its signals,
  instead of raising. Signal sets differ between the supported Qt versions, so one story must work on both.
- **Arguments:** each signal is connected once by name, through `getattr`'s bound signal, to the same `_forward` closure that
  `log_signal` uses.
- **Enum arguments:** before connecting anything, resolve the enum parameter types of every signal that will be connected (§1.2). A
  signal with a type that cannot be resolved is not connected. It is logged once per call as a warning. It is not added to the Actions
  panel: a pseudo-action would come back on every control change.

## 1. Design

### 1.1 `StoryContext.log_signals`
```python
def log_signals(self, obj: QObject, *, exclude: Iterable[str] = ()) -> None:
```
- **Without a sink** it does nothing, like `log_signal`. It neither touches `obj` nor reads `exclude`.
- **Argument checks:**
  - `exclude` as a bare `str` raises `TypeError` ("pass a tuple of names, not a string");
  - `obj` that is not a `QObject` raises `TypeError`. If it is a `SignalInstance`, the message points to `log_signal`.
- **The signals.** The names are those of §0: the object's `metaObject()` signals from the base offset up, deduplicated, in declaration
  order, without `_NOISY_SIGNALS`.
- **Unknown names** in `exclude` are logged once at warning level by the module's logger (`logging.getLogger(__name__)`, since this is
  a function in a module and not a class with state).
- **Enum types** are resolved for every remaining name first (§1.2). Unresolvable names are dropped with one warning.
- **Connecting.** Each remaining name is connected with `getattr(obj, name).connect(_forward(self.actions, name))`.
- **The docstring** (Google style) says:
  - which signals are logged, and the built-in skip set;
  - what `exclude` does, and that unknown names warn;
  - call it after configuring the object, or the setup emissions (`addItems` emits `currentIndexChanged`, ...) are logged on every
    render;
  - connections end when `obj` is deleted, so a long-lived object that is not rebuilt with the story gets one more connection per
    render; log its signals with care;
  - calling it twice connects twice;
  - `Raises: TypeError`.
- **Related docstrings.** `ActionSink`, `StoryContext.actions` and the docs that say "`log` and `log_signal`" name all three methods.
- **Public API.** No new name in `__all__`: it is a method of `StoryContext`, which is already public.

### 1.2 Resolving enum parameter types
`_resolve_parameter_types(method: QMetaMethod) -> bool`, a private helper in `story_context.py`.
- **Names without `::`** (`int`, `QString`, `bool`, `QModelIndex`, `QAbstractButton*`, `QRect`) need nothing.
- **A name containing `<`** (a template such as `std::chrono::...` or `QList<...>`) is unresolvable, so the signal is skipped.
- **Any other name with `::`** (`Owner::Enum`, or `Owner::Inner::Enum`) is resolved this way:
  - strip a trailing `*` or `&`;
  - find `Owner` as an attribute of `PySide6.QtCore`, `PySide6.QtGui` or `PySide6.QtWidgets`, in that order;
  - walk the rest with `getattr`. Touching it creates the enum type.

  A missing part makes the name unresolvable.
- **It returns** `True` when every parameter type is resolvable.
- **Which methods.** `QMetaMethod` offers no way to tell cloned entries apart in PySide6 6.8 or 6.12 (`attributes()` does not exist).
  So every signal entry with a given name is resolved. A name counts as resolvable only if all its entries are.
- **Imports.** `PySide6.QtGui` is imported inside the helper, only when needed. `QtCore` and `QtWidgets` are already imported, and all
  three are part of PySide6-Essentials, the only dependency.

### 1.3 Documentation
- **`docs/gallery.md`, "Logging actions".**
  - The opening says "a story logs one signal with `ctx.log_signal`, every signal of a widget with `ctx.log_signals`, or anything with
    `ctx.log`".
  - A new paragraph and example cover:
    - what `log_signals` logs, and what it leaves out (the `QObject`/`QWidget` signals and `updateRequest`);
    - `exclude=`, and that unknown names warn;
    - calling it after configuring the widget;
    - for an item view, logging `view.selectionModel()` (`selectionChanged`, `currentChanged`) and the model (`dataChanged`), because
      the view itself has no selection signal.
  - The example runs in `tests/test_docs.py` like every block, so it carries its imports.
- **An example story.** "Inputs/Combo Box" in `src/pyside6_storybook/examples/inputs_stories.py` calls
  `ctx.log_signals(widget, exclude=("highlighted", "textHighlighted"))` after configuring the widget, and its docstring says so. No story
  id changes. The review found nothing that breaks: the docs images use other stories, and the smoke script and `test_examples` list ids
  only.
- **`CHANGELOG.md`:** under `[Unreleased]` → `### Added`: "`StoryContext.log_signals(obj, exclude=...)` logs every signal that the
  object's classes declare (below `QWidget` for a widget) in the Actions panel."
- **`CHANGELOG.md`, `### Fixed`:** none. `log_signal`'s behaviour does not change, and its enum case is the one foreign-owner signal
  described in §0.
- **`AGENTS.md`:** the `story_context.py` entry mentions `log_signals`, and the `actions_panel.py` entry names it next to `log_signal`.

## 2. Tests

In `tests/test_registry.py`, next to the `log_signal` tests, using a recording sink as those do:
- **`QPushButton`.**
  - The connected names are exactly `pressed`, `released`, `clicked` and `toggled`. A small helper returns the names `log_signals` would
    connect, so the test asserts the list.
  - A `qtbot.mouseClick` records `[("pressed", ()), ("released", ()), ("clicked", ())]`, in that order.
  - Changing the object name records nothing.
- **A subclass with a Python `Signal(str, int)`.** Its signal is logged with both arguments.
- **`QPlainTextEdit`.** `updateRequest` is not connected, and `textChanged` is.
- **`exclude`.**
  - `exclude=("pressed", "released")` leaves only `clicked` after a click.
  - `exclude=("presed",)` logs one warning (`caplog`) naming `presed`, and every signal still logs.
  - `exclude="clicked"` raises `TypeError`.
- **Wrong object.** `ctx.log_signals(button.clicked)` raises `TypeError` naming `log_signal`.
- **Without a sink.** It does nothing: nothing is connected, and no warning is logged for an unknown name.
- **A non-widget `QObject`:** a `QItemSelectionModel` on a `QStringListModel`. Selecting a row records `selectionChanged` and
  `currentChanged` with their arguments.
- **A fresh process,** a `full` test with `subprocess.run`, a timeout and offscreen.
  - A script creates a `QMovie` for a path that does not exist inside `tmp_path`, calls `log_signals` on it with a recording sink, calls
    `start()` and processes events.
  - It prints the recorded `error` arguments. The test asserts that the `error` action carries `QImageReader.ImageReaderError`'s member,
    and that stderr has no `cannot be converted`.
  - It needs a fresh interpreter, because the test process has already created `QImageReader`. The plan checks that the test fails
    without §1.2.
- **An unresolvable type.** Monkeypatch `_resolve_parameter_types` to return `False` for `clicked`'s entries. Then `clicked` is not
  connected, one warning names it, and `pressed` still logs.
- **Lifetime,** mirroring `tests/test_actions_panel.py`'s `log_signal` test. A `weakref` to the sink is dead after `deleteLater()`,
  `QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)` and `gc.collect()`. It runs for a `QListWidget` and a `QComboBox`
  with all their signals connected.
- **Stock widgets.** For `QCheckBox`, `QSlider`, `QComboBox`, `QLineEdit`, `QSpinBox`, `QTabWidget` and `QListWidget`:
  - `log_signals` connects the names the helper reports, without an error or a warning;
  - one interaction each records the expected name with a real argument, for example `QListWidget.setCurrentRow(0)` records
    `currentRowChanged` with `(0,)`, and `QCheckBox.click()` records `checkStateChanged` with `Qt.CheckState.Checked`.

  The lowest-direct run covers PySide6 6.8.
- **In the gallery.** In `tests/test_actions_panel.py`, selecting "Inputs/Combo Box" and changing the current item records
  `currentIndexChanged` and not `highlighted`. Both are emitted on both versions, so the test really exercises `exclude`.

## 3. Verification

- The full suite, the lowest-direct run, `ruff`, `ty` and the docs build all pass.
- The fresh-process test fails when §1.2 is disabled.

## 4. Out of scope

- A `@story(log_signals=True)` option. It can be added on top later.
- Logging the signals of child widgets recursively.
- Choosing an overload other than the default one for a name.
