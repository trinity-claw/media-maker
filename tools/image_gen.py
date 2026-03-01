from __future__ import annotations

import base64
import io
import json
import mimetypes
import shutil
import time
from pathlib import Path
from typing import Any, Callable

import requests
from PIL import Image

from tools.airtable import AirtableClient
from tools.config import AppSettings, PricingConfig, RuntimeSecrets
from tools.models import CanonicalPrompt, GenerationItem, GenerationResult, LocalAsset
from tools.prompt_engine import normalize_prompt_schema
from tools.upload import KieUploader
from tools.utils import ensure_dir, now_utc_slug, slugify


PLACEHOLDER_PNG_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8Xw8AAqMB9J8kMh8AAAAASUVORK5CYII="
)


def _image_unit_price(pricing: PricingConfig, provider: str, resolution: str) -> float:
    table = pricing.images.get(provider, {})
    if resolution in table:
        return float(table[resolution])
    if table:
        return float(next(iter(table.values())))
    raise KeyError(f"No image price for provider={provider}")


def _write_placeholder_image(target: Path) -> None:
    ensure_dir(target.parent)
    target.write_bytes(base64.b64decode(PLACEHOLDER_PNG_B64))


def _extract_google_inline_image(payload: dict[str, Any]) -> bytes:
    candidates = payload.get("candidates", []) or []
    for candidate in candidates:
        content = candidate.get("content", {}) or {}
        for part in content.get("parts", []) or []:
            inline_data = part.get("inlineData", {}) or {}
            data = inline_data.get("data")
            if data:
                return base64.b64decode(data)
    raise ValueError("Google response did not include inline image data.")


def _generate_with_google(
    prompt: CanonicalPrompt,
    output_path: Path,
    settings: AppSettings,
    secrets: RuntimeSecrets,
    refs: list[str],
) -> None:
    if not secrets.google_api_key:
        raise ValueError("GOOGLE_API_KEY is required for google provider.")

    endpoint = settings.providers.google.image_endpoint_template.format(
        model=settings.providers.google.image_model
    )
    parts: list[dict[str, Any]] = []
    if refs:
        first_ref = refs[0]
        data_bytes: bytes | None = None
        mime_type: str | None = None

        local_candidate = Path(first_ref)
        if local_candidate.exists() and local_candidate.is_file():
            data_bytes = local_candidate.read_bytes()
            mime_type = mimetypes.guess_type(local_candidate.name)[0] or "image/png"
        elif first_ref.lower().startswith(("http://", "https://")):
            response = requests.get(first_ref, timeout=60)
            response.raise_for_status()
            data_bytes = response.content
            mime_type = response.headers.get("Content-Type") or "image/png"

        if data_bytes:
            parts.append(
                {
                    "inlineData": {
                        "mimeType": mime_type,
                        "data": base64.b64encode(data_bytes).decode("ascii"),
                    }
                }
            )

    parts.append(
        {
            "text": (
                f"{prompt.dense_prompt}\n\n"
                f"Negative prompt: {prompt.negative_prompt}\n"
                f"Aspect ratio: {prompt.settings.aspect_ratio}\n"
                f"Resolution target: {prompt.settings.resolution}\n"
                "Preserve subject count and action exactly when references are provided."
            )
        }
    )

    payload = {
        "contents": [{"parts": parts}],
        "generationConfig": {"responseModalities": ["image", "text"]},
    }
    response = requests.post(
        f"{endpoint}?key={secrets.google_api_key}",
        json=payload,
        timeout=settings.providers.google.timeout_seconds,
    )
    response.raise_for_status()
    image_bytes = _extract_google_inline_image(response.json() or {})
    ensure_dir(output_path.parent)
    output_path.write_bytes(image_bytes)


