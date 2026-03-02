from pathlib import Path

from PIL import Image

from tools.manual_ingest import (
    compose_product_name,
    infer_frame_ratio_from_mockup_paths,
    infer_mode,
    prepare_reference_urls,
)


class _DummyUploader:
    def upload_file(self, path: Path) -> str:
        return f"https://example.invalid/{path.name}"


class _FailingUploader:
    def upload_file(self, path: Path) -> str:
        raise RuntimeError("upload failed")


def test_compose_product_name_prefers_code_and_name() -> None:
    value = compose_product_name(frame_code="CX-001", frame_name="Atlas", product=None)
    assert value == "[CX-001] Atlas"


def test_compose_product_name_fallbacks() -> None:
    assert compose_product_name(frame_code=None, frame_name="Atlas", product=None) == "Atlas"
    assert compose_product_name(frame_code="CX-002", frame_name=None, product=None) == "Quadro CX-002"
    assert compose_product_name(frame_code=None, frame_name=None, product="Produto X") == "Produto X"


def test_infer_mode_uses_img2img_when_reference_exists() -> None:
    assert infer_mode(["https://example.invalid/ref.png"], explicit_mode=None) == "img2img"
    assert infer_mode([], explicit_mode=None) == "txt2img"


def test_prepare_reference_urls_merges_upload_and_urls(tmp_path: Path) -> None:
    mockup = tmp_path / "mockup.png"
    mockup.write_bytes(b"img")
    urls = prepare_reference_urls(
        mockup_paths=[str(mockup)],
        mockup_urls=["https://example.invalid/a.png"],
        uploader=_DummyUploader(),
    )
    assert "https://example.invalid/a.png" in urls
    assert any(url.endswith("/mockup.png") for url in urls)


def test_prepare_reference_urls_falls_back_to_local_path_on_upload_failure(tmp_path: Path) -> None:
    mockup = tmp_path / "mockup.png"
    mockup.write_bytes(b"img")
    urls = prepare_reference_urls(
        mockup_paths=[str(mockup)],
        mockup_urls=[],
        uploader=_FailingUploader(),
    )
    assert urls == [str(mockup.resolve())]


def test_infer_frame_ratio_prefers_non_square_candidate(tmp_path: Path) -> None:
    square = tmp_path / "Mock Ups - Frame Front" / "front.png"
    square.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (1200, 1200), "white").save(square)

    raw = tmp_path / "Quadros prontos & Mock Ups" / "#107 - Crushed 100 Golden Bill.jpg"
    raw.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (2792, 1398), "white").save(raw)

    ratio = infer_frame_ratio_from_mockup_paths([str(square), str(raw)])
    assert ratio == "2:1"


def test_infer_frame_ratio_returns_square_when_only_square_exists(tmp_path: Path) -> None:
    square = tmp_path / "front.png"
    Image.new("RGB", (6000, 6000), "white").save(square)
    ratio = infer_frame_ratio_from_mockup_paths([str(square)])
    assert ratio == "1:1"


def test_infer_frame_ratio_uses_visible_alpha_bbox(tmp_path: Path) -> None:
    front = tmp_path / "Mock Ups - Frame Front" / "#107 - Front png.png"
    front.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGBA", (1000, 1000), (0, 0, 0, 0))
    # Simulate a centered frame object occupying 2:1 bounding box.
    for x in range(200, 800):
        for y in range(350, 650):
            image.putpixel((x, y), (0, 0, 0, 255))
    image.save(front)

    ratio = infer_frame_ratio_from_mockup_paths([str(front)])
    assert ratio == "2:1"
