"""Adapter selection for pipeline stages."""

from __future__ import annotations

from pathlib import Path

from adapters.image_model import ImageModel
from adapters.judge import Judge
from adapters.vendors.http_generic import HttpGenericImageModel, HttpGenericVideoModel
from adapters.vendors.llm_http import LlmHttpJudge
from adapters.vendors.manual import ManualImageModel, ManualJudge, ManualVideoModel
from adapters.video_model import VideoModel
from pipeline.common import load_env


def selected_vendor(env: dict[str, str] | None = None) -> str:
    """Return the configured vendor name."""
    values = env or load_env()
    return values.get("AX_PIPELINE_VENDOR", values.get("AX_PIPELINE_ADAPTER", "manual")).strip()


def build_image_model(env_path: Path | None = None) -> ImageModel:
    """Build the configured image model adapter."""
    env = load_env(env_path or Path(".env"))
    vendor = selected_vendor(env)
    if vendor == "manual":
        return ManualImageModel()
    if vendor == "http_generic":
        return HttpGenericImageModel(env=env)
    raise ValueError(f"unsupported AX_PIPELINE_VENDOR: {vendor}")


def build_video_model(env_path: Path | None = None) -> VideoModel:
    """Build the configured video model adapter."""
    env = load_env(env_path or Path(".env"))
    vendor = selected_vendor(env)
    if vendor == "manual":
        return ManualVideoModel()
    if vendor == "http_generic":
        return HttpGenericVideoModel(env=env)
    raise ValueError(f"unsupported AX_PIPELINE_VENDOR: {vendor}")


def build_judge(env_path: Path | None = None) -> Judge:
    """Build the configured judge adapter slot."""
    env = load_env(env_path or Path(".env"))
    vendor = selected_vendor(env)
    if vendor in {"manual", "http_generic"}:
        return ManualJudge()
    if vendor == "llm_http":
        return LlmHttpJudge(env=env)
    raise ValueError(f"unsupported AX_PIPELINE_VENDOR: {vendor}")
