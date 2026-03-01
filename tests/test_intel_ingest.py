from pathlib import Path

from tools.intel_ingest import load_convexe_context


def test_load_convexe_context_reads_latest_weekly_and_prompt_pack(tmp_path: Path) -> None:
    root = tmp_path / "output" / "meta-ads"
    weekly_run = root / "weekly" / "20260301_010000"
    weekly_run.mkdir(parents=True, exist_ok=True)
    (weekly_run / "convexe-weekly-creative-plan.md").write_text(
        "# Convexe Weekly Creative Plan\n\ncontent",
        encoding="utf-8",
    )

    pack_dir = root / "ikonick" / "20260301_020000" / "analysis"
    pack_dir.mkdir(parents=True, exist_ok=True)
    (pack_dir / "convexe-prompt-pack.md").write_text("# Prompt Pack", encoding="utf-8")

    context = load_convexe_context(root)
    assert context["weekly_plan_path"] is not None
    assert context["prompt_pack_paths"]
    assert context["source_insight"].startswith("prompt_pack:")


def test_load_convexe_context_fallback_when_missing(tmp_path: Path) -> None:
    context = load_convexe_context(tmp_path / "missing-root")
    assert context["weekly_plan_path"] is None
    assert context["source_insight"] == "fallback_brand_profile"
