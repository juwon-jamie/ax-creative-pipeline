"""Aggregate run metrics into a summary report."""

from __future__ import annotations

from pathlib import Path


def aggregate_run(run_dir: Path, report_path: Path) -> Path:
    """Write image, gate, render, usable, and conversion metrics."""
    raise NotImplementedError("aggregation is not implemented in the W1 skeleton")
