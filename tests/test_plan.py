import json
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from pipeline.plan import build_plan

BRAND_YAML = """
brand:
  id: brand_zero
  name: Brand Zero
constraints:
  forbidden_claims:
    - medical efficacy
  forbidden_visuals:
    - real logo
deliverables:
  aspect_ratio: "9:16"
  duration_seconds: 5
  resolution: "1080x1920"
"""


def test_build_plan_writes_scene_cards():
    with TemporaryDirectory(dir=Path.cwd()) as raw_tmp:
        tmp_path = Path(raw_tmp)
        _assert_build_plan_writes_scene_cards(tmp_path)


def _assert_build_plan_writes_scene_cards(tmp_path):
    brand_path = tmp_path / "brand.yaml"
    brief_path = tmp_path / "brief.yaml"
    output_path = tmp_path / "plan.json"
    brand_path.write_text(BRAND_YAML, encoding="utf-8")
    brief_path.write_text(
        """
brief:
  id: campaign_01
  brand_id: brand_zero
  objective: show texture
  scenes:
    - id: texture_drop
      subject: ampoule drop
      motion: slow slide
      camera: macro
      start_state: suspended
      end_state: reflective film
""",
        encoding="utf-8",
    )

    build_plan(brand_path, brief_path, output_path)

    plan = json.loads(output_path.read_text(encoding="utf-8"))
    assert plan["scene_count"] == 1
    scene = plan["scenes"][0]
    assert scene["scene_id"] == "texture_drop"
    assert scene["image_prompt_hash"]
    assert scene["forbidden_hits"] == []


def test_build_plan_rejects_forbidden_terms():
    with TemporaryDirectory(dir=Path.cwd()) as raw_tmp:
        tmp_path = Path(raw_tmp)
        _assert_build_plan_rejects_forbidden_terms(tmp_path)


def _assert_build_plan_rejects_forbidden_terms(tmp_path):
    brand_path = tmp_path / "brand.yaml"
    brief_path = tmp_path / "brief.yaml"
    output_path = tmp_path / "plan.json"
    brand_path.write_text(BRAND_YAML, encoding="utf-8")
    brief_path.write_text(
        """
brief:
  id: campaign_01
  brand_id: brand_zero
  scenes:
    - id: bad_scene
      subject: bottle with real logo
      motion: slow turn
      camera: macro
      start_state: left
      end_state: right
""",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="forbidden terms"):
        build_plan(brand_path, brief_path, output_path)


def test_image_prompt_is_single_frame_without_end_state():
    """Regression (demo01): end-state wording in the image prompt produced storyboards."""
    with TemporaryDirectory(dir=Path.cwd()) as raw_tmp:
        out = Path(raw_tmp) / "plan.json"
        build_plan(Path("brand/brand_zero.yaml"), Path("briefs/campaign_01.yaml"), out)
        plan = json.loads(out.read_text(encoding="utf-8"))
        scenes = plan.get("scenes") or plan.get("scene_cards") or []
        assert scenes
        for scene in scenes:
            prompt = scene["image_prompt"]
            assert "End state" not in prompt
            assert "Single continuous frame" in prompt
            assert "no storyboard" in prompt
