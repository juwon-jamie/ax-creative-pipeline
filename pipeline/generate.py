"""Create image requests and validate externally generated image manifests."""

from __future__ import annotations

from pathlib import Path

from adapters.image_model import ImageModel
from pipeline.common import read_json, require_list, safe_relative_path, write_json


def _load_plan_scenes(plan_path: Path) -> list[dict[str, object]]:
    plan = read_json(plan_path)
    scenes = require_list(plan.get("scenes"), "plan.scenes")
    return [scene for scene in scenes if isinstance(scene, dict)]


def request_images(
    plan_path: Path,
    output_dir: Path,
    candidates_per_scene: int = 1,
) -> list[Path]:
    """Write one or more image request JSON files per scene."""
    if candidates_per_scene < 1:
        raise ValueError("candidates_per_scene must be at least 1")
    output_dir.mkdir(parents=True, exist_ok=True)

    request_paths: list[Path] = []
    for scene in _load_plan_scenes(plan_path):
        scene_id = str(scene["scene_id"])
        for candidate_index in range(1, candidates_per_scene + 1):
            candidate_id = f"{scene_id}-{candidate_index:02d}"
            request = {
                "request_type": "image",
                "scene_id": scene_id,
                "candidate_id": candidate_id,
                "prompt": scene["image_prompt"],
                "prompt_hash": scene["image_prompt_hash"],
                "reference_images": [],
                "aspect_ratio": scene["aspect_ratio"],
                "resolution": scene["resolution"],
                "status": "pending_external_generation",
            }
            request_path = output_dir / f"{candidate_id}.json"
            request_paths.append(write_json(request_path, request))
    return request_paths


def validate_image_manifest(plan_path: Path, images_dir: Path) -> Path:
    """Validate runs/<id>/images/manifest.json against the plan."""
    manifest_path = images_dir / "manifest.json"
    manifest = read_json(manifest_path)
    entries = manifest.get("images", manifest)
    entries = require_list(entries, "images manifest")
    scenes = {str(scene["scene_id"]): scene for scene in _load_plan_scenes(plan_path)}

    for index, entry in enumerate(entries, 1):
        if not isinstance(entry, dict):
            raise ValueError(f"image manifest entry {index} must be a mapping")
        scene_id = str(entry.get("scene_id", "")).strip()
        file_value = str(entry.get("file", "")).strip()
        prompt_hash = str(entry.get("prompt_hash", "")).strip()
        if not scene_id or scene_id not in scenes:
            raise ValueError(f"image manifest entry {index} has unknown scene_id")
        if not file_value:
            raise ValueError(f"image manifest entry {index} missing file")
        safe_relative_path(file_value, "image file")
        if prompt_hash != scenes[scene_id].get("image_prompt_hash"):
            raise ValueError(
                f"image manifest entry {index} prompt_hash mismatch"
            )
    return manifest_path


def generate_images(
    plan_path: Path,
    image_model: ImageModel,
    output_dir: Path,
) -> list[Path]:
    """Generate image candidates and return their paths."""
    output_dir.mkdir(parents=True, exist_ok=True)
    generated: list[Path] = []
    for scene in _load_plan_scenes(plan_path):
        paths = image_model.generate(
            str(scene["image_prompt"]),
            reference_images=[],
            output_dir=output_dir,
        )
        generated.extend(paths)
    return generated
