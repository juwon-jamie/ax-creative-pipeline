import json
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from adapters.vendors import llm_http
from adapters.vendors.llm_http import (
    LlmHttpJudge,
    validate_clip_judgment,
    validate_gate_judgment,
)
from pipeline.common import read_jsonl, write_json


class FakeResponse:
    def __init__(self, body: dict[str, object]):
        self.body = json.dumps(body).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self):
        return self.body


def _chat_response(content: dict[str, object]) -> dict[str, object]:
    return {"choices": [{"message": {"content": json.dumps(content)}}]}


def test_llm_http_clip_score_retries_invalid_schema(monkeypatch):
    calls = []

    def fake_urlopen(request, timeout):
        calls.append(json.loads(request.data.decode("utf-8")))
        if len(calls) == 1:
            return FakeResponse(_chat_response({"clip_id": "clip_01"}))
        return FakeResponse(
            _chat_response(
                {
                    "clip_id": "clip_01",
                    "verdict": "NOT_USABLE",
                    "fail_codes": ["F1"],
                    "pass_fail_codes": [],
                    "p7_reason": "unstable shape",
                    "reason": "shape melts",
                }
            )
        )

    monkeypatch.setattr(llm_http, "urlopen", fake_urlopen)
    judge = LlmHttpJudge(
        env={
            "LLM_JUDGE_MAX_RETRIES": "1",
            "LLM_JUDGE_MODEL": "generic-judge",
            "LLM_JUDGE_URL": "https://example.invalid/chat",
        }
    )

    result = judge.score_clip("clip_01", Path("clip.mp4"), Path("criteria/judge_prompt.md"))

    assert len(calls) == 2
    assert result["fail_codes"] == ["F1"]
    assert result["usable"] is False


def test_llm_http_gate_judgment_requires_boolean():
    with pytest.raises(ValueError, match="video_ready"):
        validate_gate_judgment({"image_id": "img_01", "video_ready": "Y", "reason": "ok"})


def test_llm_http_clip_judgment_rejects_usable_with_codes():
    with pytest.raises(ValueError, match="usable clip"):
        validate_clip_judgment(
            {
                "clip_id": "clip_01",
                "verdict": "USABLE",
                "fail_codes": ["F1"],
                "pass_fail_codes": [],
            }
        )


def test_llm_http_score_gate_image_uses_prompt_and_context(monkeypatch):
    def fake_urlopen(request, timeout):
        payload = json.loads(request.data.decode("utf-8"))
        assert payload["messages"][1]["content"]
        assert payload["model"] == "generic-judge"
        return FakeResponse(
            _chat_response(
                {"image_id": "img_01", "video_ready": True, "reason": "single frame"}
            )
        )

    monkeypatch.setattr(llm_http, "urlopen", fake_urlopen)
    judge = LlmHttpJudge(
        env={
            "LLM_JUDGE_MAX_RETRIES": "0",
            "LLM_JUDGE_MODEL": "generic-judge",
            "LLM_JUDGE_URL": "https://example.invalid/chat",
        }
    )

    result = judge.score_gate_image("img_01", Path("image.png"), {"scene_id": "scene_01"})

    assert result == {"image_id": "img_01", "video_ready": True, "reason": "single frame"}


def test_llm_http_write_vlm_judgments(monkeypatch):
    def fake_urlopen(request, timeout):
        payload = json.loads(request.data.decode("utf-8"))
        content = json.loads(payload["messages"][1]["content"])
        clip_id = content["clip_id"]
        return FakeResponse(
            _chat_response(
                {
                    "clip_id": clip_id,
                    "verdict": "USABLE",
                    "fail_codes": [],
                    "pass_fail_codes": [],
                    "p7_reason": "",
                    "reason": "",
                }
            )
        )

    monkeypatch.setattr(llm_http, "urlopen", fake_urlopen)
    with TemporaryDirectory(dir=Path.cwd()) as raw_tmp:
        tmp_path = Path(raw_tmp)
        manifest_path = tmp_path / "clips" / "manifest.json"
        write_json(
            manifest_path,
            {"clips": [{"clip_id": "clip_01", "file": "clip_01.mp4"}]},
        )
        output_path = tmp_path / "vlm.jsonl"
        judge = LlmHttpJudge(
            env={
                "LLM_JUDGE_MAX_RETRIES": "0",
                "LLM_JUDGE_URL": "https://example.invalid/chat",
            }
        )

        judge.write_vlm_judgments(manifest_path, Path("criteria/judge_prompt.md"), output_path)

        assert read_jsonl(output_path)[0]["clip_id"] == "clip_01"

