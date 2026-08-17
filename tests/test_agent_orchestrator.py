from pathlib import Path
from tempfile import TemporaryDirectory

from agent.orchestrator import AgentConfig, Memory, run_agent
from pipeline.common import read_jsonl, write_json


def _write_existing_run(run_dir: Path, usable: bool = True, fail_code: str = "F5") -> None:
    write_json(
        run_dir / "plan.json",
        {
            "scenes": [
                {
                    "aspect_ratio": "9:16",
                    "camera": "macro",
                    "duration_seconds": 5,
                    "end_state": "right",
                    "image_prompt": "single unbranded bottle frame",
                    "image_prompt_hash": "hash",
                    "motion": "slow turn",
                    "motion_prompt": "turn the bottle slowly",
                    "resolution": "1080x1920",
                    "scene_id": "scene_01",
                    "start_state": "left",
                    "subject": "unbranded bottle",
                }
            ]
        },
    )
    write_json(
        run_dir / "images" / "manifest.json",
        {
            "images": [
                {
                    "file": "img_scene_01.png",
                    "image_id": "img_scene_01",
                    "prompt_hash": "hash",
                    "scene_id": "scene_01",
                }
            ]
        },
    )
    (run_dir / "judgments").mkdir(parents=True, exist_ok=True)
    (run_dir / "judgments" / "gate_manual.csv").write_text(
        "image_id,video_ready,reason\nimg_scene_01,Y,ready\n",
        encoding="utf-8",
    )
    write_json(
        run_dir / "clips" / "manifest.json",
        {
            "clips": [
                {
                    "aspect_ratio": "9:16",
                    "clip_id": "clip_01",
                    "duration_seconds": 5,
                    "file": "clip_01.mp4",
                    "image_id": "img_scene_01",
                    "resolution": "1080x1920",
                }
            ]
        },
    )
    if usable:
        judgment = "clip_id,verdict,fail_codes,pass_fail_codes,p7_reason\nclip_01,USABLE,,,\n"
    else:
        judgment = (
            "clip_id,verdict,fail_codes,pass_fail_codes,p7_reason\n"
            f"clip_01,NOT_USABLE,{fail_code},,seeded failure\n"
        )
    (run_dir / "judgments" / "usability.csv").write_text(judgment, encoding="utf-8")


def _write_brand_and_brief(tmp_path: Path) -> tuple[Path, Path]:
    brand_path = tmp_path / "brand.yaml"
    brief_path = tmp_path / "brief.yaml"
    brand_path.write_text(
        """
brand:
  id: brand_zero
  name: Brand Zero
deliverables:
  aspect_ratio: "9:16"
  duration_seconds: 5
  resolution: "1080x1920"
""",
        encoding="utf-8",
    )
    brief_path.write_text(
        """
brief:
  id: campaign_01
  brand_id: brand_zero
  scenes:
    - id: scene_01
      subject: unbranded bottle
      motion: slow turn
      camera: macro
      start_state: left
      end_state: right
""",
        encoding="utf-8",
    )
    return brand_path, brief_path


def test_memory_appends_events():
    with TemporaryDirectory(dir=Path.cwd()) as raw_tmp:
        run_dir = Path(raw_tmp) / "run"
        memory = Memory(run_dir)

        memory.record("started", attempt_no=1)
        memory.record("finished", status="ok")

        assert [row["event"] for row in memory.rows()] == ["started", "finished"]


def test_agent_reuses_existing_outputs_and_reaches_target():
    with TemporaryDirectory(dir=Path.cwd()) as raw_tmp:
        tmp_path = Path(raw_tmp)
        run_root = tmp_path / "runs"
        run_dir = run_root / "demo"
        _write_existing_run(run_dir, usable=True)
        brand_path, brief_path = _write_brand_and_brief(tmp_path)

        result = run_agent(
            AgentConfig(
                brand_path=brand_path,
                brief_path=brief_path,
                run_id="demo",
                run_root=run_root,
                report_dir=tmp_path / "reports",
                target_usable=1,
                max_attempts=3,
                resume=True,
            )
        )

        assert result["status"] == "target_met"
        assert result["usable_clips"] == 1
        assert (run_dir / "memory.jsonl").exists()


def test_agent_waits_cleanly_when_images_are_external():
    with TemporaryDirectory(dir=Path.cwd()) as raw_tmp:
        tmp_path = Path(raw_tmp)
        brand_path, brief_path = _write_brand_and_brief(tmp_path)

        result = run_agent(
            AgentConfig(
                brand_path=brand_path,
                brief_path=brief_path,
                run_id="needs_images",
                run_root=tmp_path / "runs",
                report_dir=tmp_path / "reports",
                target_usable=1,
                max_attempts=2,
            )
        )

        run_dir = tmp_path / "runs" / "needs_images"
        assert result["status"] == "waiting_for_images"
        assert list((run_dir / "requests" / "images").glob("*.json"))
        assert read_jsonl(run_dir / "memory.jsonl")[-1]["status"] == "waiting_for_images"


def test_agent_records_retry_attempts_for_f_code_failures():
    with TemporaryDirectory(dir=Path.cwd()) as raw_tmp:
        tmp_path = Path(raw_tmp)
        run_root = tmp_path / "runs"
        run_dir = run_root / "retry"
        _write_existing_run(run_dir, usable=False, fail_code="F5")
        brand_path, brief_path = _write_brand_and_brief(tmp_path)

        result = run_agent(
            AgentConfig(
                brand_path=brand_path,
                brief_path=brief_path,
                run_id="retry",
                run_root=run_root,
                report_dir=tmp_path / "reports",
                target_usable=1,
                max_attempts=1,
                resume=True,
            )
        )

        attempts = read_jsonl(run_dir / "attempts.jsonl")
        assert result["status"] == "target_not_met_resume_reused_outputs"
        assert attempts[0]["code"] == "F5"


def test_agent_can_evaluate_without_human_csv():
    with TemporaryDirectory(dir=Path.cwd()) as raw_tmp:
        tmp_path = Path(raw_tmp)
        run_root = tmp_path / "runs"
        run_dir = run_root / "rules_only"
        _write_existing_run(run_dir, usable=True)
        (run_dir / "judgments" / "usability.csv").unlink()
        brand_path, brief_path = _write_brand_and_brief(tmp_path)

        result = run_agent(
            AgentConfig(
                brand_path=brand_path,
                brief_path=brief_path,
                run_id="rules_only",
                run_root=run_root,
                report_dir=tmp_path / "reports",
                target_usable=1,
                max_attempts=1,
                resume=True,
            )
        )

        memory_events = [row["event"] for row in read_jsonl(run_dir / "memory.jsonl")]
        assert result["status"] == "target_met"
        assert "judge_skipped_no_human_csv" in memory_events
