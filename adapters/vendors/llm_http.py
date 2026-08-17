"""Generic chat-completions HTTP adapter for LLM-based judgments."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen

from pipeline.common import read_json, write_jsonl

FAIL_CODES = {f"F{number}" for number in range(1, 8)}
PASS_CODES = {f"P{number}" for number in range(1, 8)}


def _headers(env: dict[str, str]) -> dict[str, str]:
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    api_key = env.get("LLM_JUDGE_API_KEY", "").strip()
    if api_key:
        header_name = env.get("LLM_JUDGE_API_KEY_HEADER", "Authorization").strip()
        headers[header_name] = api_key
    return headers


def _json_content(response_data: dict[str, object]) -> dict[str, object]:
    choices = response_data.get("choices")
    if not isinstance(choices, list) or not choices:
        raise ValueError("LLM response missing choices")
    first = choices[0]
    if not isinstance(first, dict):
        raise ValueError("LLM response choice must be a mapping")
    message = first.get("message")
    if not isinstance(message, dict):
        raise ValueError("LLM response missing message")
    parsed = message.get("parsed")
    if isinstance(parsed, dict):
        return parsed
    content = message.get("content")
    if isinstance(content, dict):
        return content
    if not isinstance(content, str) or not content.strip():
        raise ValueError("LLM response content must be JSON text")
    parsed_content = json.loads(content)
    if not isinstance(parsed_content, dict):
        raise ValueError("LLM JSON content must be an object")
    return parsed_content


def _codes(value: object, allowed: set[str], field: str) -> list[str]:
    if not isinstance(value, list):
        raise ValueError(f"{field} must be a list")
    codes = [str(code).strip().upper() for code in value if str(code).strip()]
    invalid = sorted(set(codes) - allowed)
    if invalid:
        joined = ", ".join(invalid)
        raise ValueError(f"{field} has invalid codes: {joined}")
    return codes


def validate_gate_judgment(row: dict[str, object]) -> dict[str, object]:
    """Validate image gate JSON returned by the LLM."""
    image_id = str(row.get("image_id", "")).strip()
    video_ready = row.get("video_ready")
    reason = str(row.get("reason", "")).strip()
    if not image_id:
        raise ValueError("gate judgment missing image_id")
    if not isinstance(video_ready, bool):
        raise ValueError("gate judgment video_ready must be boolean")
    if not reason:
        raise ValueError("gate judgment missing reason")
    return {"image_id": image_id, "video_ready": video_ready, "reason": reason}


def validate_clip_judgment(row: dict[str, object]) -> dict[str, object]:
    """Validate clip usability JSON returned by the LLM."""
    clip_id = str(row.get("clip_id", "")).strip()
    verdict = str(row.get("verdict", "")).strip().upper()
    fail_codes = _codes(row.get("fail_codes", []), FAIL_CODES, "fail_codes")
    pass_fail_codes = _codes(row.get("pass_fail_codes", []), PASS_CODES, "pass_fail_codes")
    if not clip_id:
        raise ValueError("clip judgment missing clip_id")
    if verdict not in {"USABLE", "NOT_USABLE"}:
        raise ValueError("clip judgment verdict must be USABLE or NOT_USABLE")
    if verdict == "USABLE" and (fail_codes or pass_fail_codes):
        raise ValueError("usable clip judgment must not include failure codes")
    if verdict == "NOT_USABLE" and not (fail_codes or pass_fail_codes):
        raise ValueError("not-usable clip judgment needs at least one code")
    return {
        "clip_id": clip_id,
        "verdict": verdict,
        "usable": verdict == "USABLE",
        "fail_codes": fail_codes,
        "pass_fail_codes": pass_fail_codes,
        "p7_reason": str(row.get("p7_reason", "")).strip(),
        "reason": str(row.get("reason", "")).strip(),
    }


class LlmHttpJudge:
    """LLM judge using a generic chat/completions-compatible endpoint."""

    def __init__(
        self,
        env: dict[str, str],
        prompt_path: Path = Path("criteria/judge_prompt.md"),
    ) -> None:
        self.env = env
        self.prompt_path = prompt_path
        self.max_retries = int(env.get("LLM_JUDGE_MAX_RETRIES", "2") or "2")

    def _post(self, messages: list[dict[str, str]]) -> dict[str, object]:
        url = self.env.get("LLM_JUDGE_URL", "").strip()
        if not url:
            raise ValueError("LLM_JUDGE_URL is required for llm_http")
        payload = {
            "messages": messages,
            "model": self.env.get("LLM_JUDGE_MODEL", "generic-judge"),
            "response_format": {"type": "json_object"},
            "temperature": 0,
        }
        request = Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers=_headers(self.env),
            method="POST",
        )
        with urlopen(request, timeout=60) as response:
            body = response.read().decode("utf-8")
        data = json.loads(body)
        if not isinstance(data, dict):
            raise ValueError("LLM HTTP response must be a JSON object")
        return data

    def _request_json(
        self,
        messages: list[dict[str, str]],
        validate: Callable[[dict[str, object]], dict[str, object]] | None = None,
    ) -> dict[str, object]:
        """POST, parse, and (if given) validate inside the retry loop.

        Schema validation must live inside the loop: an LLM that answers with a
        well-formed JSON object of the wrong shape is a retryable failure, not a crash.
        """
        last_error: Exception | None = None
        for _ in range(self.max_retries + 1):
            try:
                row = _json_content(self._post(messages))
                return validate(row) if validate else row
            except (ValueError, json.JSONDecodeError, URLError) as exc:
                last_error = exc
        assert last_error is not None
        raise ValueError(f"LLM judgment failed schema validation: {last_error}") from last_error

    def _system_prompt(self) -> str:
        return self.prompt_path.read_text(encoding="utf-8")

    def score_gate_image(
        self,
        image_id: str,
        image_path: Path,
        context: dict[str, object] | None = None,
    ) -> dict[str, object]:
        """Return video-readiness judgment for one image."""
        messages = [
            {"role": "system", "content": self._system_prompt()},
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "asset_type": "image_gate",
                        "image_id": image_id,
                        "image_path": image_path.as_posix(),
                        "context": context or {},
                        "required_schema": {
                            "image_id": "string",
                            "video_ready": "boolean",
                            "reason": "string",
                        },
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                ),
            },
        ]
        def _validate(row: dict[str, object]) -> dict[str, object]:
            if "image_id" not in row:
                row["image_id"] = image_id
            return validate_gate_judgment(row)

        return self._request_json(messages, _validate)

    def score_clip(
        self,
        clip_id: str,
        clip_path: Path,
        criteria_path: Path,
        context: dict[str, object] | None = None,
    ) -> dict[str, object]:
        """Return usability judgment for one clip."""
        messages = [
            {"role": "system", "content": self._system_prompt()},
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "asset_type": "clip_usability",
                        "clip_id": clip_id,
                        "clip_path": clip_path.as_posix(),
                        "context": context or {},
                        "criteria": criteria_path.read_text(encoding="utf-8"),
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                ),
            },
        ]
        def _validate(row: dict[str, object]) -> dict[str, object]:
            if "clip_id" not in row:
                row["clip_id"] = clip_id
            return validate_clip_judgment(row)

        return self._request_json(messages, _validate)

    def score(self, clip_path: Path, criteria_path: Path) -> dict[str, object]:
        """Implement the Judge protocol for direct clip scoring."""
        return self.score_clip(clip_path.stem, clip_path, criteria_path)

    def write_vlm_judgments(
        self,
        clips_manifest_path: Path,
        criteria_path: Path,
        output_path: Path,
    ) -> Path:
        """Score every clip manifest row into VLM-compatible JSONL."""
        manifest = read_json(clips_manifest_path)
        entries = manifest.get("clips", manifest)
        if not isinstance(entries, list):
            raise ValueError("clip manifest must be a list or contain clips list")
        rows: list[dict[str, object]] = []
        clips_dir = clips_manifest_path.parent
        for entry in entries:
            if not isinstance(entry, dict):
                raise ValueError("clip manifest entries must be mappings")
            clip_id = str(entry.get("clip_id", "")).strip()
            file_value = str(entry.get("file", "")).strip()
            if not clip_id or not file_value:
                raise ValueError("clip manifest entry missing clip_id or file")
            rows.append(
                self.score_clip(
                    clip_id,
                    clips_dir / file_value,
                    criteria_path,
                    context=entry,
                )
            )
        return write_jsonl(output_path, rows)

