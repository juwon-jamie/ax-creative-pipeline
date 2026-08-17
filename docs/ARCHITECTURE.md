# Architecture

This is a clean-room, reduced-scale creative pipeline. It proves method and
operating contracts, not any private production system, private vendor setup, or
internal media asset.

## Stage Map

```text
brand/brand_zero.yaml + briefs/campaign_01.yaml
  -> plan.json
  -> requests/images/*.json
  -> images/manifest.json
  -> gate.jsonl
  -> requests/videos/*.json
  -> clips/manifest.json
  -> judge.jsonl
  -> evaluate.jsonl
  -> reports/summary.md
```

The `agent/` layer runs the same stages as a loop:

```text
Planner -> Tools -> Evaluator
    ^        |          |
    |        v          v
  Memory <- retry <- aggregate
```

## Adapter Boundary

The core pipeline knows only stable interfaces:

- `ImageModel.generate(prompt, reference_images, output_dir) -> list[Path]`
- `VideoModel.render(image_path, motion_prompt, output_dir) -> Path`
- `Judge.score(clip_path, criteria_path) -> dict`

Manual mode writes request files and validates manifests. HTTP mode posts generic
JSON and saves a returned URL or base64 artifact. LLM judging uses a
chat-completions-compatible endpoint, a fixed prompt in `criteria/judge_prompt.md`,
and strict JSON schema checks before results can enter `evaluate.jsonl`.

## Data Contracts

`plan.json` stores scene cards. Required scene fields are `scene_id`, `subject`,
`motion`, `camera`, `start_state`, `end_state`, `image_prompt_hash`, aspect ratio,
duration, and resolution.

`images/manifest.json` stores:

```json
{"images": [{"image_id": "img_01", "scene_id": "scene_01", "file": "img.png", "prompt_hash": "abc"}]}
```

`gate.jsonl` stores one image decision per row:

```json
{"image_id": "img_01", "scene_id": "scene_01", "video_ready": true, "no_gate": false, "reason": ""}
```

`clips/manifest.json` stores:

```json
{"clips": [{"clip_id": "clip_01", "image_id": "img_01", "file": "clip.mp4", "aspect_ratio": "9:16"}]}
```

`judge.jsonl` and `evaluate.jsonl` use `verdict`, `usable`, `fail_codes`,
`pass_fail_codes`, `p7_reason`, and `reason`. `evaluate.jsonl` also records
source judgments from rules, LLM/VLM, and human CSV when present.

`memory.jsonl` is append-only agent memory: attempts, tool calls, external waits,
retry scheduling, and terminal status.

## Evaluation

Evaluation combines three sources:

- rules: manifest coherence and declared specs
- LLM/VLM: optional JSONL or `llm_http` adapter output
- human: manual CSV, highest priority

Agreement reports compare rules vs human and LLM/VLM vs human using simple
agreement and Cohen's kappa.

## Benchmark

`python -m bench.run` creates nine no-media runs:

- briefs: easy, normal, hard
- policies: no-gate, gate, gate+retry

The benchmark writes `reports/agent_benchmark.md` with conversion rate, attempts,
average retries, cost units, and failure code distribution.

## ADR 1: Request/Ingest Vendor Boundary

Decision: generated media is exchanged through request files and manifests.

Reason: this keeps vendor SDKs, accounts, keys, and transient model behavior out
of the repository. The same pipeline can be driven by manual UI, local mock, or a
generic HTTP adapter without changing planning, gate, render, or evaluation code.

## ADR 2: Conversion Denominator

Decision: conversion rate is `usable_clips / generated_images`.

Reason: the gate is part of the production system. Using render attempts as the
denominator would hide rejected images and overstate the system outcome. Generated
images are the stable unit that exists before gate, render, and retry choices.

## ADR 3: Three-Source Judgment

Decision: final judgment is selected from human, then LLM/VLM, then rules.

Reason: rules catch schema and spec problems cheaply, LLM/VLM can inspect richer
semantic failures, and human CSV remains the auditable review source. Keeping all
three sources in `evaluate.jsonl` makes disagreements reviewable instead of
silently collapsed.

