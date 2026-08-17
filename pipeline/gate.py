"""Rule-based image gate for video readiness."""

from __future__ import annotations

import csv
from pathlib import Path

from pipeline.common import read_json, safe_relative_path, write_jsonl

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


def _parse_yes_no(value: str) -> bool:
    normalized = value.strip().casefold()
    if normalized in {"y", "yes", "true", "1", "pass", "usable"}:
        return True
    if normalized in {"n", "no", "false", "0", "fail", "not_usable"}:
        return False
    raise ValueError(f"cannot parse boolean value: {value}")


def _image_id(entry: dict[str, object]) -> str:
    explicit = str(entry.get("image_id", "")).strip()
    if explicit:
        return explicit
    scene_id = str(entry.get("scene_id", "")).strip()
    file_stem = Path(str(entry.get("file", ""))).stem
    return f"{scene_id}-{file_stem}"


def _load_manual_judgments(path: Path | None) -> dict[str, dict[str, object]]:
    if path is None or not path.exists():
        return {}
    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = csv.DictReader(handle)
        judgments: dict[str, dict[str, object]] = {}
        for row_number, row in enumerate(rows, 2):
            image_id = str(row.get("image_id", "")).strip()
            if not image_id:
                raise ValueError(f"{path}:{row_number} missing image_id")
            judgments[image_id] = {
                "video_ready": _parse_yes_no(str(row.get("video_ready", ""))),
                "reason": str(row.get("reason", "")).strip(),
            }
        return judgments


def _load_manifest(images_dir: Path) -> list[dict[str, object]]:
    manifest = read_json(images_dir / "manifest.json")
    entries = manifest.get("images", manifest)
    if not isinstance(entries, list):
        raise ValueError("images manifest must be a list or contain images list")
    return [entry for entry in entries if isinstance(entry, dict)]


def gate_images(
    plan_path: str | Path,
    images_dir: str | Path,
    output_path: str | Path,
    judgments_path: str | Path | None = None,
    no_gate: bool = False,
) -> str:
    """Write gate decisions for generated images."""
    plan = read_json(Path(plan_path))
    scenes = {
        str(scene["scene_id"]): scene
        for scene in plan.get("scenes", [])
        if isinstance(scene, dict)
    }
    manual = _load_manual_judgments(Path(judgments_path) if judgments_path else None)
    rows: list[dict[str, object]] = []

    for entry in _load_manifest(Path(images_dir)):
        scene_id = str(entry.get("scene_id", "")).strip()
        file_value = str(entry.get("file", "")).strip()
        prompt_hash = str(entry.get("prompt_hash", "")).strip()
        image_id = _image_id(entry)
        safe_relative_path(file_value, "image file")

        scene = scenes.get(scene_id)
        rule_failures: list[str] = []
        if scene is None:
            rule_failures.append("unknown_scene")
            rule_ready = False
        else:
            missing = missing_scene_fields(scene)
            rule_failures.extend(f"missing_{field}" for field in missing)
            if prompt_hash != scene.get("image_prompt_hash"):
                rule_failures.append("prompt_hash_mismatch")
            if scene.get("forbidden_hits"):
                rule_failures.append("forbidden_terms")
            rule_ready = not rule_failures

        manual_row = manual.get(image_id)
        manual_ready = None if manual_row is None else bool(manual_row["video_ready"])
        manual_reason = "" if manual_row is None else str(manual_row["reason"])
        if not no_gate and manual_row is None:
            rule_failures.append("manual_judgment_missing")

        video_ready = True if no_gate else bool(rule_ready and manual_ready)
        reasons = list(rule_failures)
        if manual_reason:
            reasons.append(manual_reason)
        if no_gate:
            reasons.append("gate disabled by --no-gate")

        rows.append(
            {
                "image_id": image_id,
                "scene_id": scene_id,
                "file": file_value,
                "prompt_hash": prompt_hash,
                "rule_ready": rule_ready,
                "manual_ready": manual_ready,
                "video_ready": video_ready,
                "no_gate": no_gate,
                "reason": "; ".join(reasons),
            }
        )

    return str(write_jsonl(Path(output_path), rows))
