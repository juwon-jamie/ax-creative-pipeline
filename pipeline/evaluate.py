"""Evaluation harness combining rules, VLM slots, and human judgments."""

from __future__ import annotations

import csv
from pathlib import Path

from pipeline.common import read_json, read_jsonl, safe_relative_path, write_jsonl

FAIL_CODES = {f"F{number}" for number in range(1, 8)}
PASS_CODES = {f"P{number}" for number in range(1, 8)}
VERDICTS = {"USABLE", "NOT_USABLE"}


def _split_codes(raw_value: object) -> list[str]:
    if isinstance(raw_value, list):
        return [str(code).strip().upper() for code in raw_value if str(code).strip()]
    return [code.strip().upper() for code in str(raw_value).split(";") if code.strip()]


def _normalize_judgment(row: dict[str, object], source: str) -> dict[str, object]:
    verdict = str(row.get("verdict", "")).strip().upper()
    fail_codes = _split_codes(row.get("fail_codes", []))
    pass_fail_codes = _split_codes(row.get("pass_fail_codes", []))
    invalid = sorted(
        (set(fail_codes) - FAIL_CODES) | (set(pass_fail_codes) - PASS_CODES)
    )
    if verdict not in VERDICTS:
        raise ValueError(f"{source} judgment has invalid verdict: {verdict}")
    if invalid:
        joined = ", ".join(invalid)
        raise ValueError(f"{source} judgment has invalid codes: {joined}")
    if verdict == "USABLE" and (fail_codes or pass_fail_codes):
        raise ValueError(f"{source} usable judgment must not include failure codes")
    return {
        "source": source,
        "verdict": verdict,
        "usable": verdict == "USABLE",
        "fail_codes": fail_codes,
        "pass_fail_codes": pass_fail_codes,
        "p7_reason": str(row.get("p7_reason", "")).strip(),
        "reason": str(row.get("reason", "")).strip(),
    }


def _load_human_csv(path: Path | None) -> dict[str, dict[str, object]]:
    if path is None or not path.exists():
        return {}
    judgments: dict[str, dict[str, object]] = {}
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row_number, row in enumerate(reader, 2):
            clip_id = str(row.get("clip_id", "")).strip()
            if not clip_id:
                raise ValueError(f"{path}:{row_number} missing clip_id")
            judgments[clip_id] = _normalize_judgment(row, "human")
    return judgments


def _load_vlm_jsonl(path: Path | None) -> dict[str, dict[str, object]]:
    if path is None or not path.exists():
        return {}
    judgments: dict[str, dict[str, object]] = {}
    for row in read_jsonl(path):
        clip_id = str(row.get("clip_id", "")).strip()
        if not clip_id:
            raise ValueError(f"{path} contains a VLM row without clip_id")
        judgments[clip_id] = _normalize_judgment(row, "vlm")
    return judgments


def _plan_scenes(run_dir: Path) -> dict[str, dict[str, object]]:
    plan_path = run_dir / "plan.json"
    if not plan_path.exists():
        return {}
    plan = read_json(plan_path)
    return {
        str(scene.get("scene_id", "")): scene
        for scene in plan.get("scenes", [])
        if isinstance(scene, dict)
    }


def _clip_entries(run_dir: Path) -> list[dict[str, object]]:
    manifest_path = run_dir / "clips" / "manifest.json"
    manifest = read_json(manifest_path)
    entries = manifest.get("clips", manifest)
    if not isinstance(entries, list):
        raise ValueError("clip manifest must be a list or contain clips list")
    return [entry for entry in entries if isinstance(entry, dict)]


def _rule_for_clip(
    clip: dict[str, object],
    gate_by_image: dict[str, dict[str, object]],
    scenes: dict[str, dict[str, object]],
) -> dict[str, object]:
    fail_codes: list[str] = []
    pass_fail_codes: list[str] = []
    reasons: list[str] = []
    image_id = str(clip.get("image_id", "")).strip()
    gate_row = gate_by_image.get(image_id)
    scene: dict[str, object] = {}

    if gate_row is None:
        fail_codes.append("F7")
        reasons.append("clip image_id not found in gate output")
    elif not gate_row.get("video_ready"):
        fail_codes.append("F7")
        reasons.append("clip image_id was not gate-passed")
    else:
        scene_id = str(gate_row.get("scene_id", "")).strip()
        scene = scenes.get(scene_id, {})

    try:
        safe_relative_path(str(clip.get("file", "")), "clip file")
    except ValueError as exc:
        fail_codes.append("F7")
        reasons.append(str(exc))

    expected_aspect = str(scene.get("aspect_ratio", "")).strip()
    actual_aspect = str(clip.get("aspect_ratio", "")).strip()
    if actual_aspect and expected_aspect and actual_aspect != expected_aspect:
        pass_fail_codes.append("P2")
        reasons.append("aspect ratio mismatch")

    expected_resolution = str(scene.get("resolution", "")).strip()
    actual_resolution = str(clip.get("resolution", "")).strip()
    if actual_resolution and expected_resolution and actual_resolution != expected_resolution:
        pass_fail_codes.append("P2")
        reasons.append("resolution mismatch")

    actual_duration = clip.get("duration_seconds")
    expected_duration = scene.get("duration_seconds")
    if actual_duration is not None and expected_duration is not None:
        if abs(float(actual_duration) - float(expected_duration)) > 0.5:
            pass_fail_codes.append("P2")
            reasons.append("duration mismatch")

    verdict = "NOT_USABLE" if fail_codes or pass_fail_codes else "USABLE"
    return _normalize_judgment(
        {
            "verdict": verdict,
            "fail_codes": fail_codes,
            "pass_fail_codes": pass_fail_codes,
            "reason": "; ".join(reasons),
        },
        "rules",
    )


