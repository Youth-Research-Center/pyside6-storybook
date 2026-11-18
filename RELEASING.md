# Releasing pyside6-storybook

This guide is for a maintainer who has never released the project. A release is made by two GitHub Actions workflows:

- `.github/workflows/package.yml` builds the wheel and the sdist and smoke tests them;
- `.github/workflows/release.yml` publishes them with a PyPI trusted publisher (no token), installs the published files on Linux,
  Windows and macOS, runs `scripts/smoke/smoke_check.py` on them, and for a tag creates the GitHub release.

What a version number promises is on the page
[Versions and compatibility](https://youth-research-center.github.io/pyside6-storybook/versions/).

Which index a run publishes to is decided by `scripts/release/release_target.py`:

| Trigger | Publishes to | GitHub environment |
| --- | --- | --- |
| Actions → Release → Run workflow (a manual run, on any ref) | TestPyPI | `testpypi` |
| Pushing a tag `v*` | PyPI | `pypi` |

For a tag, the script fails the run unless the tag is `v` plus the version in `pyproject.toml` (`v0.1.0rc1` for `0.1.0rc1`) and the
tagged commit is on `main` or a `release/*` branch. The message names both values.

A release candidate goes to both indexes: first to TestPyPI as a dry run, then to PyPI by its tag, which claims the name and exercises
the whole PyPI path. pip ignores a pre-release unless asked (`--pre`), so a candidate on PyPI does not reach users by accident. A final
release goes to PyPI only.

**Every version change is followed by `uv lock`.** CI runs `uv sync --locked`, which fails when `uv.lock` still has the old version.

## One-time setup

Done once by the repository owner, before the first release.

### PyPI accounts

pypi.org and test.pypi.org are separate sites with separate accounts. On each:

1. Create an account and verify its e-mail address.
2. Turn on two-factor authentication (Account settings → Two factor authentication).
3. Open Your account → Publishing, and add a **pending trusted publisher** (the project does not exist yet, so it is "pending"):

   | Field | pypi.org | test.pypi.org |
   | --- | --- | --- |
   | PyPI project name | `pyside6-storybook` | `pyside6-storybook` |
   | Owner | `Youth-Research-Center` | `Youth-Research-Center` |
   | Repository name | `pyside6-storybook` | `pyside6-storybook` |
   | Workflow name | `release.yml` | `release.yml` |
   | Environment name | `pypi` | `testpypi` |

The first upload from the workflow creates the project and turns the pending publisher into a normal one.

### GitHub environments

Repository settings → Environments → New environment. The names are the ones `release_target.py` writes in `INDEXES`.

- **`testpypi`:**
  - no required reviewers;
  - Deployment branches and tags: **Selected branches and tags**, with two rules: branch `main` and branch `release/*`.
- **`pypi`:**
  - Required reviewers: the owner;
  - Deployment branches and tags: **Selected branches and tags**, with one rule: Ref type **Tag**, pattern `v*`.

### Pages

Repository settings → Pages → Build and deployment → Source: **GitHub Actions**. `docs.yml` publishes the documentation site from there.

### Recommended

- Settings → Rules → Rulesets: a tag ruleset on `v*`, so that only maintainers can create release tags.
- Required status checks on `main`: the lint job and the core tests only. `package.yml` and `docs.yml` have paths filters, and a required
  check that does not run blocks the pull request.

## Before a release

1. CI is green on `main`.
2. The Full test suite has passed on `main`: Actions → Full test suite → Run workflow, branch `main`.
3. The milestone's issues are closed.
4. Every user-facing change has its entry under `[Unreleased]` in `CHANGELOG.md`.

## A release candidate

For version `X.Y.Z`, the first candidate is `X.Y.Zrc1`.

1. Open a pull request that sets `version = "X.Y.Zrc1"` in `pyproject.toml`, then run:

   ```bash
   uv lock
   git add pyproject.toml uv.lock
   ```

   The changelog stays `## [Unreleased]`: a candidate has no section of its own, and the release notes of a pre-release are taken from
   `[Unreleased]`. Merge the pull request.
2. Actions → Release → Run workflow, on branch `main`. It builds, smoke tests, publishes to TestPyPI and installs the published wheel on
   three systems.
3. Check the TestPyPI page `https://test.pypi.org/project/pyside6-storybook/X.Y.Zrc1/`: the README, the screenshot, the licence, the
   links and the classifiers.
4. On Windows, macOS and Linux, install from TestPyPI in a fresh virtual environment. Only the project's own file comes from TestPyPI;
   its dependencies come from PyPI, so a package squatted on TestPyPI is never installed:

   ```bash
   python -m venv venv
   venv/bin/python -m pip download --no-deps --only-binary :all: --index-url https://test.pypi.org/simple/ \
     --dest testpypi "pyside6-storybook==X.Y.Zrc1"
   venv/bin/python -m pip install "testpypi/<wheel file name>[pytest]"
   ```

   On Windows the interpreter is `venv\Scripts\python.exe`. Then check by hand:

   ```bash
   venv/bin/pyside6-storybook --examples
   venv/bin/pyside6-storybook path/to/stories
   venv/bin/python -m pytest --storybook path/to/project
   ```

   In the gallery, switch the theme and edit a control.
5. If all is well, tag the same commit that the workflow ran on and push the tag:

   ```bash
   git switch main
   git pull --ff-only
   git tag -a vX.Y.Zrc1 -m "X.Y.Zrc1"
   git push origin vX.Y.Zrc1
   ```

   The run waits for the `pypi` environment: Actions → the Release run → Review deployments → approve. It then publishes to PyPI,
   verifies the install from PyPI on three systems and creates a GitHub pre-release.
6. A problem: fix it on `main` and repeat from step 1 with `X.Y.Zrc2`. A version number is used once.

## The release

1. Open a pull request that:
   - sets `version = "X.Y.Z"` in `pyproject.toml`;
   - renames `## [Unreleased]` to `## [X.Y.Z] - YYYY-MM-DD` in `CHANGELOG.md` and adds a new empty `## [Unreleased]` above it;
   - updates the link references at the bottom of `CHANGELOG.md`: `[Unreleased]` compares `vX.Y.Z` with `main`, and `[X.Y.Z]` links to
     `https://github.com/Youth-Research-Center/pyside6-storybook/releases/tag/vX.Y.Z`;
   - runs `uv lock`:

   ```bash
   uv lock
   git add pyproject.toml CHANGELOG.md uv.lock
   ```

   Merge it.
2. Tag the merge commit and push the tag:

   ```bash
   git switch main
   git pull --ff-only
   git tag -a vX.Y.Z -m "X.Y.Z"
   git push origin vX.Y.Z
   ```

3. Approve the `pypi` deployment (Actions → the Release run → Review deployments). The workflow publishes to PyPI, installs the published
   files on three systems, runs the smoke script, and creates the GitHub release with the section `## [X.Y.Z]` as its notes.

## After the release

1. Check the PyPI page `https://pypi.org/project/pyside6-storybook/X.Y.Z/` and the GitHub release.
2. After the first upload only: the project belongs to the account that published it. On pypi.org, Manage → Collaborators, add a second
   owner, or create a PyPI organization and move the project to it, so that the project does not depend on one person.
3. Set the repository's About box: the website (the documentation site, `https://youth-research-center.github.io/pyside6-storybook/`),
   the PyPI link and the topics.
4. Open the next development cycle with a pull request that sets `version = "X.(Y+1).0.dev0"`, keeps `## [Unreleased]` empty, and runs:

   ```bash
   uv lock
   git add pyproject.toml uv.lock
   ```

## A patch release

A patch is made on a branch `release/X.Y.x`, never from `main`: `main` may carry breaking changes of the next minor release. Fix the
bug on `main` first.

1. Create the branch from the first release's tag, if it does not exist yet, and push it:

   ```bash
   git switch -c release/X.Y.x vX.Y.0
   git push -u origin release/X.Y.x
   ```

2. Cherry-pick the fixes from `main`, set `version = "X.Y.Z"` (the next patch number), add its `## [X.Y.Z] - YYYY-MM-DD` section to
   `CHANGELOG.md` on the branch, and run:

   ```bash
   git cherry-pick <fix commit>
   uv lock
   git add pyproject.toml CHANGELOG.md uv.lock
   ```

   Open the pull request against `release/X.Y.x` and merge it. Add the same changelog section and link references on `main` too.
3. Tag the branch's tip and push the tag. `release_target.py` accepts a commit on a `release/*` branch:

   ```bash
   git switch release/X.Y.x
   git pull --ff-only
   git tag -a vX.Y.Z -m "X.Y.Z"
   git push origin vX.Y.Z
   ```

4. Approve the `pypi` deployment. The `pypi` environment accepts the tag `v*` whatever branch it is on.

## A broken release

PyPI never accepts a version number twice, even after a file was deleted. So a published release is never deleted:

1. Yank the broken version on pypi.org: the project → Manage → the release → Options → Yank, and write the reason. A yanked release is
   skipped by pip unless it is pinned exactly.
2. Fix the problem and release the next patch number (see "A patch release", or the release steps above when `main` has nothing else
   in it).
3. Say what was wrong under `### Fixed` in the new section of the changelog.

## A failed run

Open the run in Actions and see which job failed. The jobs run in this order: `target`, `package`, `publish`, `verify`,
`github-release`.

- **Before `publish`** (`target`, `package`): nothing was uploaded.
  - A tag that does not match the version, or a commit that is on no `main` or `release/*` branch, fails `target`. Delete the tag
    locally and on the remote (`git tag -d vX.Y.Z` and `git push origin :refs/tags/vX.Y.Z`), fix the version or the branch, and tag
    again. Or, when the candidate's version has to change, push a new candidate tag.
  - A failing smoke job in `package` is a real problem in the package: fix it on `main` and release the next candidate.
  - Re-run the workflow (Re-run all jobs, or Run workflow again for TestPyPI) once it is fixed.
- **During `publish`:** use Re-run failed jobs. It uploads the same `dist` artifact, and PyPI accepts a file that it already has with
  the same name and content. If PyPI refuses anyway, release the next number.
- **After `publish`** (`verify`, `github-release`): the files are on the index. Use Re-run failed jobs, which runs `verify` or
  `github-release` alone. A `verify` failure that persists means the published package is broken: see "A broken release".
