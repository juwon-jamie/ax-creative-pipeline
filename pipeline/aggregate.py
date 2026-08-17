"""Aggregate run metrics into a summary report."""

from __future__ import annotations

from collections import Counter
from pathlib import Path

from pipeline.common import read_json, read_jsonl


def _count_images(run_dir: Path) -> int:
    manifest_path = run_dir / "images" / "manifest.json"
    if manifest_path.exists():
        manifest = read_json(manifest_path)
        entries = manifest.get("images", manifest)
        if not isinstance(entries, list):
            raise ValueError("images manifest must be a list or contain images list")
        return len(entries)
    return len({row["image_id"] for row in read_jsonl(run_dir / "gate.jsonl")})


def _count_video_requests(run_dir: Path) -> int:
    request_dir = run_dir / "requests" / "videos"
    if request_dir.exists():
        return len(list(request_dir.glob("*.json")))
    manifest_path = run_dir / "clips" / "manifest.json"
    if manifest_path.exists():
        manifest = read_json(manifest_path)
        entries = manifest.get("clips", manifest)
        if not isinstance(entries, list):
            raise ValueError("clip manifest must be a list or contain clips list")
        return len(entries)
    return 0


def _format_rate(numerator: int, denominator: int) -> str:
    if denominator == 0:
        return ""
    return f"{numerator / denominator:.1%}"


def _read_optional_json(path: Path) -> dict[str, object]:
    if not path.exists():
        return {}
    data = read_json(path)
    if not isinstance(data, dict):
        return {}
    return data


def run_metrics(run_dir: Path) -> dict[str, object]:
    """Return aggregate metrics for one run directory."""
    gate_rows = read_jsonl(run_dir / "gate.jsonl")
    judge_rows = read_jsonl(run_dir / "judge.jsonl")
    if not judge_rows:
        judge_rows = read_jsonl(run_dir / "evaluate.jsonl")
    attempts = read_jsonl(run_dir / "attempts.jsonl")
    generated_images = _count_images(run_dir)
    gate_pass = sum(1 for row in gate_rows if row.get("video_ready"))
    render_attempts = _count_video_requests(run_dir)
    usable_clips = sum(1 for row in judge_rows if row.get("usable"))
    gate_mode = "off" if any(row.get("no_gate") for row in gate_rows) else "on"
    conversion_rate = _format_rate(usable_clips, generated_images)
    failure_counter: Counter[str] = Counter()
    for row in judge_rows:
        for code in row.get("fail_codes", []):
            failure_counter[str(code)] += 1
    run_meta = _read_optional_json(run_dir / "run_meta.json")
    adapter = str(run_meta.get("adapter", "manual"))
    retry_policy = str(run_meta.get("retry_policy", "retry.yaml"))
    avg_retries = (len(attempts) / generated_images) if generated_images else 0.0
    return {
        "run_id": run_dir.name,
        "gate": gate_mode,
        "adapter": adapter,
        "generated_images": generated_images,
        "gate_pass": gate_pass,
        "render_attempts": render_attempts,
        "usable_clips": usable_clips,
        "conversion_rate": conversion_rate,
        "retry_policy": retry_policy,
        "attempts": len(attempts),
        "avg_retries": avg_retries,
        "failure_codes": ", ".join(
            f"{code}:{count}" for code, count in sorted(failure_counter.items())
        ),
    }


def aggregate_run(run_dir: Path, report_path: Path) -> Path:
    """Write image, gate, render, usable, and conversion metrics."""
    metrics = run_metrics(run_dir)

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        "\n".join(
            [
                "# Run Summary",
                "",
                "Conversion denominator: generated image count, not render attempts.",
                "",
                "| run_id | gate | generated_images | gate_pass | "
                "render_attempts | usable_clips | conversion_rate |",
                "|---|---|---:|---:|---:|---:|---:|",
                f"| {metrics['run_id']} | {metrics['gate']} | "
                f"{metrics['generated_images']} | {metrics['gate_pass']} | "
                f"{metrics['render_attempts']} | {metrics['usable_clips']} | "
                f"{metrics['conversion_rate']} |",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return report_path


def aggregate_benchmark(run_dirs: list[Path], report_path: Path) -> Path:
    """Write a benchmark report comparing multiple run directories."""
    rows = [run_metrics(run_dir) for run_dir in run_dirs]
    lines = [
        "# Benchmark",
        "",
        "Conversion denominator: generated image count.",
        "",
        "| run_id | gate | adapter | generated_images | gate_pass | render_attempts | "
        "usable_clips | conversion_rate | retry_policy | attempts | avg_retries | "
        "failure_codes |",
        "|---|---|---|---:|---:|---:|---:|---:|---|---:|---:|---|",
    ]
    for row in rows:
        lines.append(
            f"| {row['run_id']} | {row['gate']} | {row['adapter']} | "
            f"{row['generated_images']} | {row['gate_pass']} | {row['render_attempts']} | "
            f"{row['usable_clips']} | {row['conversion_rate']} | {row['retry_policy']} | "
            f"{row['attempts']} | {float(row['avg_retries']):.2f} | "
            f"{row['failure_codes']} |"
        )
    lines.append("")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines), encoding="utf-8")
    return report_path
