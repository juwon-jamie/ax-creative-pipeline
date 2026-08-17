# Multi-Agent Workflow: one owner, two coding agents, file-based handoff

This repository (and the private parent project it was carved out of) is built by **one person directing two coding agents** — Claude Code and Codex CLI — that never talk to each other directly. All coordination goes through a handful of Markdown files that live in the repo. This document describes the protocol, why it looks the way it does, and what broke.

It is written as a reusable pattern, not a product. Copy the `templates/` folder into any repo to start.

## Roles

| Actor | Owns | Never touches |
|---|---|---|
| **Owner (human)** | decisions, numbers that go into public documents, anything irreversible (publish, delete, pay) | — |
| **Agent A — Claude Code** | strategy docs, copy, QA of Agent B's output, **all git commits**, session state | Agent B's directories |
| **Agent B — Codex CLI** | implementation tasks: tools, templates, static site, data structures | strategy docs (read-only), any number that has no source file, git commit (sandbox cannot) |

The split is by *directory* and by *kind of decision*, not by skill. Each agent has one instruction file at the repo root that says exactly this: `CLAUDE.md` for A, `AGENTS.md` for B.

## The channel: three append-only files

```
handoff/
  STATE.md      # single source of truth for "where are we". Each agent updates ONLY its own section.
  TO_CODEX.md   # A -> B task queue. Append-only. Items numbered #C-001, #C-002 ..., each with a "- [ ] done" checkbox.
  TO_CLAUDE.md  # B -> A results & questions. Append-only. Fixed 4-field format: task / files / decisions needed / blockers.
```

Rules that make it work:

1. **Append, never overwrite.** History is the audit log. When A processes an item in `TO_CLAUDE.md` it appends a `-> processed:` line under it instead of editing.
2. **Numbers must trace to a file.** Any figure that appears in a public artifact must point to a file in `evidence/`. Agent B renders `<!-- PENDING: evidence -->` rather than inventing a number.
3. **One session, one visible artifact.** Every run of either agent must leave something the owner can open. Plans that only produce more plans are rejected.
4. **The owner decides; agents propose.** Open decisions are written as checkbox lists in the relevant doc; the owner answers, the agent applies.
5. **Session start ritual.** Both agents read `handoff/STATE.md` first, then their own queue. Session end: update your section of `STATE.md`. That file is the only memory across sessions.

## Running Agent B headlessly

Agent B is launched *by Agent A* (or the owner) as a non-interactive process:

```
codex exec -C <repo> --add-dir <extra writable dir> -s workspace-write -o last_message.md - < prompt.txt
```

The prompt is short: "read AGENTS.md, process items #C-00X..#C-00Y in order, report to TO_CLAUDE.md, do not commit." A typical 7-item queue takes 15-25 minutes. Agent A waits for completion, then QAs.

## QA loop (this is where the value is)

Agent A treats Agent B's output as untrusted:

- **Leak scan** over every new/modified file for anything that must not be public (employer identifiers, e-mail patterns, keys, absolute paths).
- **Dry-run every script** against a fake backend before trusting it. In this project a shell shim standing in for `gh` exposed a real defect on the first pass: a GitHub `stats/*` endpoint answers `202` with an empty body while computing, and the script silently recorded zeros. It was replaced with endpoints that answer immediately.
- **Re-run the tests the agent claims it ran.** Agent B's sandbox lacked test dependencies and reported "passed via shim"; A re-ran under a normal environment before committing.
- **Commit per task item**, with the item number in the message, so the history reads like the queue.

## What broke, and the fix

| Problem | Fix |
|---|---|
| Agent B's sandbox cannot create `.git/index.lock`; any `.git` it initializes is owned by the sandbox user | Agent B never commits. A re-inits and commits. This turned out to be a feature: one committer, one QA gate. |
| Two crawlers writing the same JSONL concurrently overwrote each other | Board sources run in the same process as query sources; no concurrent writers to a corpus file. |
| Agent B's default lint rules differ from CI's | Pin the rule set in `ruff.toml` in the repo; never rely on tool defaults. |
| Free-text agent notes drifted into strategy docs | Strategy docs are read-only for B; proposals go to `TO_CLAUDE.md` as text, A decides. |

## Why not let the agents talk directly?

Because the owner needs to be able to read the whole conversation later, and because a file queue forces each agent to state its input and output explicitly. Latency is worse; auditability and recoverability are much better. For a solo owner running agents in the evening, recoverability wins.

## Templates

- `templates/AGENTS.md` — instructions for the implementation agent
- `templates/CLAUDE.md` — instructions for the strategy/QA agent
- `templates/handoff/STATE.md`, `TO_CODEX.md`, `TO_CLAUDE.md` — the channel

Names are placeholders; the pattern does not depend on the specific vendors.
