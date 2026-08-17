from pathlib import Path
from tempfile import TemporaryDirectory

from pipeline.common import read_jsonl, write_json
from pipeline.gate import gate_images


def test_gate_images_combines_plan_manifest_and_manual_judgment():
    with TemporaryDirectory(dir=Path.cwd()) as raw_tmp:
        tmp_path = Path(raw_tmp)
        _assert_gate_images_combines_plan_manifest_and_manual_judgment(tmp_path)


def _assert_gate_images_combines_plan_manifest_and_manual_judgment(tmp_path):
    plan_path = tmp_path / "plan.json"
    images_dir = tmp_path / "images"
    judgments_dir = tmp_path / "judgments"
    output_path = tmp_path / "gate.jsonl"
    images_dir.mkdir()
    judgments_dir.mkdir()
    write_json(
        plan_path,
        {
            "scenes": [
                {
                    "scene_id": "texture_drop",
                    "subject": "ampoule drop",
                    "motion": "slow slide",
                    "camera": "macro",
                    "start_state": "suspended",
                    "end_state": "film",
                    "image_prompt_hash": "abc123",
                    "forbidden_hits": [],
                }
            ]
        },
    )
    write_json(
        images_dir / "manifest.json",
        {
            "images": [
                {
                    "image_id": "img_01",
                    "scene_id": "texture_drop",
                    "file": "img_01.png",
                    "prompt_hash": "abc123",
                }
            ]
        },
    )
    manual_path = judgments_dir / "gate_manual.csv"
    manual_path.write_text(
        "image_id,video_ready,reason\nimg_01,Y,ready for motion\n",
        encoding="utf-8",
    )

    gate_images(plan_path, images_dir, output_path, judgments_path=manual_path)

    rows = read_jsonl(output_path)
    assert len(rows) == 1
    assert rows[0]["image_id"] == "img_01"
    assert rows[0]["rule_ready"] is True
    assert rows[0]["manual_ready"] is True
    assert rows[0]["video_ready"] is True
