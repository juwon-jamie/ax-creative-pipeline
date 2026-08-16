"""Video rendering adapter interface."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol


class VideoModel(Protocol):
    """Render a clip from one image and one motion prompt."""

    def render(self, image_path: Path, motion_prompt: str, output_dir: Path) -> Path:
        """Return rendered clip path."""
        raise NotImplementedError
