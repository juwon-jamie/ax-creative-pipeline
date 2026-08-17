"""Aggregate run metrics into a summary report."""

from __future__ import annotations

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


def aggregate_run(run_dir: Path, report_path: Path) -> Path:
    """Write image, gate, render, usable, and conversion metrics."""
    run_id = run_dir.name
    gate_rows = read_jsonl(run_dir / "gate.jsonl")
    judge_rows = read_jsonl(run_dir / "judge.jsonl")
    generated_images = _count_images(run_dir)
    gate_pass = sum(1 for row in gate_rows if row.get("video_ready"))
    render_attempts = _count_video_requests(run_dir)
    usable_clips = sum(1 for row in judge_rows if row.get("usable"))
    gate_mode = "off" if any(row.get("no_gate") for row in gate_rows) else "on"
    conversion_rate = _format_rate(usable_clips, generated_images)

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
                f"| {run_id} | {gate_mode} | {generated_images} | {gate_pass} | "
                f"{render_attempts} | {usable_clips} | {conversion_rate} |",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return report_path
