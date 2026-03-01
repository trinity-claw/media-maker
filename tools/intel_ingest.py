from __future__ import annotations

from pathlib import Path
from typing import Any


def _latest_by_mtime(paths: list[Path]) -> Path | None:
    if not paths:
        return None
    return sorted(paths, key=lambda item: item.stat().st_mtime, reverse=True)[0]


def _read_excerpt(path: Path, limit: int = 3000) -> str:
    if not path.exists():
        return ""
    content = path.read_text(encoding="utf-8", errors="ignore")
    return content[:limit].strip()


def _fallback_brand_context() -> dict[str, Any]:
    return {
        "brand_name": "Convexe",
        "strategy_mode": "motivational_first",
        "creative_boundary": "premium_seductive_moderate",
        "collections": [
            "motivacionais_inspiradores",
            "renascentistas",
            "esculturas",
            "cultura_pop",
        ],
    }


def load_convexe_context(meta_ads_root: Path) -> dict[str, Any]:
    context: dict[str, Any] = {
        "source_root": str(meta_ads_root),
        "weekly_plan_path": None,
        "weekly_plan_excerpt": "",
        "prompt_pack_paths": [],
        "prompt_pack_excerpts": [],
        "fallback_brand_profile": _fallback_brand_context(),
        "source_insight": "fallback_brand_profile",
    }

    if not meta_ads_root.exists():
        return context

    weekly_candidates = list(meta_ads_root.glob("weekly/*/convexe-weekly-creative-plan.md"))
    weekly_latest = _latest_by_mtime(weekly_candidates)
    if weekly_latest:
        context["weekly_plan_path"] = str(weekly_latest)
        context["weekly_plan_excerpt"] = _read_excerpt(weekly_latest)
        context["source_insight"] = f"weekly_plan:{weekly_latest.parent.name}"

    prompt_pack_candidates = list(meta_ads_root.glob("*/*/analysis/convexe-prompt-pack.md"))
    ranked_prompt_packs = sorted(
        prompt_pack_candidates,
        key=lambda item: item.stat().st_mtime,
        reverse=True,
    )[:3]
    for prompt_pack in ranked_prompt_packs:
        context["prompt_pack_paths"].append(str(prompt_pack))
        context["prompt_pack_excerpts"].append(_read_excerpt(prompt_pack))

    if context["prompt_pack_paths"]:
        sources = [Path(path).parts[-4] for path in context["prompt_pack_paths"]]
        context["source_insight"] = "prompt_pack:" + ",".join(sources)

    return context
