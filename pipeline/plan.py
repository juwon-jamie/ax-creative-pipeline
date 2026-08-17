"""Plan campaign briefs into structured scene cards."""

from __future__ import annotations

from pathlib import Path

from pipeline.common import load_yaml, stable_hash, write_json

REQUIRED_SCENE_FIELDS = (
    "id",
    "subject",
    "motion",
    "camera",
    "start_state",
    "end_state",
)


def _required_text(scene: dict[str, object], field: str) -> str:
    value = scene.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"scene {scene.get('id', '<unknown>')} missing {field}")
    return value.strip()


def _forbidden_terms(brand: dict[str, object]) -> list[str]:
    constraints = brand.get("constraints", {})
    if not isinstance(constraints, dict):
        return []
    terms: list[str] = []
    for key in ("forbidden_claims", "forbidden_visuals"):
        values = constraints.get(key, [])
        if isinstance(values, list):
            terms.extend(str(value) for value in values if str(value).strip())
    return terms


def _find_forbidden_terms(text: str, terms: list[str]) -> list[str]:
    normalized = text.casefold()
    return [term for term in terms if term.casefold() in normalized]


def build_plan(brand_path: Path, brief_path: Path, output_path: Path) -> Path:
    """Create a plan JSON file from brand and brief inputs."""
    brand_doc = load_yaml(brand_path)
    brief_doc = load_yaml(brief_path)
    brand = brand_doc.get("brand", {})
    brief = brief_doc.get("brief", brief_doc)
    if not isinstance(brand, dict) or not isinstance(brief, dict):
        raise ValueError("brand.yaml and brief.yaml must contain mappings")

    brand_id = str(brand.get("id", "")).strip()
    brief_brand_id = str(brief.get("brand_id", "")).strip()
    if brand_id and brief_brand_id and brand_id != brief_brand_id:
        raise ValueError(f"brief brand_id {brief_brand_id} does not match {brand_id}")

    scenes = brief.get("scenes", [])
    if not isinstance(scenes, list) or not scenes:
        raise ValueError("brief must contain at least one scene")

    forbidden = _forbidden_terms(brand_doc)
    deliverables = brand_doc.get("deliverables", {})
    if not isinstance(deliverables, dict):
        deliverables = {}

    scene_cards: list[dict[str, object]] = []
    for index, raw_scene in enumerate(scenes, 1):
        if not isinstance(raw_scene, dict):
            raise ValueError(f"scene {index} must be a mapping")
        scene = {
            field: _required_text(raw_scene, field)
            for field in REQUIRED_SCENE_FIELDS
        }
        combined_text = " ".join(scene.values())
        forbidden_hits = _find_forbidden_terms(combined_text, forbidden)
        if forbidden_hits:
            joined_hits = ", ".join(sorted(forbidden_hits))
            raise ValueError(
                f"scene {scene['id']} contains forbidden terms: {joined_hits}"
            )

        # Learning-loop fix (run demo01, 2026-08-17): putting "Start state ... End state ..."
        # into the *image* prompt made the image model render 3-panel storyboards, which
        # are not video-ready. The image prompt now describes ONE frame (the start state)
        # and says so explicitly; the end state lives only in the motion (video) prompt.
        image_prompt = (
            f"Fictional unbranded skincare ampoule scene. Subject: {scene['subject']}. "
            f"Camera: {scene['camera']}. Frame shows: {scene['start_state']}. "
            "Single continuous frame, one moment in time. No panels, no collage, "
            "no storyboard, no split screen. No real logo, no real package silhouette, "
            "no medical efficacy claim."
        )
        motion_prompt = (
            f"Create a {deliverables.get('duration_seconds', 5)} second vertical clip: "
            f"{scene['motion']}. Start with {scene['start_state']} and end with "
            f"{scene['end_state']}."
        )
        scene_cards.append(
            {
                "scene_id": scene["id"],
                "subject": scene["subject"],
                "motion": scene["motion"],
                "camera": scene["camera"],
                "start_state": scene["start_state"],
                "end_state": scene["end_state"],
                "aspect_ratio": deliverables.get("aspect_ratio", "9:16"),
                "duration_seconds": deliverables.get("duration_seconds", 5),
                "resolution": deliverables.get("resolution", "1080x1920"),
                "image_prompt": image_prompt,
                "image_prompt_hash": stable_hash(image_prompt),
                "motion_prompt": motion_prompt,
                "forbidden_hits": [],
            }
        )

    plan = {
        "brand_id": brand_id,
        "brand_name": brand.get("name", "Brand Zero"),
        "brief_id": brief.get("id", brief_path.stem),
        "objective": brief.get("objective", ""),
        "scene_count": len(scene_cards),
        "scenes": scene_cards,
        "source": {
            "brand": brand_path.as_posix(),
            "brief": brief_path.as_posix(),
        },
    }
    return write_json(output_path, plan)
