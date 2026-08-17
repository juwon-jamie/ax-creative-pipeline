# AGENTS.md — instructions for the implementation agent

Read in this order before doing anything:
1. `handoff/STATE.md` — where the project is
2. `handoff/TO_CODEX.md` — your task queue (top-down, unfinished items only)
3. The strategy docs listed there — **read-only** for you

## You own
- implementation directories (e.g. `tools/`, `web/`, `evidence/` templates)

## You never
- edit strategy docs; propose changes as text in `handoff/TO_CLAUDE.md`
- render a number that has no source file — write `<!-- PENDING: evidence -->`
- commit or push (sandbox restriction; the other agent commits after QA)
- put secrets, real names, or absolute paths in any file

## Reporting
Append to `handoff/TO_CLAUDE.md`, never overwrite:
```
## [YYYY-MM-DD] #C-00X
- task:
- files:
- decisions needed:
- blockers:
```
Then mark the item `- [x] done` in `TO_CODEX.md` and add one line to your section of `STATE.md`.
If unsure, do not act — leave a question in `TO_CLAUDE.md`.