def _extract_kie_image(payload: dict[str, Any]) -> bytes:
    for key in ("image_base64", "base64", "data"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return base64.b64decode(value)
    data = payload.get("data", {}) if isinstance(payload.get("data"), dict) else {}
    for key in ("image_base64", "base64"):
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return base64.b64decode(value)
    image_url = payload.get("url") or data.get("url")
    if image_url:
        response = requests.get(str(image_url), timeout=120)
        response.raise_for_status()
        return response.content
    raise ValueError("Kie response did not include image bytes.")


def _aspect_ratio_pair(ratio: str) -> tuple[int, int]:
    left, right = ratio.split(":", maxsplit=1)
    return int(left.strip()), int(right.strip())


def _center_crop_to_ratio(image_bytes: bytes, target_ratio: str) -> bytes:
    target_w, target_h = _aspect_ratio_pair(target_ratio)
    with Image.open(io.BytesIO(image_bytes)) as image:
        width, height = image.size
        current = width / height
        desired = target_w / target_h

        if abs(current - desired) < 1e-4:
            out = io.BytesIO()
            image.save(out, format="PNG")
            return out.getvalue()

        if current > desired:
            new_width = int(height * desired)
            offset_x = (width - new_width) // 2
            box = (offset_x, 0, offset_x + new_width, height)
        else:
            new_height = int(width / desired)
            offset_y = (height - new_height) // 2
            box = (0, offset_y, width, offset_y + new_height)

        cropped = image.crop(box)
        out = io.BytesIO()
        cropped.save(out, format="PNG")
        return out.getvalue()


def _normalize_kie_aspect_ratio(raw_ratio: str) -> tuple[str, str | None]:
    ratio = (raw_ratio or "").strip()
    allowed = {
        "1:1",
        "16:9",
        "9:16",
        "4:3",
        "3:4",
        "4:5",
        "5:4",
        "3:2",
        "2:3",
        "21:9",
        "9:21",
        "auto",
    }
    if ratio in allowed:
        return ratio, None
    if ratio == "2:1":
        return "16:9", "2:1"
    if ratio == "1:2":
        return "9:16", "1:2"
    return "auto", None


def _sync_to_cloud(local_path: Path, settings: AppSettings, batch_id: str) -> str | None:
    if not settings.cloud_sync.enabled:
        return None
    cloud_root = settings.cloud_sync.root
    ensure_dir(cloud_root)
    target_dir = ensure_dir(cloud_root / batch_id)
    target = target_dir / local_path.name
    shutil.copy2(local_path, target)
    return str(target)


def _generate_with_kie(
    prompt: CanonicalPrompt,
    output_path: Path,
    settings: AppSettings,
    secrets: RuntimeSecrets,
    reference_images: list[str],
) -> None:
    if not secrets.kie_api_key:
        raise ValueError("KIE_API_KEY is required for kie provider.")

    def _to_kie_resolution(raw: str) -> str:
        value = raw.strip().lower()
        if value in {"4k", "4096x4096"}:
            return "4K"
        if "2048" in value or value in {"2k", "2048x2048"}:
            return "2K"
        return "1K"

    remote_refs = [ref for ref in reference_images if ref.lower().startswith(("http://", "https://"))]
    sent_aspect, post_crop_ratio = _normalize_kie_aspect_ratio(prompt.settings.aspect_ratio)

    payload = {
        "model": "nano-banana-2",
        "input": {
            "prompt": (
                f"{prompt.dense_prompt}\n\n"
                f"Negative prompt: {prompt.negative_prompt}\n"
                "Maintain realistic proportions and avoid over-stylization."
            ),
            "google_search": False,
            "resolution": _to_kie_resolution(prompt.settings.resolution),
            "output_format": "png",
            "aspect_ratio": sent_aspect,
            "image_input": remote_refs,
        },
        "config": {"webhookConfig": {"endpoint": "", "secret": ""}},
    }
    task_response = requests.post(
        settings.providers.kie.image_endpoint,
        headers={
            "Authorization": f"Bearer {secrets.kie_api_key}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=settings.providers.kie.timeout_seconds,
    )
    task_response.raise_for_status()
    task_payload = task_response.json() or {}
    if int(task_payload.get("code", 500)) != 200:
        raise ValueError(task_payload.get("msg") or "Kie createTask failed")
    task_id = str((task_payload.get("data", {}) or {}).get("taskId", "")).strip()
    if not task_id:
        raise ValueError("Kie createTask response missing taskId")

    deadline = time.time() + settings.providers.kie.timeout_seconds
    result_payload: dict[str, Any] | None = None
    while time.time() < deadline:
        status_response = requests.get(
            settings.providers.kie.task_status_endpoint,
            headers={"Authorization": f"Bearer {secrets.kie_api_key}"},
            params={"taskId": task_id},
            timeout=60,
        )
        status_response.raise_for_status()
        status_payload = status_response.json() or {}
        data = status_payload.get("data", {}) or {}
        state = str(data.get("state", "")).lower()
        if state == "success":
            result_payload = status_payload
            break
        if state in {"fail", "failed"}:
            raise ValueError(data.get("failMsg") or "Kie generation failed")
        time.sleep(3)

    if result_payload is None:
        raise TimeoutError("Kie image generation timed out while polling task status.")

    data = result_payload.get("data", {}) or {}
    result_json_raw = data.get("resultJson")
    if not result_json_raw:
        result_json_raw = (data.get("response", {}) or {}).get("resultJson")
    parsed_result: dict[str, Any] = {}
    if isinstance(result_json_raw, str) and result_json_raw.strip():
        try:
            parsed_result = json.loads(result_json_raw)
        except json.JSONDecodeError:
            parsed_result = {}
    elif isinstance(result_json_raw, dict):
        parsed_result = result_json_raw

    result_urls = parsed_result.get("resultUrls") or []
    if not result_urls:
        raise ValueError("Kie task completed but no resultUrls were returned.")
    image_url = str(result_urls[0])
    image_download = requests.get(image_url, timeout=120)
    image_download.raise_for_status()
    image_bytes = image_download.content
    if post_crop_ratio:
        image_bytes = _center_crop_to_ratio(image_bytes=image_bytes, target_ratio=post_crop_ratio)
    ensure_dir(output_path.parent)
    output_path.write_bytes(image_bytes)


def generate_single(
    prompt: CanonicalPrompt | dict[str, Any] | str,
    refs: list[str],
    provider: str,
    settings: AppSettings,
    pricing: PricingConfig,
    secrets: RuntimeSecrets,
    output_dir: Path,
    name_hint: str,
) -> LocalAsset:
    canonical = normalize_prompt_schema(prompt)
    resolution = canonical.settings.resolution
    file_name = f"{slugify(name_hint)}-{provider}-{now_utc_slug()}.png"
    output_path = ensure_dir(output_dir) / file_name
    if settings.generation.dry_run:
        _write_placeholder_image(output_path)
    else:
        if provider == "google":
            _generate_with_google(
                prompt=canonical,
                output_path=output_path,
                settings=settings,
                secrets=secrets,
                refs=refs,
            )
        elif provider == "kie":
            _generate_with_kie(
                prompt=canonical,
                output_path=output_path,
                settings=settings,
                secrets=secrets,
                reference_images=refs,
            )
        else:
            raise ValueError(f"Unsupported provider: {provider}")

    return LocalAsset(
        provider=provider,
        local_path=output_path,
        cost_usd=_image_unit_price(pricing=pricing, provider=provider, resolution=resolution),
    )


def generate_images(
    records: list[dict[str, Any]],
    provider_order: list[str],
    *,
    settings: AppSettings,
    pricing: PricingConfig,
    secrets: RuntimeSecrets,
    output_dir: Path,
    batch_id: str,
    airtable: AirtableClient | None = None,
    uploader: KieUploader | None = None,
    single_generator: Callable[..., LocalAsset] = generate_single,
) -> GenerationResult:
    ensure_dir(output_dir)
    result_items: list[GenerationItem] = []
    total_cost = 0.0
    success_count = 0
    failure_count = 0

    for row in records:
        ad_name = str(row.get("ad_name", "ad-variant"))
        record_id = row.get("airtable_record_id")
        prompt_payload = row.get("prompt_json")
        refs = [str(item) for item in row.get("reference_images", []) if str(item).strip()]
        last_error = ""
        generated_asset: LocalAsset | None = None

        for provider in provider_order:
            try:
                generated_asset = single_generator(
                    prompt=prompt_payload,
                    refs=refs,
                    provider=provider,
                    settings=settings,
                    pricing=pricing,
                    secrets=secrets,
                    output_dir=output_dir,
                    name_hint=ad_name,
                )
                break
            except Exception as exc:  # noqa: BLE001
                last_error = f"{provider}: {exc}"

        if generated_asset is None:
            failure_count += 1
            item = GenerationItem(
                record_id=record_id,
                ad_name=ad_name,
                success=False,
                error=last_error or "unknown generation error",
            )
            if airtable and record_id:
                airtable.update_record_assets(
                    record_id=record_id,
                    image_status="Rejected",
                    error=item.error,
                )
            result_items.append(item)
            continue

        public_url = None
        cloud_path = None
        cloud_path = _sync_to_cloud(local_path=generated_asset.local_path, settings=settings, batch_id=batch_id)
        upload_error: str | None = None
        if uploader:
            try:
                public_url = uploader.upload_file(generated_asset.local_path)
            except Exception as exc:  # noqa: BLE001
                upload_error = str(exc)

        if upload_error:
            failure_count += 1
            error_message = f"upload_failed: {upload_error}"
            if airtable and record_id:
                airtable.update_record_assets(
                    record_id=record_id,
                    image_status="Rejected",
                    error=error_message,
                    cloud_asset_path=cloud_path,
                )
            result_items.append(
                GenerationItem(
                    record_id=record_id,
                    ad_name=ad_name,
                    success=False,
                    provider=generated_asset.provider,
                    local_path=generated_asset.local_path,
                    cloud_path=cloud_path,
                    error=error_message,
                )
            )
            continue

        total_cost += generated_asset.cost_usd
        success_count += 1

        if airtable and record_id:
            airtable.update_record_assets(
                record_id=record_id,
                image_url=public_url,
                image_status="Generated",
                actual_cost=generated_asset.cost_usd,
                provider=generated_asset.provider,
                error="",
                cloud_asset_path=cloud_path,
            )

        # Keep generation metadata side-by-side for debugging.
        metadata_path = generated_asset.local_path.with_suffix(".json")
        metadata_path.write_text(
            json.dumps(
                {
                    "batch_id": batch_id,
                    "record_id": record_id,
                    "provider": generated_asset.provider,
                    "public_url": public_url,
                    "cloud_path": cloud_path,
                    "cost_usd": generated_asset.cost_usd,
                },
                ensure_ascii=True,
                indent=2,
            ),
            encoding="utf-8",
        )

        result_items.append(
            GenerationItem(
                record_id=record_id,
                ad_name=ad_name,
                success=True,
                provider=generated_asset.provider,
                local_path=generated_asset.local_path,
                public_url=public_url,
                cloud_path=cloud_path,
                cost_usd=generated_asset.cost_usd,
            )
        )

    return GenerationResult(
        items=result_items,
        success_count=success_count,
        failure_count=failure_count,
        total_cost_usd=round(total_cost, 4),
    )
