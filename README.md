# ax-creative-pipeline

Clean-room miniature of an AI creative production pipeline for a fictional Brand Zero campaign.

| 증명한다 | 증명하지 않는다 |
|---|---|
| 방법론(생성 -> 영상화 가능성 게이트 -> 렌더 -> 실패 분류 -> 월별 집계)을 재현 가능한 코드로 쓸 수 있다 | 회사에서의 4% -> 32% 수치 |
| "사용 가능" 판정이 문서화된 기준(`criteria/usability_v1.md`)으로 돌아간다 | 회사 시스템의 규모(18단계, 9채널) |
| 다른 조직과 다른 브랜드에 이식할 수 있다. 브랜드 설정 파일 하나를 바꾸면 돈다 | 대규모 처리 성능 |
| 개인 계정에 공개 가능한 2026-08~09 활동 기록이 생긴다 | 회사 코드나 회사 자산의 공개 |

This repository is unrelated to any employer codebase, client asset, private prompt, production model configuration, or internal operating document. It is a clean-room, reduced-scale implementation designed to show the method, not the proprietary system.

## What Runs

```text
brand/brand_zero.yaml + briefs/campaign_01.yaml
  -> pipeline.plan
  -> pipeline.generate  (request files, then manifest ingest)
  -> pipeline.gate
  -> pipeline.render    (request files, then manifest ingest)
  -> pipeline.judge     (manual usability CSV -> JSONL)
  -> pipeline.aggregate
```

The current W2 pass is file-based. It does not call a vendor SDK or require an API key. Generate images with any model, drop the results into `runs/<id>/images/`, and record `manifest.json`. Render works the same way through `runs/<id>/requests/videos/` and `runs/<id>/clips/manifest.json`.

## 30-Second Setup

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt pytest ruff
python -m pytest
```

No API key is required for the local checks. Real keys belong only in `.env`, never in git.

Run the committed no-media example:

```bash
python run.py --run-id example --stage aggregate
```

Start a new run:

```bash
python run.py --brief briefs/campaign_01.yaml --run-id demo01 --stage plan
python run.py --run-id demo01 --stage generate --mode request
# Generate images with any model, then write runs/demo01/images/manifest.json.
python run.py --run-id demo01 --stage generate --mode ingest
python run.py --run-id demo01 --stage gate
python run.py --run-id demo01 --stage render --mode request
# Render clips with any model, then write runs/demo01/clips/manifest.json.
python run.py --run-id demo01 --stage render --mode ingest
python run.py --run-id demo01 --stage judge
python run.py --run-id demo01 --stage aggregate
```

## Design Boundary

- No company code.
- No real brand, account, patient, campaign, path, or model/API name.
- No generated production media in the repository.
- `runs/example/` is the only committed run directory; other runs are ignored.
