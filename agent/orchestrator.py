"""Agent loop over the file-based creative pipeline stages."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from pipeline.aggregate import aggregate_run, run_metrics
from pipeline.common import read_jsonl, write_json, write_jsonl
from pipeline.evaluate import evaluate_run
from pipeline.gate import gate_images
from pipeline.generate import request_images, validate_image_manifest
from pipeline.judge import write_judgments
from pipeline.plan import build_plan
from pipeline.render import request_videos, validate_clip_manifest
from pipeline.retry import failures_from_judgments, record_retry_attempts


@dataclass(frozen=True)
class AgentConfig:
    """Runtime configuration for one agent run."""

    brand_path: Path
    brief_path: Path
    run_id: str
    target_usable: int = 3
    max_attempts: int = 12
    run_root: Path = Path("runs")
    report_dir: Path = Path("reports")
    policy_path: Path = Path("policies/retry.yaml")
    candidates_per_scene: int = 1
    no_gate: bool = False
    resume: bool = False


class Memory:
    """Append-only memory backed by runs/<id>/memory.jsonl."""

    def __init__(self, run_dir: Path) -> None:
        self.path = run_dir / "memory.jsonl"

    def rows(self) -> list[dict[str, object]]:
        """Return prior memory events."""
        return read_jsonl(self.path)

    def record(self, event: str, **fields: object) -> None:
        """Append one memory event."""
        rows = self.rows()
        rows.append({"event": event, **fields})
        write_jsonl(self.path, rows)


class Planner:
    """Create or reuse the structured scene plan."""

    def __init__(self, config: AgentConfig, memory: Memory) -> None:
        self.config = config
        self.memory = memory

    def ensure_plan(self, run_dir: Path) -> Path:
        """Write plan.json unless resume allows reusing it."""
        plan_path = run_dir / "plan.json"
        if self.config.resume and plan_path.exists():
            self.memory.record("plan_reused", path=plan_path.as_posix())
            return plan_path
        build_plan(self.config.brand_path, self.config.brief_path, plan_path)
        self.memory.record("plan_written", path=plan_path.as_posix())
        return plan_path


class Tools:
    """Tool-use boundary around the pipeline stage functions."""

    def __init__(self, config: AgentConfig, run_dir: Path, memory: Memory) -> None:
        self.config = config
        self.run_dir = run_dir
        self.memory = memory

    def request_or_ingest_images(self, plan_path: Path) -> bool:
        """Ensure image requests exist and validate a manifest when present."""
        requests_dir = self.run_dir / "requests" / "images"
        if not (self.config.resume and requests_dir.exists()):
            paths = request_images(
                plan_path,
                requests_dir,
                candidates_per_scene=self.config.candidates_per_scene,
            )
            self.memory.record("image_requests_written", count=len(paths))

        manifest_path = self.run_dir / "images" / "manifest.json"
        if not manifest_path.exists():
            self.memory.record("waiting_for_images", path=manifest_path.as_posix())
            return False
        validate_image_manifest(plan_path, self.run_dir / "images")
        self.memory.record("images_ingested", path=manifest_path.as_posix())
        return True

    def gate_images(self, plan_path: Path) -> Path:
        """Run the image readiness gate."""
        output_path = self.run_dir / "gate.jsonl"
        if self.config.resume and output_path.exists():
            self.memory.record("gate_reused", path=output_path.as_posix())
            return output_path
        gate_images(
            plan_path,
            self.run_dir / "images",
            output_path,
            judgments_path=self.run_dir / "judgments" / "gate_manual.csv",
            no_gate=self.config.no_gate,
        )
        self.memory.record("gate_written", path=output_path.as_posix())
        return output_path

    def request_or_ingest_videos(self, plan_path: Path, gate_path: Path) -> bool:
        """Ensure render requests exist and validate a clip manifest when present."""
        requests_dir = self.run_dir / "requests" / "videos"
        if not (self.config.resume and requests_dir.exists()):
            paths = request_videos(
                gate_path=gate_path,
                plan_path=plan_path,
                output_dir=requests_dir,
            )
            self.memory.record("video_requests_written", count=len(paths))

        manifest_path = self.run_dir / "clips" / "manifest.json"
        if not manifest_path.exists():
            self.memory.record("waiting_for_clips", path=manifest_path.as_posix())
            return False
        validate_clip_manifest(gate_path, self.run_dir / "clips")
        self.memory.record("clips_ingested", path=manifest_path.as_posix())
        return True

    def judge_and_evaluate(self) -> Path:
        """Write manual judgments, combined evaluation, and retry attempts."""
        judge_path = self.run_dir / "judge.jsonl"
        human_csv = self.run_dir / "judgments" / "usability.csv"
        if self.config.resume and judge_path.exists():
            self.memory.record("judge_reused", path=judge_path.as_posix())
        elif human_csv.exists():
            write_judgments(
                human_csv,
                Path("criteria/usability_v1.md"),
                judge_path,
                clips_manifest_path=self.run_dir / "clips" / "manifest.json",
            )
            self.memory.record("judge_written", path=judge_path.as_posix())
        else:
            self.memory.record("judge_skipped_no_human_csv", path=human_csv.as_posix())

        evaluate_path = self.run_dir / "evaluate.jsonl"
        if self.config.resume and evaluate_path.exists():
            self.memory.record("evaluate_reused", path=evaluate_path.as_posix())
        else:
            evaluate_run(self.run_dir, evaluate_path)
            self.memory.record("evaluate_written", path=evaluate_path.as_posix())

        failures = failures_from_judgments(read_jsonl(evaluate_path))
        attempts_path = record_retry_attempts(
            self.run_dir,
            "agent",
            failures,
            self.config.policy_path,
        )
        self.memory.record(
            "retry_policy_applied",
            failure_count=len(failures),
            path=attempts_path.as_posix(),
        )
        return evaluate_path

    def aggregate(self) -> Path:
        """Write the current run summary."""
        report_path = self.config.report_dir / "summary.md"
        aggregate_run(self.run_dir, report_path)
        self.memory.record("aggregate_written", path=report_path.as_posix())
        return report_path

    def write_meta(self, status: str, attempt_no: int) -> None:
        """Persist agent metadata for benchmark and review."""
        write_json(
            self.run_dir / "run_meta.json",
            {
                "adapter": "agent",
                "agent_status": status,
                "attempt_no": attempt_no,
                "max_attempts": self.config.max_attempts,
                "retry_policy": self.config.policy_path.name,
                "target_usable": self.config.target_usable,
            },
        )


class Evaluator:
    """Read run outputs and decide whether the loop is complete."""

    def __init__(self, run_dir: Path, target_usable: int) -> None:
        self.run_dir = run_dir
        self.target_usable = target_usable

    def usable_count(self) -> int:
        """Return the current usable clip count."""
        rows = read_jsonl(self.run_dir / "evaluate.jsonl")
        if not rows:
            rows = read_jsonl(self.run_dir / "judge.jsonl")
        return sum(1 for row in rows if row.get("usable"))

    def target_met(self) -> bool:
        """Return True when the run has enough usable clips."""
        return self.usable_count() >= self.target_usable

    def metrics(self) -> dict[str, object]:
        """Return aggregate metrics when the run is ready for aggregation."""
        return run_metrics(self.run_dir)


class Loop:
    """Planning, memory, tools, and evaluation loop."""

    def __init__(self, config: AgentConfig) -> None:
        self.config = config
        self.run_dir = config.run_root / config.run_id
        self.memory = Memory(self.run_dir)
        self.planner = Planner(config, self.memory)
        self.tools = Tools(config, self.run_dir, self.memory)
        self.evaluator = Evaluator(self.run_dir, config.target_usable)

    def run(self) -> dict[str, object]:
        """Run until target, external wait, or attempt budget exhaustion."""
        if self.config.max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")
        if self.config.target_usable < 0:
            raise ValueError("target_usable must be non-negative")

        status = "max_attempts_reached"
        final_attempt = 0
        self.memory.record(
            "agent_started",
            max_attempts=self.config.max_attempts,
            target_usable=self.config.target_usable,
        )

        for attempt_no in range(1, self.config.max_attempts + 1):
            final_attempt = attempt_no
            self.memory.record("attempt_started", attempt_no=attempt_no)
            plan_path = self.planner.ensure_plan(self.run_dir)
            if not self.tools.request_or_ingest_images(plan_path):
                status = "waiting_for_images"
                break
            gate_path = self.tools.gate_images(plan_path)
            if not self.tools.request_or_ingest_videos(plan_path, gate_path):
                status = "waiting_for_clips"
                break
            self.tools.judge_and_evaluate()
            self.tools.aggregate()
            usable = self.evaluator.usable_count()
            target_met = usable >= self.config.target_usable
            self.memory.record(
                "attempt_completed",
                attempt_no=attempt_no,
                target_met=target_met,
                usable_clips=usable,
            )
            if target_met:
                status = "target_met"
                break
            if self.config.resume:
                status = "target_not_met_resume_reused_outputs"
                break

        self.tools.write_meta(status, final_attempt)
        self.memory.record("agent_finished", attempt_no=final_attempt, status=status)
        result = {
            "attempts": final_attempt,
            "run_id": self.config.run_id,
            "status": status,
            "target_usable": self.config.target_usable,
            "usable_clips": self.evaluator.usable_count()
            if (self.run_dir / "evaluate.jsonl").exists()
            else 0,
        }
        return result


def run_agent(config: AgentConfig) -> dict[str, object]:
    """Run the agent loop."""
    return Loop(config).run()
