from pathlib import Path

from tools.manual_ingest import compose_product_name, infer_mode, prepare_reference_urls


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
