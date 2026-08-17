from pathlib import Path
from tempfile import TemporaryDirectory

from pipeline.aggregate import aggregate_benchmark
from pipeline.common import write_json, write_jsonl


def test_aggregate_benchmark_compares_gate_modes_and_retries():
    with TemporaryDirectory(dir=Path.cwd()) as raw_tmp:
        tmp_path = Path(raw_tmp)
        run_on = tmp_path / "on"
        run_off = tmp_path / "off"
        for run_dir, no_gate in ((run_on, False), (run_off, True)):
            write_json(run_dir / "images" / "manifest.json", {"images": [{"image_id": "img"}]})
            write_jsonl(
                run_dir / "gate.jsonl",
                [{"image_id": "img", "video_ready": True, "no_gate": no_gate}],
            )
            write_json(run_dir / "requests" / "videos" / "img.json", {})
            write_jsonl(run_dir / "judge.jsonl", [{"clip_id": "clip", "usable": True}])
        write_jsonl(run_off / "attempts.jsonl", [{"attempt_no": 1, "code": "F6"}])

        aggregate_benchmark([run_on, run_off], tmp_path / "benchmark.md")

        report = (tmp_path / "benchmark.md").read_text(encoding="utf-8")
        assert "| on | on | manual |" in report
        assert "| off | off | manual |" in report
        assert "| off | off | manual | 1 | 1 | 1 | 1 | 100.0% | retry.yaml | 1 | 1.00 |" in report
