from __future__ import annotations

from typing import Any

from tools.prompt_engine import build_prompt_variants


def create_campaign_prompt_variants(
    *,
    product: str,
    style: str,
    variations: int,
    mode: str,
    resolution: str,
    aspect_ratio: str,
    copy_ptbr: str | None,
    brand_context: dict[str, Any],
) -> list[dict[str, Any]]:
    prompts = build_prompt_variants(
        brief={
            "product": product,
            "style": style,
            "mode": mode,
            "resolution": resolution,
            "aspect_ratio": aspect_ratio,
            "copy_ptbr": copy_ptbr,
        },
        brand_context=brand_context,
        n=variations,
    )
    return [prompt.model_dump(mode="json") for prompt in prompts]
