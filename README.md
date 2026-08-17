# ax-creative-pipeline

Clean-room miniature of an AI creative production pipeline for a fictional Brand Zero campaign.

This repository is unrelated to any employer codebase, client asset, private prompt, production model configuration, or internal operating document. It is a reduced-scale implementation designed to show the method, not any proprietary system.

## What This Proves / Does Not

| Proves | Does not prove |
|---|---|
| A creative pipeline can be represented as reproducible code: plan -> image -> gate -> render -> evaluate -> aggregate. | Any private production result or internal conversion number. |
| "Usable clip" can be scored against documented criteria in `criteria/usability_v1.md`. | The scale, vendor choices, cost model, or architecture of any private system. |
| The workflow is portable: swap one brand YAML, one brief YAML, and one adapter. | Large-scale throughput. |
| Retry and evaluation policy are explicit enough for review and benchmark comparison. | That generated sample media is production media. No media is committed. |

## Architecture

```text
brand/brand_zero.yaml + briefs/campaign_01.yaml
  -> pipeline.plan       scene cards and prompt hashes
  -> pipeline.generate   manual request/ingest or direct adapter
  -> pipeline.gate       rules + manual video-readiness gate
  -> pipeline.render     manual request/ingest or direct adapter
  -> pipeline.judge      manual usability CSV -> judge.jsonl
  -> pipeline.evaluate   rules + optional VLM JSONL + human CSV -> final verdicts
  -> pipeline.retry      F1-F7 policy -> attempts.jsonl
  -> pipeline.aggregate  summary.md and benchmark.md
```

Adapters live behind a small interface:

- `AX_PIPELINE_VENDOR=manual` writes request files and ingests manifests.
- `AX_PIPELINE_VENDOR=http_generic` POSTs JSON to `IMAGE_MODEL_URL` or `VIDEO_MODEL_URL`, then saves a returned URL or base64 artifact.
- Field mappings are in `adapters/vendors/mapping.yaml`.
- Real keys belong only in `.env`; `.env.example` lists names only.

The evaluation harness has three inputs. Rule checks validate manifest coherence and declared specs. A VLM slot can provide JSONL shaped by `criteria/judge_prompt.md`. Human CSV remains the highest-priority source for the final verdict. Agreement reports use simple agreement and Cohen's kappa.

## Run in 60 Seconds

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt pytest ruff
python -m pytest
python -m ruff check .
python run.py --run-id example --stage aggregate
```

On Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt pytest ruff
python -m pytest
python -m ruff check .
python run.py --run-id example --stage aggregate
```

Run the committed no-media benchmark:

```bash
python run.py --run-id example --stage aggregate --compare-runs example,example_nogate
```

## Manual Workflow

```bash
python run.py --brief briefs/campaign_01.yaml --run-id demo01 --stage plan
python run.py --run-id demo01 --stage generate --mode request
# Generate images with any model, then write runs/demo01/images/manifest.json.
python run.py --run-id demo01 --stage generate --mode ingest
python run.py --run-id demo01 --stage gate
python run.py --run-id demo01 --stage render --mode request
# Render clips with any model, then write runs/demo01/clips/manifest.json.
python run.py --run-id demo01 --stage render --mode ingest
python run.py --run-id demo01 --stage judge --resume
python run.py --run-id demo01 --stage evaluate --resume
python run.py --run-id demo01 --stage aggregate
```

`--resume` reuses completed stage outputs when present. For `judge` and `evaluate`, it also records retryable F1-F7 failures in `runs/<id>/attempts.jsonl` according to `policies/retry.yaml`.

## Direct HTTP Adapter

```bash
AX_PIPELINE_VENDOR=http_generic python run.py --run-id demo01 --stage generate --mode direct
AX_PIPELINE_VENDOR=http_generic python run.py --run-id demo01 --stage render --mode direct
```

The generic HTTP adapter expects JSON responses containing a mapped URL or base64 field. It does not name or depend on any specific vendor SDK.


## Real-media run: `runs/demo01/` (2026-08-17)

First pass with real image and video models (vendors abstracted behind the adapters; 64.5 credits total).

| generated_images | gate_pass | render_attempts | usable_clips | conversion (usable / generated) |
|---:|---:|---:|---:|---:|
| 6 | 3 | 3 | 2 | 33.3% |

**What the gate caught, unstaged:** 3 of 6 images came back as 3-panel storyboards because the image prompt
carried "Start state ... End state ..." wording. The gate rejected them (`runs/demo01/judgments/gate_manual.csv`),
and the learning loop turned that into a template fix in `pipeline/plan.py` (image prompt = one frame, start state
only; end state lives in the video prompt) with a regression test. Small previews of every frame and clip are in
`runs/demo01/media_small/`; notes in `runs/demo01/RUN_NOTES.md`. Full-size media stays out of git.

Compare runs: `python run.py --run-id demo01 --stage aggregate --compare-runs demo01,example,example_nogate` -> `reports/benchmark.md`.

## Design Boundary

- No company code.
- No real brand, account, patient, campaign, path, or model/API name.
- No generated production media in the repository.
- `runs/example/` and `runs/example_nogate/` are committed no-media runs; other runs are ignored.
