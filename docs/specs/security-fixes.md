# Security review fixes before 0.1.0: design and plan

Status: draft. Four pull requests, from the security review of 23 November 2026 (main at 122565f, plus #121). Every finding below was
verified against the code; the reviewers' reproductions are under `/tmp/claude-0/secreview/<area>/`. None needs an advisory: each needs
control of story code, project config or a dependency. Section numbers (§1) are used by the reviews.

## Order, branches and merging

| PR | Area | Branch | Base |
| --- | --- | --- | --- |
| S1 | Story text shown as plain text in the gallery | `claude/pyside6-storybook-plain-text` | `main` |
| S2 | Reload and discovery scope | `claude/pyside6-storybook-reload-scope` | `main` |
| S3 | Snapshot file names | `claude/pyside6-storybook-snapshot-names` | `main` |
| S4 | Release pipeline hardening, SECURITY.md and RELEASING.md | `claude/pyside6-storybook-release-hardening` | `main` |

- **Independent.** The four touch different files, except `CHANGELOG.md` (each adds an entry) and `AGENTS.md`. Each uses "Create a merge
  commit". Whichever merges later merges `main` first and checks that its changelog entries are under `## [Unreleased]`.
- **Process.** As for #66/#100:
  - a Sonnet subagent implements each PR, test first, in its own worktree, following this spec, `AGENTS.md`, `CLAUDE.md` and
    `/tmp/claude-0/specs9/common.md`;
  - I review and rerun every check;
  - I push, open a draft PR, and wait for CI.
- **Changelog.** The bug fixes go under `### Fixed`. S3 also gets a `### Changed` entry, because snapshot file names change for ids with
  `_`, `%` or special characters, and the plugin shipped in 0.1.0rc1.

## §1 S1: story text is shown as plain text

**Finding (Low, confirmed).** Several widgets show story strings with Qt's default `AutoText`, so a string that looks like HTML is
rendered as HTML:
- `QLabel`s showing a story id (the preview heading, `gui/window.py:140, 658`) or a control label (`gui/controls_panel.py:61`);
- tooltips holding a control description (`controls_panel.py:65-66`) or a story id (`gui/sidebar.py:442`).

An `<img src=...>` in one of them opens a local file, and on Windows a `\\host\share` path would make an SMB connection, which
SECURITY.md rules out. The sidebar's "No stories match '…'" label (`sidebar.py:264, 535`) has the same flaw, though only the user's own
typing reaches it.

**Fix.**
- **Labels:** every `QLabel` that can show a story-, control-, theme-provider- or user-derived string gets
  `setTextFormat(Qt.TextFormat.PlainText)`. The implementer finds them all with
  `grep -n "QLabel(\|setText(\|setToolTip(\|ToolTipRole" src/pyside6_storybook/gui`, and lists each one with its decision in the report.
  The Docs tab's sibling links stay `RichText`, because they already `html.escape` both the href and the text.
- **Tooltips:** every tooltip built from such a string is escaped. A tooltip is always rich text when it looks like HTML, so it is passed
  through a small helper, `plain_tooltip(text: str) -> str`, which returns `"<p>" + html.escape(text) + "</p>"` for non-empty text and
  `""` for empty text. It lives in `gui/chrome.py`, the module of the gallery's widget helpers, and is used by `controls_panel.py`,
  `sidebar.py` and any other place the grep finds.
- **Actions panel:** `gui/actions_panel.py` `format_arguments` guards each `reprlib` call with `try/except Exception`. On failure it
  shows `<TypeName>`. On Python 3.11 and 3.12, `repr_int` raises `ValueError` for an int over 4300 digits, and a `__repr__` may raise too.

**Tests.**
- **The window:** a story whose id, docstring, control label, description and choice options contain `<img src="file:///…/probe.png">`
  and `<b>bold</b>` payloads, the probe being a real PNG in `tmp_path`. After `select_story`, every visible `QLabel` in the window whose
  text contains the payload has `textFormat() == PlainText`.
- **Tooltips:** the control label's tooltip, the editor's tooltip and the sidebar item's `ToolTipRole` are escaped, with no `<img`
  outside `&lt;img`.
- **The search label** with `<b>x</b>` typed is `PlainText`.
- **`format_arguments`:**
  - an int with 5000 digits returns a string, which on 3.11 is `<int>`;
  - an object whose `__repr__` raises returns `<ClassName>`.
- **Each test fails before the fix.**

## §2 S2: reload and discovery stay inside the project

**Finding 1 (Low, confirmed).** `discovery/reload.py` `_is_project_module` (`:226-237`) treats any imported module under the working
directory or a `pythonpath` folder as a project module. The only exclusions are `site-packages`, `dist-packages`, `venv`, `.venv`,
`node_modules` and hidden folders. When the Python installation lies under those roots, each reload:
- drops `os`, `re`, `json` and the rest of the standard library from `sys.modules`;
- deletes their `__pycache__` files (`os.remove`) outside the project;
- leaves the QFileSystemWatcher watching every standard-library file.

Examples are a conda env in the project, a Windows per-user Python under the home folder with the terminal started there, and a
container whose working directory is `/`. The drop, the bytecode deletion and `importlib.invalidate_caches()` also run before the `try`
(`:118-129`). A `PermissionError` from `os.remove`, which only `FileNotFoundError` is caught for, therefore leaves `sys.modules` gutted
and the registry bindings on an empty registry.

**Fix.**
- **`_is_project_module`** returns `False` for a module whose top-level name is in `sys.stdlib_module_names`. It also returns `False` for
  a module whose file lies under any path in `{sysconfig.get_paths()[key] for key in ("stdlib", "platstdlib", "purelib", "platlib")}`.
  Those are computed once, in `__init__`, resolved. Whole prefixes are not excluded: a project may live under `sys.prefix`.
- **`_delete_bytecode`** acts only on files under one of `self._roots`. It catches `OSError` and logs it at debug level with the class
  logger, instead of only `FileNotFoundError`.
- **`reload`** moves the snapshot, the drop, the registry rebind, the bytecode deletion and `invalidate_caches()` inside the `try`, so any
  exception restores the previous modules and bindings. The docstring is updated.

**Finding 2 (Low, confirmed).** `discovery/file_search.py` `story_modules_in_package` follows symlinked folders with no visited set. A
`loop -> ..` symlink inside a package makes discovery run until the kernel's symlink limit, and with two such links it runs effectively
forever. Discovery is called on every watcher event.
- **Fix:** keep a set of resolved folders and skip any folder already visited, either as a parameter of an inner helper or as a set the
  generator closes over.

**Finding 3 (Hardening).**
- **Entry points.** An entry point's `module` reaches `load_stories` as a target. A target that exists as a path is loaded as a path, so
  an entry point naming `..` walks the parent folder. The fix is in `discovery/sources.py`: an entry point whose module is not a dotted
  name of identifiers (`all(part.isidentifier() for part in module.split("."))`) is reported as a `StorySourcesError` naming the
  distribution and entry point. The case of a valid name that also exists as a local folder (`stories`) is not changed; it is described
  in the PR as a known, documented order.
- **One exclusion list.** `discovery/file_search.py` `_is_searched_folder` also skips `site-packages`, `dist-packages` and
  `node_modules`. Both modules use one constant, `EXCLUDED_FOLDER_NAMES`, in `discovery/constants.py`.

**Tests.**
- **`tests/test_reload.py`:**
  - with the session's roots including the folder that holds the standard library (`Path(sysconfig.get_paths()["stdlib"]).parent`), a
    reload keeps `json` and `logging` the same module objects, and deletes no bytecode outside the stories folder (`os.remove`
    monkeypatched to record);
  - a reload whose bytecode deletion raises `PermissionError` still restores `sys.modules` and both registry bindings;
  - a reload whose `invalidate_caches` raises restores them too.
- **`tests/test_file_search.py`** (or the existing discovery test module): a package with a `loop -> ..` symlink is walked in under a
  second, and yields each story module once. It is skipped where symlinks cannot be created, as on Windows without the privilege.
- **Entry points:** `..` and `a b` as an entry point's module give `StorySourcesError`.
- **Folder search:** a `site-packages` folder under a folder target is not searched.

## §3 S3: snapshot file names are unique and stay in the snapshot folder

**Finding (Low, confirmed).** `testing/snapshots.py` `snapshot_name` replaces only `/` in the id, and `/` and `\` in the theme:
- **Collisions.** `"Grp/X"` and `"Grp__X"` both give `Grp__X[Light]`, so an update run reports success while one baseline overwrites
  the other.
- **Unsafe characters.** `\`, `:`, NUL and control characters pass through. On Windows, `\..\` or `C:\…` in an id writes outside the
  snapshot folder. On any system, Qt cuts the name at a NUL.

**Fix.**
- **`snapshot_name(story_id, theme)`** encodes both parts reversibly:
  - `/` becomes `__`;
  - every character outside `[A-Za-z0-9 .-]` and every `_` is percent-encoded as `%XX` per UTF-8 byte, `%` itself included;
  - a leading `.` is encoded.

  The result is still `<id>[<theme>]`, and because `[`, `]` and `_` are encoded inside the parts, the mapping is one-to-one. Readable ids
  such as `Inputs/Push Button/Default` keep their names: `Inputs__Push Button__Default[Light]`.
- **Containment.** `storybook_session.py`, before each write and each unlink (baseline, `.actual.png`, `.diff.png`), checks that
  `path.resolve()` is relative to the resolved folder. Otherwise it raises `StorybookFailure` naming the story.
- **The default ignore pattern.** `testing/storybook_options.py` `DEFAULT_QT_WARNINGS_IGNORE` becomes
  `(r"^This plugin does not support propagateSizeHints\(\)$",)`. Check the exact message in `tests/test_pytest_plugin.py:443`.
- **Docs.** The help text and `docs/testing.md` say that `storybook_snapshot_dir` and `storybook_snapshot_failures` are relative to the
  rootdir unless absolute.
- **Changelog.** Under `### Changed`: "Snapshot file names encode `_`, `%` and characters that are not letters, digits, spaces, `.` or
  `-`, so two stories never share a baseline and a name never leaves the snapshot folder. Regenerate baselines of stories with such ids
  with `--storybook-update-snapshots`." Under `### Fixed`: the collision and the unanchored ignore pattern.

**Tests.**
- **`tests/test_snapshots.py`:**
  - `snapshot_name` is injective over a list of tricky pairs: `Grp/X` and `Grp__X`, `("A","B][C")` and `("A[B]","C")`, `%41` and `A`, ids
    with `\`, `:`, NUL, `..` and a leading `.`;
  - the result never contains `/`, `\`, `:`, NUL or a control character, and never starts with `.`;
  - the readable example above is unchanged.
- **`tests/test_pytest_plugin.py`:**
  - two stories `Grp/X` and `Grp__X`, run with `--storybook-update-snapshots`, write two files;
  - an id with `..\\..\\x` writes inside the folder on every platform;
  - a Qt warning that merely contains `propagateSizeHints` is no longer ignored by default.
- **Existing tests** that assert file names of ids with `_` or special characters are updated, each listed in the report.

## §4 S4: release pipeline hardening, SECURITY.md and RELEASING.md

**Findings.**
- **Medium.** The build job runs the latest uv, a freshly resolved hatchling and about 27 `twine` dependencies, all unlocked, in the
  job that writes `dist/` before uploading it.
- **Low:**
  - nothing checks that `dist` is unchanged between build and publish;
  - actions are pinned by tag or branch;
  - the `release/*` check is not a security boundary.
- **Hardening:**
  - checkouts keep their credentials;
  - the uv cache is on in the build jobs;
  - `github-release` also runs on a manual run from a tag;
  - the workflow test does not reject `github.head_ref`.

**Fix.**
- **Pin uv.** `pyproject.toml` `[tool.uv] required-version = "==0.11.32"`, the version used now. The implementer checks that
  `astral-sh/setup-uv` v7 reads `required-version` from `pyproject.toml` when `version` is not given; if not, pass `version:` in every
  setup-uv step. Dependabot's uv ecosystem does not update `required-version`, so RELEASING.md's checklist says to bump it on purpose.
- **Pin the build backend.** `[tool.uv] build-constraint-dependencies = ["hatchling==<the version uv build resolves today>"]`. The
  implementer finds it with `uv build -v` or `uv pip compile`.
- **Move `twine check`** out of the build job into its own job in `package.yml`, `metadata`. It downloads `dist` and runs
  `uvx twine==7.0.0 check --strict dist/*`, with an exact version, and never uploads anything. The build job uploads `dist` right after
  the name check.
- **Digests.** The build job computes `sha256sum dist/*` (relative names, run inside `dist/`) and exposes it as a job output and a
  workflow output, `sha256sums`, a multi-line value written with the `<<EOF` delimiter form. `release.yml` `publish` writes it to a
  file before `pypa/gh-action-pypi-publish` and runs `sha256sum -c` inside `dist/`. `verify` and `github-release` do the same check on
  their downloaded `dist` where they use it.
- **Pin every action by SHA.** Every `uses:` of a non-local action becomes `owner/repo@<40-hex SHA> # vX.Y.Z`, where `X.Y.Z` is the
  exact release that the current major tag points to. Find the SHA with `git ls-remote https://github.com/<owner>/<repo> 'refs/tags/vX*'`
  and take the peeled `^{}` SHA of the highest `vX.Y.Z` that matches the current major. For `pypa/gh-action-pypi-publish@release/v1`,
  take the SHA of the latest `v1.x.y` tag. Dependabot's `github-actions` ecosystem keeps SHA pins and their comments up to date.
- **`persist-credentials: false`** on every `actions/checkout`.
- **`enable-cache: false`** on setup-uv in `package.yml` `build` and `metadata` and in `docs.yml` `build`. The other jobs keep the cache.
- **`github-release`** gets `if: github.event_name == 'push' && github.ref_type == 'tag'`.
- **`tests/test_workflows.py`:**
  - rejects `github.head_ref` in `run:` blocks, with `github.event` and `inputs`;
  - checks that every non-local `uses:` is pinned to a 40-character hex SHA with a version comment;
  - checks that every checkout has `persist-credentials: false`;
  - checks that `package.yml` `build` does not run `twine`, and that `publish` runs `sha256sum -c` before the publish action;
  - checks that `github-release`'s `if` names both `push` and `tag`.
- **`SECURITY.md`:** the "running project code" list adds "each story file's own folder, or the folder above its top package, which is
  put first on `sys.path` when the file is imported". `tests/test_community_files.py` checks for `sys.path` in that section.
- **`RELEASING.md`:**
  - the one-time setup makes two rulesets required, not merely recommended: a tag ruleset on `v*` that only maintainers can create, and
    a branch ruleset on `release/*` that only maintainers can create;
  - the approval step tells the approver to compare the run's commit SHA with the release PR's merge commit before approving `pypi`;
  - a line says the `release/*` check in `release_target.py` is a guard against mistakes, not a security boundary.

  `tests/test_releasing.py` gets updated where it checks section text.
- **`AGENTS.md`:** the CI section mentions the digest check, the SHA pins and the uv pin.

**Owner steps** (repository settings, after S4 merges):
- create the `v*` tag ruleset and the `release/*` branch ruleset, as RELEASING.md describes;
- confirm the `pypi` environment's deployment rule still allows `v*` tags.

**Tests** are the `tests/test_workflows.py` additions above, `actionlint` with shellcheck, and `tests/test_releasing.py` and
`tests/test_community_files.py`. The first Release run after merging (a TestPyPI dispatch on `main`) is the end-to-end check of the
digest step. The PR asks the owner to run it.
