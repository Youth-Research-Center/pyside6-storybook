## What and why

<!-- What does this pull request change, and why? Link the issue: "Closes #N" only when it fully resolves it, otherwise "Refs #N". -->

## How it was tested

<!-- The tests you added or ran, and anything you checked by hand. Add screenshots for changes to the gallery. -->

## Checklist

- [ ] `uv run ruff check .` and `uv run ty check` pass
- [ ] `QT_QPA_PLATFORM=offscreen uv run pytest` passes
- [ ] New behaviour has tests, and a bug fix has a regression test that fails without the fix
- [ ] User-facing changes have an entry under `[Unreleased]` in `CHANGELOG.md`
- [ ] Docs (`docs/`, `README.md`) are updated where behaviour changed
- [ ] Screenshots are included for visible changes to the gallery
