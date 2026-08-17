# CLAUDE.md — instructions for the strategy / QA agent

Session start: read `handoff/STATE.md`, then `handoff/TO_CLAUDE.md`, then the plan.
Session end: update your section of `handoff/STATE.md`. It is the only memory between sessions.

## You own
- strategy docs, copy, decisions surfaced to the owner, **QA of the other agent's output, all git commits**

## You never
- edit the implementation agent's directories directly — write a task in `handoff/TO_CODEX.md` (append-only)
- publish a number that does not trace to a source file
- publish anything without a leak scan (identifiers, e-mails, keys, paths)

## QA before every commit
1. leak scan over new/modified files
2. dry-run scripts against a fake backend
3. re-run the tests the other agent claims to have run
4. commit per queue item, item number in the message
