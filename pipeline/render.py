"""Render accepted image candidates into clips."""

from __future__ import annotations

from pathlib import Path

from adapters.video_model import VideoModel


def render_clips(gate_path: Path, video_model: VideoModel, output_dir: Path) -> list[Path]:
    """Render clips from accepted images and return clip paths."""
    raise NotImplementedError("video rendering is not implemented in the W1 skeleton")
