from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel, Field

from tools.utils import load_yaml, project_root


class ProjectSettings(BaseModel):
    name: str = "media-maker"
    locale: str = "pt-BR"
    timezone: str = "America/Sao_Paulo"


class PathSettings(BaseModel):
    convexe_meta_ads_root: Path = Path("../convexe-openclaw-marketing-team/output/meta-ads")
    references_root: Path = Path("references/inputs")
    output_root: Path = Path("output")
    batch_root: Path = Path("output/batches")
    runs_root: Path = Path("output/runs")
    image_root: Path = Path("output/images")
    video_root: Path = Path("output/videos")


class GenerationSettings(BaseModel):
    default_mode: str = "txt2img"
    default_resolution: str = "1024x1792"
    default_aspect_ratio: str = "4:5"
    default_prompt_schema: str = "hybrid"
    default_provider_order: list[str] = Field(default_factory=lambda: ["kie", "google"])
    max_batch_cost_usd: float = 20.0
    require_explicit_cost_confirmation: bool = True
    dry_run: bool = True


class BrandSettings(BaseModel):
    name: str = "Convexe"
    strategy_mode: str = "motivational_first"
    default_collections: list[str] = Field(
        default_factory=lambda: [
            "motivacionais_inspiradores",
            "renascentistas",
            "esculturas",
            "cultura_pop",
        ]
    )


class SafetySettings(BaseModel):
    synthetic_personas_only: bool = True
    forbid_real_people_likeness: bool = True
    forbid_beauty_filters: bool = True
    forbid_professional_retouch: bool = True
    forbid_fake_studio_when_documentary: bool = True


class KieProviderSettings(BaseModel):
    enabled: bool = True
    image_endpoint: str = "https://api.kie.ai/api/v1/jobs/createTask"
    task_status_endpoint: str = "https://api.kie.ai/api/v1/jobs/recordInfo"
    upload_endpoint: str = "https://kieai.redpandaai.co/api/file-stream-upload"
    video_endpoint: str = "https://api.kie.ai/api/v1/jobs/createTask"
    timeout_seconds: int = 240


