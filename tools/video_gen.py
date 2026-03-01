from __future__ import annotations

import base64
from pathlib import Path
from typing import Any

import requests

from tools.airtable import AirtableClient
from tools.config import AppSettings, PricingConfig, RuntimeSecrets
from tools.costs import assert_budget_or_raise, estimate_generation_cost
from tools.prompt_engine import build_video_prompt_from_image, normalize_prompt_schema
from tools.upload import KieUploader
from tools.utils import ensure_dir, now_utc_slug, slugify


PLACEHOLDER_MP4_B64 = "AAAAIGZ0eXBpc29tAAACAGlzb21pc28yYXZjMQAAAGxtZGF0AAAAAA=="


def _write_placeholder_video(path: Path) -> None:
    ensure_dir(path.parent)
    path.write_bytes(base64.b64decode(PLACEHOLDER_MP4_B64))


def _video_price(pricing: PricingConfig, provider: str, unit_key: str) -> float:
    table = pricing.videos.get(provider, {})
    if unit_key in table:
        return float(table[unit_key])
    if table:
        return float(next(iter(table.values())))
    raise KeyError(f"No video pricing for provider={provider}")


def _generate_video_google(
    *,
    video_prompt: str,
    start_frame_url: str,
    output_path: Path,
    settings: AppSettings,
    secrets: RuntimeSecrets,
) -> None:
    if not secrets.google_api_key:
        raise ValueError("GOOGLE_API_KEY is required for real video generation.")

    endpoint = settings.providers.google.video_endpoint_template.format(
        model=settings.providers.google.video_model
    )
    payload = {
        "prompt": video_prompt,
        "input": {"startFrameUrl": start_frame_url},
    }
    response = requests.post(
        f"{endpoint}?key={secrets.google_api_key}",
        json=payload,
        timeout=settings.providers.google.timeout_seconds,
    )
    response.raise_for_status()
    result = response.json() or {}
    video_url = result.get("videoUrl") or result.get("url")
    if not video_url:
        raise ValueError("Google video response did not include downloadable video URL.")
    video_bytes = requests.get(video_url, timeout=120).content
    ensure_dir(output_path.parent)
    output_path.write_bytes(video_bytes)


def generate_videos_from_approved(
    *,
    airtable: AirtableClient,
    settings: AppSettings,
    pricing: PricingConfig,
    secrets: RuntimeSecrets,
    uploader: KieUploader,
    from_approved: bool,
    confirm_cost: bool,
    allow_over_budget: bool = False,
) -> dict[str, Any]:
    if not from_approved:
        raise ValueError("This command currently supports only --from-approved mode.")

    approved = airtable.fetch_records_by_status(image_status="Approved")
    if not approved:
        return {"records": 0, "generated": 0, "total_cost_usd": 0.0}

    estimate = estimate_generation_cost(
        batch=[
            {
                "kind": "video",
                "provider": "google",
                "unit_key": "veo-3.1-5s",
                "quantity": len(approved),
            }
        ],
        pricing=pricing,
    )
    if settings.generation.require_explicit_cost_confirmation and not confirm_cost:
        raise ValueError("Missing --confirm-cost for video generation.")
    assert_budget_or_raise(
        estimate=estimate,
        max_budget_usd=settings.generation.max_batch_cost_usd,
        allow_over_budget=allow_over_budget,
    )

    generated = 0
    total_cost = 0.0
    for record in approved:
        record_id = record.get("id")
        fields = record.get("fields", {}) or {}
        ad_name = str(fields.get("Ad Name", "ad-video"))
        image_list = fields.get("Generated Image", []) or []
        if not image_list:
            continue
        start_frame_url = str((image_list[0] or {}).get("url", "")).strip()
        if not start_frame_url:
            continue

        prompt_json_raw = fields.get("Prompt JSON", "{}")
        prompt = normalize_prompt_schema(prompt_json_raw)
        video_prompt = build_video_prompt_from_image(prompt=prompt, generated_image_url=start_frame_url)

        file_path = settings.paths.video_root / f"{slugify(ad_name)}-{now_utc_slug()}.mp4"
        if settings.generation.dry_run:
            _write_placeholder_video(file_path)
        else:
            _generate_video_google(
                video_prompt=video_prompt,
                start_frame_url=start_frame_url,
                output_path=file_path,
                settings=settings,
                secrets=secrets,
            )

        public_url = uploader.upload_file(file_path)
        unit_cost = _video_price(pricing=pricing, provider="google", unit_key="veo-3.1-5s")
        total_cost += unit_cost
        generated += 1

        if record_id:
            airtable.update_record_assets(
                record_id=record_id,
                video_url=public_url,
                video_status="Generated",
                provider="google",
                actual_cost=unit_cost,
                error="",
                video_prompt=video_prompt,
            )

    return {
        "records": len(approved),
        "generated": generated,
        "total_cost_usd": round(total_cost, 4),
    }
