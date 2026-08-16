"""Clip judging adapter interface."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol


class Judge(Protocol):
    """Score a clip against usability criteria."""

    def score(self, clip_path: Path, criteria_path: Path) -> dict[str, object]:
        """Return verdict and evidence fields."""
        raise NotImplementedError
