from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


DEFAULT_NEGATIVE_BLOCKERS = [
    "blurry",
    "low resolution",
    "distorted face",
    "extra fingers",
    "plastic skin",
    "beautification filters",
    "heavy makeup",
    "airbrushed texture",
    "cartoon",
    "cgi",
    "oversaturated colors",
]


class PromptSettings(BaseModel):
    resolution: str = "1024x1792"
    aspect_ratio: str = "4:5"
    style: str = "photorealistic, documentary realism"
    lighting: str = "direct on-camera flash, high contrast"
    camera_angle: str = "eye-level portrait framing"
    lens: str = "85mm lens, f/2.0, ISO 200"
    quality: str = "high detail, visible skin texture, unretouched"


class CanonicalPrompt(BaseModel):
    task: str
    mode: Literal["txt2img", "img2img"] = "txt2img"
    dense_prompt: str
    negative_prompt: str = ""
    settings: PromptSettings = Field(default_factory=PromptSettings)
    deep_grid: dict[str, Any] | None = None
    brand_constraints: list[str] = Field(default_factory=list)
    safety_constraints: list[str] = Field(default_factory=list)
    render_text: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def add_default_negative_blockers(self) -> "CanonicalPrompt":
        current = [entry.strip() for entry in self.negative_prompt.split(",") if entry.strip()]
        for blocker in DEFAULT_NEGATIVE_BLOCKERS:
            if blocker not in current:
                current.append(blocker)
        self.negative_prompt = ", ".join(current)
        return self


class CostLine(BaseModel):
    kind: Literal["image", "video"]
    provider: str
    unit_key: str
    quantity: int = 1
    unit_cost_usd: float
    subtotal_usd: float


class CostEstimate(BaseModel):
    currency: str = "USD"
    lines: list[CostLine] = Field(default_factory=list)
    total_usd: float = 0.0


class LocalAsset(BaseModel):
    provider: str
    local_path: Path
    public_url: str | None = None
    cost_usd: float = 0.0


class GenerationItem(BaseModel):
    record_id: str | None = None
    ad_name: str
    success: bool
    provider: str | None = None
    local_path: Path | None = None
    public_url: str | None = None
    error: str | None = None
    cost_usd: float = 0.0


class GenerationResult(BaseModel):
    items: list[GenerationItem] = Field(default_factory=list)
    success_count: int = 0
    failure_count: int = 0
    total_cost_usd: float = 0.0
