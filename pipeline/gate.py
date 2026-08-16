"""Rule-based image gate for video readiness."""

from __future__ import annotations

REQUIRED_SCENE_FIELDS = {
    "subject",
    "motion",
    "camera",
    "start_state",
    "end_state",
}


def missing_scene_fields(scene: dict[str, object]) -> list[str]:
    """Return required scene fields that are missing or blank."""
    missing: list[str] = []
    for field in sorted(REQUIRED_SCENE_FIELDS):
        value = scene.get(field)
        if value is None or (isinstance(value, str) and not value.strip()):
            missing.append(field)
    return missing


def is_scene_video_ready(scene: dict[str, object]) -> bool:
    """Return True when the scene has enough structured motion data to render."""
    return not missing_scene_fields(scene)


def gate_images(plan_path: str, images_dir: str, output_path: str) -> str:
    """Write gate decisions for generated images."""
    raise NotImplementedError("image gating is not implemented in the W1 skeleton")
