"""Generate image candidates from scene cards."""

from __future__ import annotations

from pathlib import Path

from adapters.image_model import ImageModel


def generate_images(plan_path: Path, image_model: ImageModel, output_dir: Path) -> list[Path]:
    """Generate image candidates and return their paths."""
    raise NotImplementedError("image generation is not implemented in the W1 skeleton")
