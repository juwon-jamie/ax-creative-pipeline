from pipeline.gate import is_scene_video_ready, missing_scene_fields


def test_scene_with_required_motion_fields_is_video_ready():
    scene = {
        "subject": "unbranded bottle",
        "motion": "slow turn",
        "camera": "macro close-up",
        "start_state": "left angle",
        "end_state": "right angle",
    }

    assert missing_scene_fields(scene) == []
    assert is_scene_video_ready(scene)


def test_scene_missing_motion_is_not_video_ready():
    scene = {
        "subject": "unbranded bottle",
        "motion": "",
        "camera": "macro close-up",
        "start_state": "left angle",
        "end_state": "right angle",
    }

    assert missing_scene_fields(scene) == ["motion"]
    assert not is_scene_video_ready(scene)
