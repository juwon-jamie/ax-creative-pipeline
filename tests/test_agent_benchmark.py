from pathlib import Path
from tempfile import TemporaryDirectory

from bench.run import POLICIES, SCENARIOS, create_benchmark_run, run_benchmark
from pipeline.aggregate import run_metrics


def test_create_benchmark_run_writes_no_media_contracts():
    with TemporaryDirectory(dir=Path.cwd()) as raw_tmp:
        tmp_path = Path(raw_tmp)

        run_dir = create_benchmark_run(SCENARIOS[0], "gate", tmp_path / "runs")

        assert (run_dir / "plan.json").exists()
        assert (run_dir / "images" / "manifest.json").exists()
        assert (run_dir / "clips" / "manifest.json").exists()
        assert not list(run_dir.rglob("*.mp4"))
        assert not list(run_dir.rglob("*.png"))


def test_run_benchmark_creates_full_matrix_and_report():
    with TemporaryDirectory(dir=Path.cwd()) as raw_tmp:
        tmp_path = Path(raw_tmp)

        report_path = run_benchmark(tmp_path / "runs", tmp_path / "agent_benchmark.md")

        report = report_path.read_text(encoding="utf-8")
        assert len(list((tmp_path / "runs").glob("bench_*"))) == len(SCENARIOS) * len(POLICIES)
        assert "bench_hard_gate_retry" in report
        assert "cost_units" in report


def test_gate_retry_benchmark_records_attempts():
    with TemporaryDirectory(dir=Path.cwd()) as raw_tmp:
        tmp_path = Path(raw_tmp)

        run_dir = create_benchmark_run(SCENARIOS[1], "gate_retry", tmp_path / "runs")
        metrics = run_metrics(run_dir)

        assert metrics["attempts"] >= 1
        assert float(metrics["avg_retries"]) > 0

