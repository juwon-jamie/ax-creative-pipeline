"""Validate manual usability judgments and write judge JSONL."""

from __future__ import annotations

import csv
from pathlib import Path

from adapters.judge import Judge
from pipeline.common import read_json, write_jsonl

FAIL_CODES = {f"F{number}" for number in range(1, 8)}
PASS_CODES = {f"P{number}" for number in range(1, 8)}


def _split_codes(raw_value: str) -> list[str]:
    return [code.strip().upper() for code in raw_value.split(";") if code.strip()]


def _validate_criteria_text(criteria_path: Path) -> None:
    criteria = criteria_path.read_text(encoding="utf-8")
    missing = sorted((FAIL_CODES | PASS_CODES) - set(_codes_in_text(criteria)))
    if missing:
        joined = ", ".join(missing)
        raise ValueError(f"criteria file is missing codes: {joined}")


def _codes_in_text(value: str) -> set[str]:
    codes: set[str] = set()
    for code in FAIL_CODES | PASS_CODES:
        if code in value:
            codes.add(code)
    return codes


def write_judgments(
    judgments_csv: Path,
    criteria_path: Path,
    output_path: Path,
    clips_manifest_path: Path | None = None,
) -> Path:
    """Convert manual usability CSV judgments to judge.jsonl."""
    _validate_criteria_text(criteria_path)
    known_clip_ids: set[str] | None = None
    if clips_manifest_path and clips_manifest_path.exists():
        manifest = read_json(clips_manifest_path)
        entries = manifest.get("clips", manifest)
        if not isinstance(entries, list):
            raise ValueError("clip manifest must be a list or contain clips list")
        known_clip_ids = {str(entry.get("clip_id", "")) for entry in entries}

    rows: list[dict[str, object]] = []
    with judgments_csv.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row_number, row in enumerate(reader, 2):
            clip_id = str(row.get("clip_id", "")).strip()
            verdict = str(row.get("verdict", "")).strip().upper()
            fail_codes = _split_codes(str(row.get("fail_codes", "")))
            pass_fail_codes = _split_codes(str(row.get("pass_fail_codes", "")))
            p7_reason = str(row.get("p7_reason", "")).strip()
            if not clip_id:
                raise ValueError(f"{judgments_csv}:{row_number} missing clip_id")
            if known_clip_ids is not None and clip_id not in known_clip_ids:
                raise ValueError(f"{judgments_csv}:{row_number} unknown clip_id")
            if verdict not in {"USABLE", "NOT_USABLE"}:
                raise ValueError(f"{judgments_csv}:{row_number} invalid verdict")
            invalid_fail = sorted(set(fail_codes) - FAIL_CODES)
            invalid_pass = sorted(set(pass_fail_codes) - PASS_CODES)
            if invalid_fail or invalid_pass:
                invalid = ", ".join(invalid_fail + invalid_pass)
                raise ValueError(
                    f"{judgments_csv}:{row_number} invalid codes: {invalid}"
                )
            has_failure_data = fail_codes or pass_fail_codes or p7_reason
            if verdict == "USABLE" and has_failure_data:
                raise ValueError(
                    f"{judgments_csv}:{row_number} usable clip has failure data"
                )
            if verdict == "NOT_USABLE" and not has_failure_data:
                raise ValueError(
                    f"{judgments_csv}:{row_number} missing not-usable reason"
                )
            rows.append(
                {
                    "clip_id": clip_id,
                    "verdict": verdict,
                    "usable": verdict == "USABLE",
                    "fail_codes": fail_codes,
                    "pass_fail_codes": pass_fail_codes,
                    "p7_reason": p7_reason,
                }
            )
    return write_jsonl(output_path, rows)


def judge_clips(
    clips_dir: Path,
    judge: Judge,
    criteria_path: Path,
    output_path: Path,
) -> Path:
    """Write one judgement row per rendered clip."""
    _validate_criteria_text(criteria_path)
    manifest = read_json(clips_dir / "manifest.json")
    entries = manifest.get("clips", manifest)
    if not isinstance(entries, list):
        raise ValueError("clip manifest must be a list or contain clips list")
    rows: list[dict[str, object]] = []
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError("clip manifest entries must be mappings")
        clip_id = str(entry["clip_id"])
        result = judge.score(Path(str(entry["file"])), criteria_path)
        verdict = str(result.get("verdict", "")).upper()
        if verdict not in {"USABLE", "NOT_USABLE"}:
            raise ValueError(f"judge returned invalid verdict for {clip_id}")
        rows.append({"clip_id": clip_id, "usable": verdict == "USABLE", **result})
    return write_jsonl(output_path, rows)
