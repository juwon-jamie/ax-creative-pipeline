"""Shared file helpers for the clean-room pipeline."""

from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path
from typing import Any

import yaml

JsonObject = dict[str, Any]


def load_yaml(path: Path) -> JsonObject:
    """Read a YAML mapping from disk."""
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a YAML mapping")
    return data


def read_json(path: Path) -> Any:
    """Read JSON from disk."""
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: Any) -> Path:
    """Write stable, UTF-8 JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


def read_jsonl(path: Path) -> list[JsonObject]:
    """Read a JSONL file into mappings."""
    if not path.exists():
        return []
    rows: list[JsonObject] = []
    lines = path.read_text(encoding="utf-8").splitlines()
    for line_number, line in enumerate(lines, 1):
        if not line.strip():
            continue
        row = json.loads(line)
        if not isinstance(row, dict):
            raise ValueError(f"{path}:{line_number} must contain a JSON object")
        rows.append(row)
    return rows


def write_jsonl(path: Path, rows: list[JsonObject]) -> Path:
    """Write JSONL rows."""
    path.parent.mkdir(parents=True, exist_ok=True)
    text = "".join(
        json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows
    )
    path.write_text(text, encoding="utf-8")
    return path


def stable_hash(value: str, length: int = 16) -> str:
    """Return a short stable hash for prompt/request matching."""
    return sha256(value.encode("utf-8")).hexdigest()[:length]


def require_mapping(value: Any, name: str) -> JsonObject:
    """Require a value to be a mapping."""
    if not isinstance(value, dict):
        raise ValueError(f"{name} must be a mapping")
    return value


def require_list(value: Any, name: str) -> list[Any]:
    """Require a value to be a list."""
    if not isinstance(value, list):
        raise ValueError(f"{name} must be a list")
    return value


def safe_relative_path(value: str, field_name: str) -> Path:
    """Validate a manifest path field as relative and local."""
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(f"{field_name} must be a relative path inside the run")
    return path
