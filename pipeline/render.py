"""Create video requests and validate externally rendered clip manifests."""

from __future__ import annotations

from pathlib import Path

from adapters.video_model import VideoModel
from pipeline.common import (
    read_json,
    read_jsonl,
    safe_relative_path,
    stable_hash,
    write_json,
)


def _load_plan_motion_prompts(plan_path: Path) -> dict[str, dict[str, object]]:
    plan = read_json(plan_path)
    return {
        str(scene["scene_id"]): scene
        for scene in plan.get("scenes", [])
        if isinstance(scene, dict)
    }


def request_videos(gate_path: Path, plan_path: Path, output_dir: Path) -> list[Path]:
    """Write one video render request per gate-passing image."""
    scenes = _load_plan_motion_prompts(plan_path)
    output_dir.mkdir(parents=True, exist_ok=True)
    request_paths: list[Path] = []
    for row in read_jsonl(gate_path):
        if not row.get("video_ready"):
            continue
        scene_id = str(row["scene_id"])
        scene = scenes[scene_id]
        image_id = str(row["image_id"])
        motion_prompt = str(scene["motion_prompt"])
        request = {
            "request_type": "video",
            "image_id": image_id,
            "scene_id": scene_id,
            "source_image": row["file"],
            "motion_prompt": motion_prompt,
            "prompt_hash": stable_hash(f"{image_id}:{motion_prompt}"),
            "duration_seconds": scene["duration_seconds"],
            "aspect_ratio": scene["aspect_ratio"],
            "status": "pending_external_render",
        }
        request_paths.append(write_json(output_dir / f"{image_id}.json", request))
    return request_paths


def validate_clip_manifest(gate_path: Path, clips_dir: Path) -> Path:
    """Validate runs/<id>/clips/manifest.json against gate-passing images."""
    manifest_path = clips_dir / "manifest.json"
    manifest = read_json(manifest_path)
    entries = manifest.get("clips", manifest)
    if not isinstance(entries, list):
        raise ValueError("clip manifest must be a list or contain clips list")
    accepted_images = {
        str(row["image_id"]) for row in read_jsonl(gate_path) if row.get("video_ready")
    }
    for index, entry in enumerate(entries, 1):
        if not isinstance(entry, dict):
            raise ValueError(f"clip manifest entry {index} must be a mapping")
        image_id = str(entry.get("image_id", "")).strip()
        clip_id = str(entry.get("clip_id", "")).strip()
        file_value = str(entry.get("file", "")).strip()
        if not clip_id:
            raise ValueError(f"clip manifest entry {index} missing clip_id")
        if image_id not in accepted_images:
            raise ValueError(
                f"clip manifest entry {index} image_id was not gate-passed"
            )
        if not file_value:
            raise ValueError(f"clip manifest entry {index} missing file")
        safe_relative_path(file_value, "clip file")
    return manifest_path


def render_clips(
    gate_path: Path,
    video_model: VideoModel,
    output_dir: Path,
) -> list[Path]:
    """Render clips from accepted images and return clip paths."""
    output_dir.mkdir(parents=True, exist_ok=True)
    rendered: list[Path] = []
    for row in read_jsonl(gate_path):
        if not row.get("video_ready"):
            continue
        clip = video_model.render(
            image_path=Path(str(row["file"])),
            motion_prompt=str(row.get("motion_prompt", "")),
            output_dir=output_dir,
        )
        rendered.append(clip)
    return rendered
