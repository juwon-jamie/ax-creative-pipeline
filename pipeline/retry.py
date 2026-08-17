"""Retry policy and attempt history helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from pipeline.common import load_yaml, read_jsonl, write_jsonl

FAIL_CODES = {f"F{number}" for number in range(1, 8)}
DEFAULT_POLICY_PATH = Path("policies/retry.yaml")


def load_retry_policy(path: Path = DEFAULT_POLICY_PATH) -> dict[str, object]:
    """Load retry policy YAML, returning safe defaults when absent."""
    if not path.exists():
        return {"defaults": {"max_retries": 0}, "codes": {}}
    return load_yaml(path)


def _policy_for_code(policy: dict[str, object], code: str) -> dict[str, object]:
    defaults = policy.get("defaults", {})
    code_policies = policy.get("codes", {})
    if not isinstance(defaults, dict):
        defaults = {}
    if not isinstance(code_policies, dict):
        code_policies = {}
    selected = dict(defaults)
    raw_code_policy = code_policies.get(code, {})
    if isinstance(raw_code_policy, dict):
        selected.update(raw_code_policy)
    return selected


def failures_from_judgments(rows: Iterable[dict[str, object]]) -> list[dict[str, str]]:
    """Extract retryable F-code failures from judgment-like rows."""
    failures: list[dict[str, str]] = []
    for row in rows:
        if row.get("usable") is True or str(row.get("verdict", "")).upper() == "USABLE":
            continue
        asset_id = str(row.get("clip_id") or row.get("image_id") or row.get("asset_id") or "")
        reason = str(row.get("p7_reason") or row.get("reason") or "").strip()
        for raw_code in row.get("fail_codes", []):
            code = str(raw_code).upper()
            if code in FAIL_CODES:
                failures.append({"asset_id": asset_id, "code": code, "reason": reason})
    return failures


def _attempt_counts(rows: Iterable[dict[str, object]]) -> dict[tuple[str, str, str], int]:
    counts: dict[tuple[str, str, str], int] = {}
    for row in rows:
        key = (
            str(row.get("stage", "")),
            str(row.get("asset_id", "")),
            str(row.get("code", "")),
        )
        counts[key] = counts.get(key, 0) + 1
    return counts


def _format_action(policy: dict[str, object], failure: dict[str, str]) -> str:
    template = str(policy.get("prompt_adjustment") or policy.get("action") or "")
    if not template:
        return "retry"
    return template.format(
        asset_id=failure.get("asset_id", ""),
        code=failure.get("code", ""),
        reason=failure.get("reason", ""),
    )


def record_retry_attempts(
    run_dir: Path,
    stage: str,
    failures: Iterable[dict[str, str]],
    policy_path: Path = DEFAULT_POLICY_PATH,
) -> Path:
    """Append retry attempts allowed by policy to runs/<id>/attempts.jsonl."""
    attempts_path = run_dir / "attempts.jsonl"
    existing = read_jsonl(attempts_path)
    counts = _attempt_counts(existing)
    next_attempt_no = max([int(row.get("attempt_no", 0)) for row in existing] + [0]) + 1
    policy = load_retry_policy(policy_path)
    appended: list[dict[str, object]] = []

    for failure in failures:
        code = failure.get("code", "").upper()
        if code not in FAIL_CODES:
            continue
        asset_id = failure.get("asset_id", "")
        selected = _policy_for_code(policy, code)
        max_retries = int(selected.get("max_retries", 0))
        key = (stage, asset_id, code)
        if counts.get(key, 0) >= max_retries:
            continue
        appended.append(
            {
                "attempt_no": next_attempt_no,
                "stage": stage,
                "asset_id": asset_id,
                "code": code,
                "action": str(selected.get("action", "retry")),
                "prompt_adjustment": _format_action(selected, failure),
                "max_retries": max_retries,
                "status": "queued",
            }
        )
        counts[key] = counts.get(key, 0) + 1
        next_attempt_no += 1

    if appended:
        write_jsonl(attempts_path, existing + appended)
    elif not attempts_path.exists():
        write_jsonl(attempts_path, existing)
    return attempts_path
