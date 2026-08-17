from pathlib import Path
from tempfile import TemporaryDirectory

from pipeline.aggregate import aggregate_run
from pipeline.common import write_json, write_jsonl


def test_aggregate_uses_generated_images_as_conversion_denominator():
    with TemporaryDirectory(dir=Path.cwd()) as raw_tmp:
        tmp_path = Path(raw_tmp)
        _assert_aggregate_uses_generated_images_as_conversion_denominator(tmp_path)


def _assert_aggregate_uses_generated_images_as_conversion_denominator(tmp_path):
    run_dir = tmp_path / "demo"
    (run_dir / "images").mkdir(parents=True)
    (run_dir / "requests" / "videos").mkdir(parents=True)
    write_json(
        run_dir / "images" / "manifest.json",
        {
            "images": [
                {"image_id": "img_01"},
                {"image_id": "img_02"},
                {"image_id": "img_03"},
            ]
        },
    )
    write_jsonl(
        run_dir / "gate.jsonl",
        [
            {"image_id": "img_01", "video_ready": True, "no_gate": False},
            {"image_id": "img_02", "video_ready": True, "no_gate": False},
            {"image_id": "img_03", "video_ready": False, "no_gate": False},
        ],
    )
    write_json(run_dir / "requests" / "videos" / "img_01.json", {})
    write_json(run_dir / "requests" / "videos" / "img_02.json", {})
    write_jsonl(
        run_dir / "judge.jsonl",
        [
            {"clip_id": "clip_01", "usable": True},
            {"clip_id": "clip_02", "usable": False},
        ],
    )
    report_path = tmp_path / "summary.md"

    aggregate_run(run_dir, report_path)

    report = report_path.read_text(encoding="utf-8")
    assert "| demo | on | 3 | 2 | 2 | 1 | 33.3% |" in report
