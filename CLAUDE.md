# pyside6-storybook - Claude Code Instructions

@AGENTS.md

## Claude Code Notes
- `AGENTS.md` is the single source of truth for conventions. Change shared guidance there; keep this file for Claude Code-specific notes.
- Follow existing patterns and keep changes focused; do not add abstractions the task does not need.
- For a bug, reproduce it with a failing test first, then fix it.
- Before declaring work done, run `uv run ruff check .`, `uv run ruff check --select W291,W292,W293 <files you changed>` and the relevant tests
  with `QT_QPA_PLATFORM=offscreen`, and report failures honestly.
- Verify a review finding against the code before acting on it, and reproduce it when you can. If it is wrong, reply with the evidence
  instead of changing the code.
- When asked to review a pull request, report findings in chat first; post to GitHub only when explicitly asked.
