"""Generate deterministic no-media benchmark runs."""

from __future__ import annotations

import json
import shutil
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from pipeline.aggregate import run_metrics
from pipeline.common import stable_hash, write_json, write_jsonl
from pipeline.evaluate import evaluate_run
from pipeline.judge import write_judgments


@dataclass(frozen=True)
class BenchmarkScene:
    """One synthetic benchmark scene."""

    scene_id: str
    failure_code: str | None = None
    gate_ready: bool = True
    retry_fixes: bool = False


@dataclass(frozen=True)
class BenchmarkScenario:
    """Synthetic brief used by the benchmark matrix."""

    name: str
    difficulty: str
    scenes: tuple[BenchmarkScene, ...]


SCENARIOS = (
    BenchmarkScenario(
        name="easy",
        difficulty="simple texture and turn",
        scenes=(
            BenchmarkScene("texture_drop"),
            BenchmarkScene("bottle_turn"),
            BenchmarkScene("skin_light", failure_code="F5", retry_fixes=True),
        ),
    ),
    BenchmarkScenario(
        name="normal",
        difficulty="mixed motion and spec pressure",
        scenes=(
            BenchmarkScene("texture_drop"),
            BenchmarkScene("bottle_turn", failure_code="F4", retry_fixes=True),
            BenchmarkScene("skin_light", failure_code="F5"),
        ),
    ),
    BenchmarkScenario(
        name="hard",
        difficulty="logo-like mark trap and unstable physics",
        scenes=(
            BenchmarkScene("texture_drop", failure_code="F6", gate_ready=False),
            BenchmarkScene("bottle_turn", failure_code="F4", retry_fixes=True),
            BenchmarkScene("skin_light", failure_code="F1"),
        ),
    ),
)

POLICIES = ("no_gate", "gate", "gate_retry")


def _clean_run_dir(run_dir: Path) -> None:
    if run_dir.exists():
        if not run_dir.name.startswith("bench_"):
            raise ValueError(f"refusing to clean non-benchmark run: {run_dir}")
        shutil.rmtree(run_dir)
    run_dir.mkdir(parents=True)


def _write_plan(run_dir: Path, scenario: BenchmarkScenario) -> None:
    scenes: list[dict[str, object]] = []
    for scene in scenario.scenes:
        prompt = f"Benchmark {scenario.name} single frame for {scene.scene_id}"
        scenes.append(
            {
                "aspect_ratio": "9:16",
                "camera": "macro",
                "duration_seconds": 5,
                "end_state": "clear end state",
                "image_prompt": prompt,
                "image_prompt_hash": stable_hash(prompt),
                "motion": "visible but controlled motion",
                "motion_prompt": f"Move {scene.scene_id} for five seconds.",
                "resolution": "1080x1920",
                "scene_id": scene.scene_id,
                "start_state": "clear start state",
                "subject": "unbranded product texture",
            }
        )
    write_json(
        run_dir / "plan.json",
        {
            "brand_id": "brand_zero",
            "brief_id": f"bench_{scenario.name}",
            "objective": scenario.difficulty,
            "scene_count": len(scenes),
            "scenes": scenes,
        },
    )


def _write_images(run_dir: Path, scenario: BenchmarkScenario) -> None:
    images = []
    for scene in scenario.scenes:
        prompt = f"Benchmark {scenario.name} single frame for {scene.scene_id}"
        image_id = f"img_{scene.scene_id}"
        images.append(
            {
                "file": f"{image_id}.png",
                "image_id": image_id,
                "prompt_hash": stable_hash(prompt),
                "scene_id": scene.scene_id,
            }
        )
    write_json(run_dir / "images" / "manifest.json", {"images": images})


def _gate_ready(scene: BenchmarkScene, policy: str) -> bool:
    if policy == "no_gate":
        return True
    return scene.gate_ready


def _write_gate(run_dir: Path, scenario: BenchmarkScenario, policy: str) -> None:
    rows = []
    for scene in scenario.scenes:
        video_ready = _gate_ready(scene, policy)
        rows.append(
            {
                "file": f"img_{scene.scene_id}.png",
                "image_id": f"img_{scene.scene_id}",
                "manual_ready": video_ready,
                "no_gate": policy == "no_gate",
                "prompt_hash": stable_hash(
                    f"Benchmark {scenario.name} single frame for {scene.scene_id}"
                ),
                "reason": "" if video_ready else "logo-like mark risk caught by gate",
                "rule_ready": True,
                "scene_id": scene.scene_id,
                "video_ready": video_ready,
            }
        )
    write_jsonl(run_dir / "gate.jsonl", rows)


def _write_clips(run_dir: Path, scenario: BenchmarkScenario, policy: str) -> list[str]:
    clips = []
    for scene in scenario.scenes:
        if not _gate_ready(scene, policy):
            continue
        clip_id = f"clip_{scene.scene_id}"
        clips.append(
            {
                "aspect_ratio": "9:16",
                "clip_id": clip_id,
                "duration_seconds": 5,
                "file": f"{clip_id}.mp4",
                "image_id": f"img_{scene.scene_id}",
                "resolution": "1080x1920",
                "scene_id": scene.scene_id,
            }
        )
        write_json(
            run_dir / "requests" / "videos" / f"img_{scene.scene_id}.json",
            {"request_type": "video", "scene_id": scene.scene_id},
        )
    write_json(run_dir / "clips" / "manifest.json", {"clips": clips})
    return [str(clip["clip_id"]) for clip in clips]


