from __future__ import annotations

import json
from typing import Any

from tools.models import CanonicalPrompt, PromptSettings


SAFETY_CONSTRAINTS = [
    "no real people likeness",
    "no beauty filters",
    "no professional retouching",
    "no synthetic skin smoothing",
]


BRAND_CONSTRAINTS = [
    "convexe premium motivational direction",
    "aspirational but brand-safe tone",
    "optional contemporary renaissance vandalized cues",
]


def _as_dict(raw_prompt: CanonicalPrompt | dict[str, Any] | str) -> dict[str, Any]:
    if isinstance(raw_prompt, CanonicalPrompt):
        return raw_prompt.model_dump()
    if isinstance(raw_prompt, str):
        stripped = raw_prompt.strip()
        if stripped.startswith("{") and stripped.endswith("}"):
            return json.loads(stripped)
        return {"prompt": stripped}
    return raw_prompt


def normalize_prompt_schema(raw_prompt: CanonicalPrompt | dict[str, Any] | str) -> CanonicalPrompt:
    payload = _as_dict(raw_prompt)

    dense_prompt = (
        payload.get("dense_prompt")
        or payload.get("prompt")
        or payload.get("task_description")
        or "Ultra realistic ad image with explicit camera and lighting instructions."
    )

    settings_payload: dict[str, Any] = dict(payload.get("settings", {}) or {})
    if "style" not in settings_payload and payload.get("style"):
        settings_payload["style"] = payload.get("style")
    if "lighting" not in settings_payload and payload.get("lighting"):
        settings_payload["lighting"] = payload.get("lighting")
    if "resolution" not in settings_payload and payload.get("resolution"):
        settings_payload["resolution"] = payload.get("resolution")
    if "aspect_ratio" not in settings_payload and payload.get("aspect_ratio"):
        settings_payload["aspect_ratio"] = payload.get("aspect_ratio")
    if "lens" not in settings_payload and payload.get("camera"):
        settings_payload["lens"] = payload.get("camera")

    deep_grid = payload.get("deep_grid")
    deep_keys = {
        "subject",
        "output",
        "environment",
        "multi_panel_layout",
        "image_quality_simulation",
        "explicit_restrictions",
        "negative_prompt",
    }
    if deep_grid is None and deep_keys.intersection(payload.keys()):
        deep_grid = {key: payload[key] for key in deep_keys if key in payload}

    return CanonicalPrompt(
        task=str(payload.get("task", "convexe_ultra_realistic_ad")),
        mode=str(payload.get("mode", "txt2img")),
        dense_prompt=str(dense_prompt),
        negative_prompt=str(payload.get("negative_prompt", "")),
        settings=PromptSettings.model_validate(settings_payload),
        deep_grid=deep_grid if isinstance(deep_grid, dict) else None,
        brand_constraints=list(payload.get("brand_constraints", BRAND_CONSTRAINTS)),
        safety_constraints=list(payload.get("safety_constraints", SAFETY_CONSTRAINTS)),
        render_text=payload.get("render_text"),
        metadata=dict(payload.get("metadata", {}) or {}),
    )


def build_prompt_variants(
    brief: dict[str, Any],
    brand_context: dict[str, Any],
    n: int,
) -> list[CanonicalPrompt]:
    product = str(brief.get("product", "Convexe wall art"))
    style_hint = str(brief.get("style", "premium documentary realism"))
    mode = str(brief.get("mode", "txt2img"))
    resolution = str(brief.get("resolution", "1024x1792"))
    aspect_ratio = str(brief.get("aspect_ratio", "4:5"))
    render_text = brief.get("copy_ptbr")
    source_insight = brand_context.get("source_insight", "fallback_brand_profile")

    style_variants = [
        ("documentary realism", "direct on-camera flash, realistic contrast", "85mm lens, f/2.0, ISO 200"),
        ("lifestyle influencer realism", "window natural light with subtle shadows", "50mm lens, f/2.8, ISO 250"),
        ("premium product realism", "controlled side lighting, high texture reveal", "90mm macro lens, f/4.0, ISO 180"),
        ("candid mobile realism", "mixed ambient indoor light, slight noise", "26mm smartphone lens equivalent, f/1.9, ISO 400"),
    ]

    prompts: list[CanonicalPrompt] = []
    for idx in range(n):
        style, lighting, lens = style_variants[idx % len(style_variants)]
        dense_prompt = (
            f"Ultra-realistic ad photo for {product}. "
            f"Visual direction: {style_hint}, variation style: {style}. "
            "Preserve natural textures and imperfections. "
            "No beautification or skin smoothing. "
            "Frame composition for paid social conversion. "
            "Premium aspirational environment, motivational mood, brand-safe. "
            f"Lighting: {lighting}. Camera setup: {lens}. "
            "Sharp focus on product and subject interaction. "
            "Documentary realism. Do not stylize as CGI."
        )
        deep_grid = {
            "subject": {
                "identity": "synthetic persona only",
                "appearance": {
                    "skin_texture": "visible pores and realistic imperfections",
                    "expression": "confident, aspirational, natural",
                },
            },
            "output": {
                "type": "single_image",
                "aspect_ratio": aspect_ratio,
                "resolution": resolution,
            },
            "environment": {
                "location": "premium home-office or modern living room",
                "lighting": {"type": lighting, "quality": "realistic non-studio"},
            },
            "explicit_restrictions": {
                "no_professional_retouching": True,
                "no_ai_beauty_filters": True,
                "no_studio_lighting": False,
            },
        }
        canonical = normalize_prompt_schema(
            {
                "task": "convexe_creative_variant",
                "mode": mode,
                "prompt": dense_prompt,
                "negative_prompt": (
                    "unrealistic skin, beauty filter, plastic look, cartoon, cgi, overprocessed lighting"
                ),
                "settings": {
                    "resolution": resolution,
                    "aspect_ratio": aspect_ratio,
                    "style": style,
                    "lighting": lighting,
                    "camera_angle": "eye-level product-forward portrait",
                    "lens": lens,
                    "quality": "high detail, unretouched realism",
                },
                "deep_grid": deep_grid,
                "render_text": render_text,
                "metadata": {
                    "variant_index": idx + 1,
                    "source_insight": source_insight,
                    "collection": "motivacionais_inspiradores",
                    "funnel_stage": "mofu",
                    "hook_type": "status_aspiration",
                },
            }
        )
        prompts.append(canonical)

    return prompts


def build_video_prompt_from_image(
    prompt: CanonicalPrompt,
    generated_image_url: str,
) -> str:
    return (
        "Create a short ultra-realistic ad video from the provided start frame. "
        "Keep the same subject identity, product design, and visual style. "
        "Use subtle camera push-in, natural motion, premium aspirational tone, and safe ad pacing. "
        f"Start frame URL: {generated_image_url}. "
        f"Primary visual guidance: {prompt.dense_prompt}"
    )
