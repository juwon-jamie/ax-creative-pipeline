import base64
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from adapters.vendors import http_generic
from adapters.vendors.http_generic import HttpGenericImageModel, HttpGenericVideoModel


class FakeResponse:
    def __init__(self, body: dict[str, object]):
        self.body = json.dumps(body).encode("utf-8")
        self.headers = {"Content-Type": "application/json"}

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self):
        return self.body


def test_http_generic_image_saves_base64_response(monkeypatch):
    with TemporaryDirectory(dir=Path.cwd()) as raw_tmp:
        tmp_path = Path(raw_tmp)

        def fake_urlopen(request, timeout):
            assert timeout == 60
            payload = json.loads(request.data.decode("utf-8"))
            assert payload["prompt"] == "clean product frame"
            assert request.headers["X-api-key"] == "test-key"
            encoded = base64.b64encode(b"image-bytes").decode("ascii")
            return FakeResponse(
                {"output": {"base64": encoded, "filename": "image.png"}}
            )

        monkeypatch.setattr(http_generic, "urlopen", fake_urlopen)
        model = HttpGenericImageModel(
            env={
                "IMAGE_MODEL_URL": "https://example.invalid/image",
                "IMAGE_MODEL_API_KEY": "test-key",
                "IMAGE_MODEL_API_KEY_HEADER": "X-API-Key",
            }
        )

        paths = model.generate("clean product frame", [], tmp_path)

        assert paths == [tmp_path / "image.png"]
        assert paths[0].read_bytes() == b"image-bytes"


def test_http_generic_video_saves_base64_response(monkeypatch):
    with TemporaryDirectory(dir=Path.cwd()) as raw_tmp:
        tmp_path = Path(raw_tmp)

        def fake_urlopen(request, timeout):
            payload = json.loads(request.data.decode("utf-8"))
            assert payload["motion_prompt"] == "slow turn"
            assert payload["image_path"] == "source.png"
            encoded = base64.b64encode(b"video-bytes").decode("ascii")
            return FakeResponse(
                {"output": {"base64": encoded, "filename": "clip.mp4"}}
            )

        monkeypatch.setattr(http_generic, "urlopen", fake_urlopen)
        model = HttpGenericVideoModel(
            env={"VIDEO_MODEL_URL": "https://example.invalid/video"}
        )

        path = model.render(Path("source.png"), "slow turn", tmp_path)

        assert path == tmp_path / "clip.mp4"
        assert path.read_bytes() == b"video-bytes"