class GoogleProviderSettings(BaseModel):
    enabled: bool = True
    image_model: str = "gemini-2.0-flash-preview-image-generation"
    image_endpoint_template: str = (
        "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    )
    video_model: str = "veo-3.1"
    video_endpoint_template: str = (
        "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateVideo"
    )
    timeout_seconds: int = 180


class ProvidersSettings(BaseModel):
    kie: KieProviderSettings = Field(default_factory=KieProviderSettings)
    google: GoogleProviderSettings = Field(default_factory=GoogleProviderSettings)


class AirtableSettings(BaseModel):
    table_name: str = "Content"
    page_size: int = 100
    timeout_seconds: int = 30


class AssetPathsSettings(BaseModel):
    catalog_output: Path = Path("output/catalog/convexe-assets.json")
    raw_frames_root: Path = Path(
        r"G:\.shortcut-targets-by-id\1-5LjpWVLR1Ak4WlIlo0ImeXNbnS1UiiU\Convexe Canvas\Quadros\Quadros prontos & Mock Ups"
    )
    mockup_angles_root: Path = Path(
        r"G:\.shortcut-targets-by-id\1-5LjpWVLR1Ak4WlIlo0ImeXNbnS1UiiU\Convexe Canvas\Quadros\Quadros prontos & Mock Ups\Mock Ups - Frame Angles\Atualizados"
    )
    mockup_front_root: Path = Path(
        r"G:\.shortcut-targets-by-id\1-5LjpWVLR1Ak4WlIlo0ImeXNbnS1UiiU\Convexe Canvas\Quadros\Quadros prontos & Mock Ups\Mock Ups - Frame Front\Atualizados"
    )
    environments_root: Path = Path(
        r"G:\.shortcut-targets-by-id\1-5LjpWVLR1Ak4WlIlo0ImeXNbnS1UiiU\Convexe Canvas\Quadros\Quadros prontos & Mock Ups\Mockups em ambientes\1800x1800\Novo"
    )


class AppSettings(BaseModel):
    project: ProjectSettings = Field(default_factory=ProjectSettings)
    paths: PathSettings = Field(default_factory=PathSettings)
    generation: GenerationSettings = Field(default_factory=GenerationSettings)
    brand: BrandSettings = Field(default_factory=BrandSettings)
    safety: SafetySettings = Field(default_factory=SafetySettings)
    providers: ProvidersSettings = Field(default_factory=ProvidersSettings)
    airtable: AirtableSettings = Field(default_factory=AirtableSettings)
    assets: AssetPathsSettings = Field(default_factory=AssetPathsSettings)


class RuntimeSecrets(BaseModel):
    google_api_key: str = ""
    kie_api_key: str = ""
    airtable_api_key: str = ""
    airtable_base_id: str = ""
    airtable_table_id: str = ""

    def require(self, *keys: str) -> None:
        mapping = {
            "google_api_key": self.google_api_key,
            "kie_api_key": self.kie_api_key,
            "airtable_api_key": self.airtable_api_key,
            "airtable_base_id": self.airtable_base_id,
            "airtable_table_id": self.airtable_table_id,
        }
        missing = [key for key in keys if not mapping.get(key)]
        if missing:
            raise ValueError(f"Missing required secrets: {', '.join(missing)}")


class PricingConfig(BaseModel):
    currency: str = "USD"
    images: dict[str, dict[str, float]] = Field(default_factory=dict)
    videos: dict[str, dict[str, float]] = Field(default_factory=dict)


def _resolve_path(value: Path) -> Path:
    if value.is_absolute():
        return value
    return (project_root() / value).resolve()


def load_env(env_path: Path | None = None) -> Path:
    target = env_path or (project_root() / ".claude/.env")
    if target.exists():
        load_dotenv(target, override=False)
    return target


def load_settings(path: Path | None = None) -> AppSettings:
    load_env()
    cfg_path = path or (project_root() / "config/settings.yml")
    raw = load_yaml(cfg_path)
    settings = AppSettings.model_validate(raw)
    settings.paths.convexe_meta_ads_root = _resolve_path(settings.paths.convexe_meta_ads_root)
    settings.paths.references_root = _resolve_path(settings.paths.references_root)
    settings.paths.output_root = _resolve_path(settings.paths.output_root)
    settings.paths.batch_root = _resolve_path(settings.paths.batch_root)
    settings.paths.runs_root = _resolve_path(settings.paths.runs_root)
    settings.paths.image_root = _resolve_path(settings.paths.image_root)
    settings.paths.video_root = _resolve_path(settings.paths.video_root)
    settings.assets.catalog_output = _resolve_path(settings.assets.catalog_output)
    settings.assets.raw_frames_root = _resolve_path(settings.assets.raw_frames_root)
    settings.assets.mockup_angles_root = _resolve_path(settings.assets.mockup_angles_root)
    settings.assets.mockup_front_root = _resolve_path(settings.assets.mockup_front_root)
    settings.assets.environments_root = _resolve_path(settings.assets.environments_root)
    return settings


def load_pricing(path: Path | None = None) -> PricingConfig:
    cfg_path = path or (project_root() / "config/pricing.yml")
    raw = load_yaml(cfg_path)
    return PricingConfig.model_validate(raw)


def load_runtime_secrets() -> RuntimeSecrets:
    load_env()
    return RuntimeSecrets(
        google_api_key=os.getenv("GOOGLE_API_KEY", "").strip(),
        kie_api_key=os.getenv("KIE_API_KEY", "").strip(),
        airtable_api_key=os.getenv("AIRTABLE_API_KEY", "").strip(),
        airtable_base_id=os.getenv("AIRTABLE_BASE_ID", "").strip(),
        airtable_table_id=os.getenv("AIRTABLE_TABLE_ID", "").strip(),
    )
