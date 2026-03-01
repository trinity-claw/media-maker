from tools.prompt_engine import build_prompt_variants, normalize_prompt_schema


def test_normalize_prompt_from_dense_schema() -> None:
    prompt = normalize_prompt_schema(
        {
            "prompt": "Ultra-realistic portrait with explicit camera details",
            "settings": {"resolution": "1024x1792", "aspect_ratio": "4:5"},
            "negative_prompt": "blurry",
        }
    )
    assert prompt.mode == "txt2img"
    assert prompt.settings.resolution == "1024x1792"
    assert "blurry" in prompt.negative_prompt
    assert "plastic skin" in prompt.negative_prompt


def test_normalize_prompt_from_deep_grid_shape() -> None:
    prompt = normalize_prompt_schema(
        {
            "task": "deep_grid_test",
            "subject": {"identity": "synthetic"},
            "output": {"aspect_ratio": "4:5"},
            "environment": {"location": "studio"},
        }
    )
    assert prompt.deep_grid is not None
    assert "subject" in prompt.deep_grid


def test_build_prompt_variants_returns_expected_count() -> None:
    prompts = build_prompt_variants(
        brief={"product": "Quadro Atlas", "style": "premium", "mode": "txt2img"},
        brand_context={"source_insight": "prompt_pack:ikonick"},
        n=4,
    )
    assert len(prompts) == 4
    assert prompts[0].metadata["source_insight"] == "prompt_pack:ikonick"
