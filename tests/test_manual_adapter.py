from pathlib import Path
from tempfile import TemporaryDirectory

from adapters.vendors.manual import ManualImageModel
from pipeline.common import write_json


def test_manual_image_adapter_writes_request_files():
    with TemporaryDirectory(dir=Path.cwd()) as raw_tmp:
        tmp_path = Path(raw_tmp)
        plan_path = tmp_path / "plan.json"
        write_json(
            plan_path,
            {
                "scenes": [
                    {
                        "scene_id": "scene_01",
                        "image_prompt": "prompt",
                        "image_prompt_hash": "hash",
                        "aspect_ratio": "9:16",
                        "resolution": "1080x1920",
                    }
                ]
            },
        )
        output_dir = tmp_path / "requests"

        paths = ManualImageModel().request_images(plan_path, output_dir, candidates_per_scene=2)

        assert [path.name for path in paths] == ["scene_01-01.json", "scene_01-02.json"]
        assert all(path.exists() for path in paths)
