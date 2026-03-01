from __future__ import annotations

from typing import Any, Sequence

from tools.config import PricingConfig
from tools.models import CostEstimate, CostLine


def _unit_price(pricing: PricingConfig, kind: str, provider: str, unit_key: str) -> float:
    lookup = pricing.images if kind == "image" else pricing.videos
    provider_table = lookup.get(provider, {})
    if unit_key in provider_table:
        return float(provider_table[unit_key])
    if provider_table:
        return float(next(iter(provider_table.values())))
    raise KeyError(f"No pricing found for kind={kind}, provider={provider}, key={unit_key}")


def estimate_generation_cost(batch: Sequence[dict[str, Any]], pricing: PricingConfig) -> CostEstimate:
    lines: list[CostLine] = []
    total = 0.0
    for row in batch:
        kind = str(row.get("kind", "image"))
        provider = str(row.get("provider", "kie"))
        unit_key = str(row.get("unit_key", "1024x1792"))
        quantity = int(row.get("quantity", 1))
        unit_cost = _unit_price(pricing=pricing, kind=kind, provider=provider, unit_key=unit_key)
        subtotal = unit_cost * quantity
        lines.append(
            CostLine(
                kind=kind,
                provider=provider,
                unit_key=unit_key,
                quantity=quantity,
                unit_cost_usd=unit_cost,
                subtotal_usd=subtotal,
            )
        )
        total += subtotal

    return CostEstimate(currency=pricing.currency, lines=lines, total_usd=round(total, 4))


def estimate_image_batch_cost(
    count: int,
    provider: str,
    resolution: str,
    pricing: PricingConfig,
) -> CostEstimate:
    return estimate_generation_cost(
        batch=[
            {
                "kind": "image",
                "provider": provider,
                "unit_key": resolution,
                "quantity": count,
            }
        ],
        pricing=pricing,
    )


def assert_budget_or_raise(
    estimate: CostEstimate,
    max_budget_usd: float,
    allow_over_budget: bool = False,
) -> None:
    if estimate.total_usd <= max_budget_usd:
        return
    if allow_over_budget:
        return
    raise ValueError(
        f"Estimated cost USD {estimate.total_usd:.2f} exceeds batch limit USD {max_budget_usd:.2f}."
    )
