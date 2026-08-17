"""Command line entry point for the clean-room creative pipeline."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from adapters.factory import build_image_model, build_video_model
from agent.orchestrator import AgentConfig, run_agent
from pipeline.aggregate import aggregate_benchmark, aggregate_run
from pipeline.common import read_jsonl
from pipeline.evaluate import evaluate_run
from pipeline.gate import gate_images
from pipeline.generate import generate_images, request_images, validate_image_manifest
from pipeline.judge import write_judgments
from pipeline.plan import build_plan
from pipeline.render import render_clips, request_videos, validate_clip_manifest
from pipeline.retry import failures_from_judgments, record_retry_attempts


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(description="Run one clean-room pipeline stage.")
    parser.add_argument("--brand", default="brand/brand_zero.yaml")
    parser.add_argument("--brief", default="briefs/campaign_01.yaml")
    parser.add_argument("--run-id", required=True)
    parser.add_argument(
        "--stage",
        required=True,
        choices=[
            "plan",
            "generate",
            "gate",
            "render",
            "judge",
            "evaluate",
            "aggregate",
            "agent",
        ],
    )
    parser.add_argument(
        "--mode",
        choices=["request", "ingest", "direct"],
        default="request",
    )
    parser.add_argument("--no-gate", action="store_true")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--policy", default="policies/retry.yaml")
    parser.add_argument("--compare-runs", default="")
    parser.add_argument("--candidates-per-scene", type=int, default=1)
    parser.add_argument("--target-usable", type=int, default=3)
    parser.add_argument("--max-attempts", type=int, default=12)
    return parser.parse_args()


def _skip_if_resumed(path: Path, resume: bool) -> bool:
    if resume and path.exists():
        print(f"resume: using existing {path.as_posix()}")
        return True
    return False


def main() -> int:
    """Run the selected stage."""
    args = parse_args()
    run_dir = Path("runs") / args.run_id
    plan_path = run_dir / "plan.json"

    if args.stage == "plan":
        if _skip_if_resumed(plan_path, args.resume):
            return 0
        build_plan(Path(args.brand), Path(args.brief), plan_path)
        print(plan_path.as_posix())
        return 0

    if args.stage == "generate":
        if args.mode == "request":
            if _skip_if_resumed(run_dir / "requests" / "images", args.resume):
                return 0
            paths = request_images(
                plan_path,
                run_dir / "requests" / "images",
                candidates_per_scene=args.candidates_per_scene,
            )
            print(f"wrote {len(paths)} image request(s)")
        elif args.mode == "ingest":
            if _skip_if_resumed(run_dir / "images" / "manifest.json", args.resume):
                return 0
            path = validate_image_manifest(plan_path, run_dir / "images")
            print(path.as_posix())
        else:
            if _skip_if_resumed(run_dir / "images" / "manifest.json", args.resume):
                return 0
            paths = generate_images(plan_path, build_image_model(), run_dir / "images")
            print(f"generated {len(paths)} image file(s)")
        return 0

    if args.stage == "gate":
        if _skip_if_resumed(run_dir / "gate.jsonl", args.resume):
            return 0
        output = gate_images(
            plan_path,
            run_dir / "images",
            run_dir / "gate.jsonl",
            judgments_path=run_dir / "judgments" / "gate_manual.csv",
            no_gate=args.no_gate,
        )
        print(output)
        return 0

    if args.stage == "render":
        if args.mode == "request":
            if _skip_if_resumed(run_dir / "requests" / "videos", args.resume):
                return 0
            paths = request_videos(
                plan_path=plan_path,
                gate_path=run_dir / "gate.jsonl",
                output_dir=run_dir / "requests" / "videos",
            )
            print(f"wrote {len(paths)} video request(s)")
        elif args.mode == "ingest":
            if _skip_if_resumed(run_dir / "clips" / "manifest.json", args.resume):
                return 0
            path = validate_clip_manifest(run_dir / "gate.jsonl", run_dir / "clips")
            print(path.as_posix())
        else:
            if _skip_if_resumed(run_dir / "clips" / "manifest.json", args.resume):
                return 0
            paths = render_clips(
                run_dir / "gate.jsonl",
                build_video_model(),
                run_dir / "clips",
                plan_path=plan_path,
            )
            print(f"rendered {len(paths)} clip file(s)")
        return 0

    if args.stage == "judge":
        if _skip_if_resumed(run_dir / "judge.jsonl", args.resume):
            failures = failures_from_judgments(read_jsonl(run_dir / "judge.jsonl"))
            record_retry_attempts(run_dir, "judge", failures, Path(args.policy))
            return 0
        path = write_judgments(
            run_dir / "judgments" / "usability.csv",
            Path("criteria/usability_v1.md"),
            run_dir / "judge.jsonl",
            clips_manifest_path=run_dir / "clips" / "manifest.json",
        )
        if args.resume:
            failures = failures_from_judgments(read_jsonl(path))
            record_retry_attempts(run_dir, "judge", failures, Path(args.policy))
        print(path.as_posix())
        return 0

    if args.stage == "evaluate":
        if _skip_if_resumed(run_dir / "evaluate.jsonl", args.resume):
            failures = failures_from_judgments(read_jsonl(run_dir / "evaluate.jsonl"))
            record_retry_attempts(run_dir, "evaluate", failures, Path(args.policy))
            return 0
        path = evaluate_run(run_dir, run_dir / "evaluate.jsonl")
        if args.resume:
            failures = failures_from_judgments(read_jsonl(path))
            record_retry_attempts(run_dir, "evaluate", failures, Path(args.policy))
        print(path.as_posix())
        return 0

    if args.stage == "aggregate":
        if args.compare_runs:
            run_dirs = [
                Path("runs") / run_id.strip()
                for run_id in args.compare_runs.split(",")
                if run_id.strip()
            ]
            path = aggregate_benchmark(run_dirs, Path("reports") / "benchmark.md")
            print(path.as_posix())
            return 0
        path = aggregate_run(run_dir, Path("reports") / "summary.md")
        print(path.as_posix())
        return 0

    if args.stage == "agent":
        result = run_agent(
            AgentConfig(
                brand_path=Path(args.brand),
                brief_path=Path(args.brief),
                run_id=args.run_id,
                target_usable=args.target_usable,
                max_attempts=args.max_attempts,
                policy_path=Path(args.policy),
                candidates_per_scene=args.candidates_per_scene,
                no_gate=args.no_gate,
                resume=args.resume,
            )
        )
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0

    raise AssertionError(f"unknown stage: {args.stage}")


if __name__ == "__main__":
    raise SystemExit(main())
