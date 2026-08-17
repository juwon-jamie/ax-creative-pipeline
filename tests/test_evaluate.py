from pathlib import Path
from tempfile import TemporaryDirectory

from pipeline.common import read_jsonl, write_json, write_jsonl
from pipeline.evaluate import agreement_by_source, automatic_rule_judgments, evaluate_run


def _write_minimal_run(run_dir: Path) -> None:
    write_json(
        run_dir / "plan.json",
        {
            "scenes": [
                {
                    "scene_id": "scene_01",
                    "aspect_ratio": "9:16",
                    "duration_seconds": 5,
                    "resolution": "1080x1920",
                }
            ]
        },
    )
    write_jsonl(
        run_dir / "gate.jsonl",
        [{"image_id": "img_01", "scene_id": "scene_01", "video_ready": True}],
    )
    write_json(
        run_dir / "clips" / "manifest.json",
        {
            "clips": [
                {
                    "clip_id": "clip_01",
                    "image_id": "img_01",
                    "file": "clip_01.mp4",
                    "aspect_ratio": "9:16",
                    "duration_seconds": 5,
                    "resolution": "1080x1920",
                }
            ]
        },
    )


def test_automatic_rule_judgments_passes_matching_manifest():
    with TemporaryDirectory(dir=Path.cwd()) as raw_tmp:
        run_dir = Path(raw_tmp) / "run"
        _write_minimal_run(run_dir)

        judgments = automatic_rule_judgments(run_dir)

        assert judgments["clip_01"]["verdict"] == "USABLE"


def test_evaluate_run_prefers_human_over_rules_and_writes_agreement():
    with TemporaryDirectory(dir=Path.cwd()) as raw_tmp:
        tmp_path = Path(raw_tmp)
        run_dir = tmp_path / "run"
        _write_minimal_run(run_dir)
        human_csv = run_dir / "judgments" / "usability.csv"
        human_csv.parent.mkdir(parents=True)
        human_csv.write_text(
            "clip_id,verdict,fail_codes,pass_fail_codes,p7_reason\n"
            "clip_01,NOT_USABLE,F5,,too static\n",
            encoding="utf-8",
        )

        evaluate_run(run_dir, run_dir / "evaluate.jsonl", agreement_path=tmp_path / "agreement.md")

        rows = read_jsonl(run_dir / "evaluate.jsonl")
        assert rows[0]["final_source"] == "human"
        assert rows[0]["fail_codes"] == ["F5"]
        assert "rules_vs_human" in (tmp_path / "agreement.md").read_text(encoding="utf-8")


def test_agreement_by_source_calculates_binary_metrics():
    rows = [
        {
            "sources": {
                "rules": {"verdict": "USABLE"},
                "human": {"verdict": "USABLE"},
            }
        },
        {
            "sources": {
                "rules": {"verdict": "USABLE"},
                "human": {"verdict": "NOT_USABLE"},
            }
        },
    ]

    result = agreement_by_source(rows, "rules", "human")

    assert result["count"] == 2
    assert result["agreement"] == 0.5
