"""Generic HTTP JSON adapter for image and video models."""

from __future__ import annotations

import base64
import json
import mimetypes
from pathlib import Path
from urllib.request import Request, urlopen

from pipeline.common import get_dotted, load_yaml, safe_relative_path, set_dotted, stable_hash

MAPPING_PATH = Path(__file__).with_name("mapping.yaml")


def _load_mapping(kind: str, mapping_path: Path = MAPPING_PATH) -> dict[str, object]:
    mapping = load_yaml(mapping_path)
    vendor = mapping.get("http_generic", {})
    if not isinstance(vendor, dict):
        raise ValueError("mapping.yaml missing http_generic section")
    section = vendor.get(kind, {})
    if not isinstance(section, dict):
        raise ValueError(f"mapping.yaml missing http_generic.{kind} section")
    return section


def _mapped_payload(mapping: dict[str, object], source: dict[str, object]) -> dict[str, object]:
    payload_map = mapping.get("payload", {})
    if not isinstance(payload_map, dict):
        raise ValueError("payload mapping must be a mapping")
    payload: dict[str, object] = {}
    for target_path, source_path in payload_map.items():
        value = get_dotted(source, str(source_path))
        set_dotted(payload, str(target_path), value)
    return payload


def _response_fields(mapping: dict[str, object]) -> dict[str, str]:
    fields = mapping.get("response", {})
    if not isinstance(fields, dict):
        raise ValueError("response mapping must be a mapping")
    return {str(key): str(value) for key, value in fields.items()}


def _headers(env: dict[str, str], prefix: str) -> dict[str, str]:
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    api_key = env.get(f"{prefix}_API_KEY", "").strip()
    if api_key:
        header_name = env.get(f"{prefix}_API_KEY_HEADER", "Authorization").strip()
        headers[header_name] = api_key
    return headers


def _post_json(url: str, payload: dict[str, object], headers: dict[str, str]) -> dict[str, object]:
    request = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    with urlopen(request, timeout=60) as response:
        body = response.read().decode("utf-8")
    data = json.loads(body)
    if not isinstance(data, dict):
        raise ValueError("HTTP adapter response must be a JSON object")
    return data


def _read_url(url: str) -> tuple[bytes, str]:
    with urlopen(url, timeout=60) as response:
        content_type = response.headers.get("Content-Type", "")
        return response.read(), content_type


def _safe_output_path(output_dir: Path, filename: str) -> Path:
    path = safe_relative_path(Path(filename).name, "response filename")
    return output_dir / path


def _extension_from_type(content_type: str, default: str) -> str:
    media_type = content_type.split(";", 1)[0].strip()
    return mimetypes.guess_extension(media_type) or default


def _write_response_file(
    response_data: dict[str, object],
    mapping: dict[str, object],
    output_dir: Path,
    seed: str,
) -> Path:
    fields = _response_fields(mapping)
    filename = get_dotted(response_data, fields.get("filename", ""))
    default_extension = str(mapping.get("default_extension", ".bin"))
    if filename is None:
        filename = f"{stable_hash(seed)}{default_extension}"
    output_path = _safe_output_path(output_dir, str(filename))

    base64_value = get_dotted(response_data, fields.get("base64", ""))
    url_value = get_dotted(response_data, fields.get("url", ""))
    if isinstance(base64_value, str) and base64_value.strip():
        content = base64.b64decode(base64_value)
    elif isinstance(url_value, str) and url_value.strip():
        content, content_type = _read_url(url_value)
        if output_path.suffix == ".bin":
            output_path = output_path.with_suffix(
                _extension_from_type(content_type, default_extension)
            )
    else:
        raise ValueError("HTTP adapter response must include mapped url or base64")

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(content)
    return output_path


class HttpGenericImageModel:
    """Image adapter for generic JSON-over-HTTP endpoints."""

    def __init__(
        self,
        env: dict[str, str],
        mapping_path: Path = MAPPING_PATH,
    ) -> None:
        self.env = env
        self.mapping = _load_mapping("image", mapping_path)

    def generate(
        self,
        prompt: str,
        reference_images: list[Path],
        output_dir: Path,
    ) -> list[Path]:
        """POST an image request and save the returned artifact."""
        url = self.env.get("IMAGE_MODEL_URL", "").strip()
        if not url:
            raise ValueError("IMAGE_MODEL_URL is required for http_generic")
        source = {
            "prompt": prompt,
            "reference_images": [path.as_posix() for path in reference_images],
        }
        payload = _mapped_payload(self.mapping, source)
        response_data = _post_json(url, payload, _headers(self.env, "IMAGE_MODEL"))
        path = _write_response_file(response_data, self.mapping, output_dir, prompt)
        return [path]


class HttpGenericVideoModel:
    """Video adapter for generic JSON-over-HTTP endpoints."""

    def __init__(
        self,
        env: dict[str, str],
        mapping_path: Path = MAPPING_PATH,
    ) -> None:
        self.env = env
        self.mapping = _load_mapping("video", mapping_path)

    def render(self, image_path: Path, motion_prompt: str, output_dir: Path) -> Path:
        """POST a video request and save the returned artifact."""
        url = self.env.get("VIDEO_MODEL_URL", "").strip()
        if not url:
            raise ValueError("VIDEO_MODEL_URL is required for http_generic")
        source = {
            "image_path": image_path.as_posix(),
            "motion_prompt": motion_prompt,
        }
        payload = _mapped_payload(self.mapping, source)
        response_data = _post_json(url, payload, _headers(self.env, "VIDEO_MODEL"))
        return _write_response_file(response_data, self.mapping, output_dir, motion_prompt)
