from pathlib import Path
from tempfile import TemporaryDirectory

from pipeline.common import read_jsonl
from pipeline.retry import failures_from_judgments, record_retry_attempts


def test_failures_from_judgments_extracts_only_f_codes():
    rows = [
        {"clip_id": "clip_01", "usable": False, "fail_codes": ["F1"], "p7_reason": "bad shape"},
        {"clip_id": "clip_02", "usable": False, "pass_fail_codes": ["P6"]},
        {"clip_id": "clip_03", "usable": True, "fail_codes": ["F2"]},
    ]

    failures = failures_from_judgments(rows)

    assert failures == [{"asset_id": "clip_01", "code": "F1", "reason": "bad shape"}]


def test_record_retry_attempts_respects_max_retries():
    with TemporaryDirectory(dir=Path.cwd()) as raw_tmp:
        tmp_path = Path(raw_tmp)
        policy_path = tmp_path / "retry.yaml"
        policy_path.write_text(
            """
defaults:
  max_retries: 1
  action: retry
  prompt_adjustment: "fix {code} for {asset_id}"
codes:
  F1:
    max_retries: 1
    action: simplify
""",
            encoding="utf-8",
        )
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        failures = [{"asset_id": "clip_01", "code": "F1", "reason": "bad shape"}]

        record_retry_attempts(run_dir, "judge", failures, policy_path)
        record_retry_attempts(run_dir, "judge", failures, policy_path)

        rows = read_jsonl(run_dir / "attempts.jsonl")
        assert len(rows) == 1
        assert rows[0]["attempt_no"] == 1
        assert rows[0]["action"] == "simplify"
