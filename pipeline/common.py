"""Shared file helpers for the clean-room pipeline."""

from __future__ import annotations

import json
import os
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


def load_env(path: Path | None = None) -> dict[str, str]:
    """Return process environment overlaid with a simple .env file."""
    path = path or Path(".env")
    env = dict(os.environ)
    if not path.exists():
        return env
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].strip()
        if "=" not in line:
            raise ValueError(f"{path}:{line_number} must be KEY=VALUE")
        key, value = line.split("=", 1)
        key = key.strip()
        if not key:
            raise ValueError(f"{path}:{line_number} has an empty key")
        env[key] = value.strip().strip("'\"")
    return env


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


def get_dotted(data: Any, path: str) -> Any:
    """Return a nested value from a dotted path, or None when absent."""
    if not path:
        return data
    current = data
    for part in path.split("."):
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return None
    return current


def set_dotted(data: JsonObject, path: str, value: Any) -> None:
    """Set a nested mapping value from a dotted path."""
    parts = [part for part in path.split(".") if part]
    if not parts:
        raise ValueError("dotted path must not be empty")
    current = data
    for part in parts[:-1]:
        child = current.setdefault(part, {})
        if not isinstance(child, dict):
            raise ValueError(f"{path} conflicts with a non-mapping value")
        current = child
    current[parts[-1]] = value


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