def automatic_rule_judgments(run_dir: Path) -> dict[str, dict[str, object]]:
    """Score manifest coherence and declared specs without model calls."""
    gate_by_image = {
        str(row.get("image_id", "")): row for row in read_jsonl(run_dir / "gate.jsonl")
    }
    scenes = _plan_scenes(run_dir)
    judgments: dict[str, dict[str, object]] = {}
    for clip in _clip_entries(run_dir):
        clip_id = str(clip.get("clip_id", "")).strip()
        if not clip_id:
            raise ValueError("clip manifest entry missing clip_id")
        judgments[clip_id] = _rule_for_clip(clip, gate_by_image, scenes)
    return judgments


def _choose_final(
    rules: dict[str, object] | None,
    vlm: dict[str, object] | None,
    human: dict[str, object] | None,
) -> dict[str, object]:
    for source in (human, vlm, rules):
        if source is not None:
            return source
    raise ValueError("cannot choose final judgment without any source")


def _source_verdicts(row: dict[str, object]) -> dict[str, str]:
    sources = row.get("sources", {})
    if not isinstance(sources, dict):
        return {}
    verdicts: dict[str, str] = {}
    for name, source_row in sources.items():
        if isinstance(source_row, dict) and source_row.get("verdict"):
            verdicts[str(name)] = str(source_row["verdict"])
    return verdicts


def binary_agreement(left: list[str], right: list[str]) -> dict[str, float | int]:
    """Return count, simple agreement, and Cohen's kappa for binary verdicts."""
    if len(left) != len(right):
        raise ValueError("agreement lists must have the same length")
    total = len(left)
    if total == 0:
        return {"count": 0, "agreement": 0.0, "kappa": 0.0}
    matches = sum(
        1
        for left_value, right_value in zip(left, right, strict=True)
        if left_value == right_value
    )
    observed = matches / total
    left_yes = sum(1 for value in left if value == "USABLE") / total
    right_yes = sum(1 for value in right if value == "USABLE") / total
    expected = left_yes * right_yes + (1 - left_yes) * (1 - right_yes)
    if expected == 1:
        kappa = 1.0 if observed == 1 else 0.0
    else:
        kappa = (observed - expected) / (1 - expected)
    return {"count": total, "agreement": observed, "kappa": kappa}


def agreement_by_source(
    rows: list[dict[str, object]],
    left: str,
    right: str,
) -> dict[str, float | int]:
    """Calculate agreement between two sources over shared clips."""
    left_values: list[str] = []
    right_values: list[str] = []
    for row in rows:
        verdicts = _source_verdicts(row)
        if left in verdicts and right in verdicts:
            left_values.append(verdicts[left])
            right_values.append(verdicts[right])
    return binary_agreement(left_values, right_values)


def write_agreement_report(rows: list[dict[str, object]], report_path: Path) -> Path:
    """Write rules/human and VLM/human agreement metrics."""
    comparisons = [
        ("rules_vs_human", "rules", "human"),
        ("vlm_vs_human", "vlm", "human"),
    ]
    lines = [
        "# Agreement",
        "",
        "| comparison | clips | agreement | kappa |",
        "|---|---:|---:|---:|",
    ]
    for label, left, right in comparisons:
        result = agreement_by_source(rows, left, right)
        lines.append(
            f"| {label} | {result['count']} | "
            f"{float(result['agreement']):.1%} | {float(result['kappa']):.2f} |"
        )
    lines.append("")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines), encoding="utf-8")
    return report_path


def evaluate_run(
    run_dir: Path,
    output_path: Path,
    human_csv: Path | None = None,
    vlm_jsonl: Path | None = None,
    agreement_path: Path | None = None,
) -> Path:
    """Combine rule, VLM, and human judgments into final evaluation JSONL."""
    rules = automatic_rule_judgments(run_dir)
    human = _load_human_csv(human_csv or run_dir / "judgments" / "usability.csv")
    vlm = _load_vlm_jsonl(vlm_jsonl or run_dir / "judgments" / "vlm.jsonl")
    clip_ids = sorted(set(rules) | set(human) | set(vlm))
    rows: list[dict[str, object]] = []

    for clip_id in clip_ids:
        sources = {
            name: source
            for name, source in {
                "rules": rules.get(clip_id),
                "vlm": vlm.get(clip_id),
                "human": human.get(clip_id),
            }.items()
            if source is not None
        }
        final = _choose_final(rules.get(clip_id), vlm.get(clip_id), human.get(clip_id))
        rows.append(
            {
                "clip_id": clip_id,
                "verdict": final["verdict"],
                "usable": final["usable"],
                "fail_codes": final["fail_codes"],
                "pass_fail_codes": final["pass_fail_codes"],
                "p7_reason": final["p7_reason"],
                "reason": final["reason"],
                "final_source": final["source"],
                "sources": sources,
            }
        )

    write_jsonl(output_path, rows)
    write_agreement_report(rows, agreement_path or Path("reports") / "agreement.md")
    return output_path
