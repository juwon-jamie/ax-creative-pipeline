"""Image generation adapter interface."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol


class ImageModel(Protocol):
    """Generate candidate images for a scene card."""

    def generate(
        self,
        prompt: str,
        reference_images: list[Path],
        output_dir: Path,
    ) -> list[Path]:
        """Return generated image paths."""
        raise NotImplementedError
