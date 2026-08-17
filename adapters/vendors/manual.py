"""Manual request/ingest adapters for the file-based workflow."""

from __future__ import annotations

from pathlib import Path

from pipeline.generate import request_images, validate_image_manifest
from pipeline.judge import write_judgments
from pipeline.render import request_videos, validate_clip_manifest


class ManualImageModel:
    """Adapter wrapper for image request files and manifest ingest."""

    def generate(
        self,
        prompt: str,
        reference_images: list[Path],
        output_dir: Path,
    ) -> list[Path]:
        """Manual mode cannot synchronously generate media."""
        raise RuntimeError(
            "manual image adapter uses request_images() and ingest_images(), "
            "not direct generation"
        )

    def request_images(
        self,
        plan_path: Path,
        output_dir: Path,
        candidates_per_scene: int = 1,
    ) -> list[Path]:
        """Write manual image request JSON files."""
        return request_images(plan_path, output_dir, candidates_per_scene)

    def ingest_images(self, plan_path: Path, images_dir: Path) -> Path:
        """Validate a manually prepared image manifest."""
        return validate_image_manifest(plan_path, images_dir)


class ManualVideoModel:
    """Adapter wrapper for video request files and manifest ingest."""

    def render(self, image_path: Path, motion_prompt: str, output_dir: Path) -> Path:
        """Manual mode cannot synchronously render media."""
        raise RuntimeError(
            "manual video adapter uses request_videos() and ingest_clips(), "
            "not direct rendering"
        )

    def request_videos(self, gate_path: Path, plan_path: Path, output_dir: Path) -> list[Path]:
        """Write manual video request JSON files."""
        return request_videos(gate_path=gate_path, plan_path=plan_path, output_dir=output_dir)

    def ingest_clips(self, gate_path: Path, clips_dir: Path) -> Path:
        """Validate a manually prepared clip manifest."""
        return validate_clip_manifest(gate_path, clips_dir)


class ManualJudge:
    """Adapter wrapper for manual usability CSV judgments."""

    def score(self, clip_path: Path, criteria_path: Path) -> dict[str, object]:
        """Manual judging is represented by CSV input, not direct scoring."""
        raise RuntimeError("manual judge adapter uses score_csv(), not direct scoring")

    def score_csv(
        self,
        judgments_csv: Path,
        criteria_path: Path,
        output_path: Path,
        clips_manifest_path: Path | None = None,
    ) -> Path:
        """Convert manual usability CSV to JSONL."""
        return write_judgments(
            judgments_csv,
            criteria_path,
            output_path,
            clips_manifest_path=clips_manifest_path,
        )
