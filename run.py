"""Command line entry point for the clean-room creative pipeline."""

from __future__ import annotations

import argparse
from pathlib import Path

from pipeline.aggregate import aggregate_run
from pipeline.gate import gate_images
from pipeline.generate import request_images, validate_image_manifest
from pipeline.judge import write_judgments
from pipeline.plan import build_plan
from pipeline.render import request_videos, validate_clip_manifest


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(description="Run one clean-room pipeline stage.")
    parser.add_argument("--brand", default="brand/brand_zero.yaml")
    parser.add_argument("--brief", default="briefs/campaign_01.yaml")
    parser.add_argument("--run-id", required=True)
    parser.add_argument(
        "--stage",
        required=True,
        choices=["plan", "generate", "gate", "render", "judge", "aggregate"],
    )
    parser.add_argument("--mode", choices=["request", "ingest"], default="request")
    parser.add_argument("--no-gate", action="store_true")
    parser.add_argument("--candidates-per-scene", type=int, default=1)
    return parser.parse_args()


def main() -> int:
    """Run the selected stage."""
    args = parse_args()
    run_dir = Path("runs") / args.run_id
    plan_path = run_dir / "plan.json"

    if args.stage == "plan":
        build_plan(Path(args.brand), Path(args.brief), plan_path)
        print(plan_path.as_posix())
        return 0

    if args.stage == "generate":
        if args.mode == "request":
            paths = request_images(
                plan_path,
                run_dir / "requests" / "images",
                candidates_per_scene=args.candidates_per_scene,
            )
            print(f"wrote {len(paths)} image request(s)")
        else:
            path = validate_image_manifest(plan_path, run_dir / "images")
            print(path.as_posix())
        return 0

    if args.stage == "gate":
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
            paths = request_videos(
                plan_path=plan_path,
                gate_path=run_dir / "gate.jsonl",
                output_dir=run_dir / "requests" / "videos",
            )
            print(f"wrote {len(paths)} video request(s)")
        else:
            path = validate_clip_manifest(run_dir / "gate.jsonl", run_dir / "clips")
            print(path.as_posix())
        return 0

    if args.stage == "judge":
        path = write_judgments(
            run_dir / "judgments" / "usability.csv",
            Path("criteria/usability_v1.md"),
            run_dir / "judge.jsonl",
            clips_manifest_path=run_dir / "clips" / "manifest.json",
        )
        print(path.as_posix())
        return 0

    if args.stage == "aggregate":
        path = aggregate_run(run_dir, Path("reports") / "summary.md")
        print(path.as_posix())
        return 0

    raise AssertionError(f"unknown stage: {args.stage}")


if __name__ == "__main__":
    raise SystemExit(main())