def _scene_by_clip(scenario: BenchmarkScenario) -> dict[str, BenchmarkScene]:
    return {f"clip_{scene.scene_id}": scene for scene in scenario.scenes}


def _is_usable(scene: BenchmarkScene, policy: str) -> bool:
    if scene.failure_code is None:
        return True
    return policy == "gate_retry" and scene.retry_fixes


def _write_judgments(
    run_dir: Path,
    scenario: BenchmarkScenario,
    policy: str,
    clip_ids: list[str],
) -> None:
    scenes = _scene_by_clip(scenario)
    lines = ["clip_id,verdict,fail_codes,pass_fail_codes,p7_reason"]
    for clip_id in clip_ids:
        scene = scenes[clip_id]
        if _is_usable(scene, policy):
            lines.append(f"{clip_id},USABLE,,,")
        else:
            lines.append(
                f"{clip_id},NOT_USABLE,{scene.failure_code},,"
                f"seeded {scene.failure_code} benchmark failure"
            )
    path = run_dir / "judgments" / "usability.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    write_judgments(
        path,
        Path("criteria/usability_v1.md"),
        run_dir / "judge.jsonl",
        clips_manifest_path=run_dir / "clips" / "manifest.json",
    )
    evaluate_run(
        run_dir,
        run_dir / "evaluate.jsonl",
        agreement_path=run_dir / "agreement.md",
    )


def _write_attempts(run_dir: Path, scenario: BenchmarkScenario, policy: str) -> None:
    attempts = []
    if policy == "gate_retry":
        for attempt_no, scene in enumerate(scenario.scenes, 1):
            if scene.failure_code and scene.retry_fixes:
                attempts.append(
                    {
                        "action": "seeded_retry",
                        "asset_id": f"clip_{scene.scene_id}",
                        "attempt_no": attempt_no,
                        "code": scene.failure_code,
                        "max_retries": 1,
                        "prompt_adjustment": f"seeded fix for {scene.failure_code}",
                        "stage": "agent",
                        "status": "resolved",
                    }
                )
    write_jsonl(run_dir / "attempts.jsonl", attempts)


def _estimated_cost(metrics: dict[str, object]) -> float:
    return (
        int(metrics["generated_images"]) * 0.10
        + int(metrics["render_attempts"]) * 0.25
        + int(metrics["attempts"]) * 0.05
    )


def _failure_distribution(run_dir: Path) -> str:
    counter: Counter[str] = Counter()
    for row in (run_dir / "judge.jsonl").read_text(encoding="utf-8").splitlines():
        if not row.strip():
            continue
        for code in json.loads(row).get("fail_codes", []):
            counter[str(code)] += 1
    if not counter:
        return ""
    return ", ".join(f"{code}:{count}" for code, count in sorted(counter.items()))


def create_benchmark_run(
    scenario: BenchmarkScenario,
    policy: str,
    run_root: Path = Path("runs"),
) -> Path:
    """Create one deterministic no-media benchmark run."""
    if policy not in POLICIES:
        raise ValueError(f"unknown benchmark policy: {policy}")
    run_dir = run_root / f"bench_{scenario.name}_{policy}"
    _clean_run_dir(run_dir)
    _write_plan(run_dir, scenario)
    _write_images(run_dir, scenario)
    _write_gate(run_dir, scenario, policy)
    clip_ids = _write_clips(run_dir, scenario, policy)
    _write_judgments(run_dir, scenario, policy, clip_ids)
    _write_attempts(run_dir, scenario, policy)
    write_json(
        run_dir / "run_meta.json",
        {
            "adapter": "seeded",
            "benchmark_brief": scenario.name,
            "retry_policy": policy,
        },
    )
    return run_dir


def write_agent_benchmark_report(run_dirs: list[Path], report_path: Path) -> Path:
    """Write the agent benchmark markdown report."""
    lines = [
        "# Agent Benchmark",
        "",
        "No-media seeded benchmark: three briefs crossed with no-gate, gate, and "
        "gate+retry policies.",
        "",
        "| run_id | brief | policy | generated_images | gate_pass | render_attempts | "
        "usable_clips | conversion_rate | attempts | avg_retries | cost_units | "
        "failure_codes |",
        "|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for run_dir in run_dirs:
        metrics = run_metrics(run_dir)
        brief = run_dir.name.split("_")[1]
        policy = "_".join(run_dir.name.split("_")[2:])
        lines.append(
            f"| {metrics['run_id']} | {brief} | {policy} | "
            f"{metrics['generated_images']} | {metrics['gate_pass']} | "
            f"{metrics['render_attempts']} | {metrics['usable_clips']} | "
            f"{metrics['conversion_rate']} | {metrics['attempts']} | "
            f"{float(metrics['avg_retries']):.2f} | {_estimated_cost(metrics):.2f} | "
            f"{_failure_distribution(run_dir)} |"
        )
    lines.append("")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines), encoding="utf-8")
    return report_path


def run_benchmark(
    run_root: Path = Path("runs"),
    report_path: Path = Path("reports") / "agent_benchmark.md",
) -> Path:
    """Create the full benchmark matrix and report."""
    run_dirs = [
        create_benchmark_run(scenario, policy, run_root)
        for scenario in SCENARIOS
        for policy in POLICIES
    ]
    return write_agent_benchmark_report(run_dirs, report_path)


def main() -> int:
    """CLI entry point for python -m bench.run."""
    path = run_benchmark()
    print(path.as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
