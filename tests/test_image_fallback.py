from pathlib import Path
from typing import Any

from tools.config import AppSettings, PricingConfig, RuntimeSecrets
from tools.image_gen import generate_images
from tools.models import LocalAsset


class DummyAirtable:
    def __init__(self) -> None:
        self.updates: list[dict[str, Any]] = []

    def update_record_assets(self, **kwargs: Any) -> None:
        self.updates.append(kwargs)


class DummyUploader:
    def upload_file(self, path: Path) -> str:
        return f"https://example.invalid/{path.name}"


def test_generate_images_fallback_from_kie_to_google(tmp_path: Path) -> None:
    call_order: list[str] = []

    def fake_generate_single(**kwargs: Any) -> LocalAsset:
        provider = kwargs["provider"]
        call_order.append(provider)
        if provider == "kie":
            raise RuntimeError("kie unavailable")
        file_path = tmp_path / "ok-google.png"
        file_path.write_bytes(b"img")
        return LocalAsset(provider="google", local_path=file_path, cost_usd=0.1)

    airtable = DummyAirtable()
    result = generate_images(
        records=[
            {
                "airtable_record_id": "rec123",
                "ad_name": "test ad",
                "prompt_json": {"prompt": "hello", "settings": {"resolution": "1024x1792"}},
                "reference_images": [],
            }
        ],
        provider_order=["kie", "google"],
        settings=AppSettings(),
        pricing=PricingConfig(images={"google": {"1024x1792": 0.1}}, videos={}),
        secrets=RuntimeSecrets(),
        output_dir=tmp_path,
        batch_id="batch-1",
        airtable=airtable,
        uploader=DummyUploader(),
        single_generator=fake_generate_single,
    )

    assert call_order == ["kie", "google"]
    assert result.success_count == 1
    assert airtable.updates[0]["provider"] == "google"
