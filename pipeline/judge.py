"""Judge rendered clips against usability criteria."""

from __future__ import annotations

from pathlib import Path

from adapters.judge import Judge


def judge_clips(clips_dir: Path, judge: Judge, criteria_path: Path, output_path: Path) -> Path:
    """Write one judgement row per rendered clip."""
    raise NotImplementedError("clip judging is not implemented in the W1 skeleton")
