import pytest

from tools.config import PricingConfig
from tools.costs import assert_budget_or_raise, estimate_generation_cost


def _pricing() -> PricingConfig:
    return PricingConfig(
        currency="USD",
        images={"kie": {"1024x1792": 0.06}},
        videos={"google": {"veo-3.1-5s": 0.6}},
    )


def test_estimate_generation_cost_image() -> None:
    estimate = estimate_generation_cost(
        batch=[{"kind": "image", "provider": "kie", "unit_key": "1024x1792", "quantity": 5}],
        pricing=_pricing(),
    )
    assert estimate.total_usd == 0.3
    assert len(estimate.lines) == 1


def test_budget_guardrail_blocks_when_over_limit() -> None:
    estimate = estimate_generation_cost(
        batch=[{"kind": "video", "provider": "google", "unit_key": "veo-3.1-5s", "quantity": 5}],
        pricing=_pricing(),
    )
    with pytest.raises(ValueError):
        assert_budget_or_raise(estimate=estimate, max_budget_usd=1.0, allow_over_budget=False)
