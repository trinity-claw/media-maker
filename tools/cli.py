from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from tools.airtable import AirtableClient, AirtableCredentials
from tools.config import load_pricing, load_runtime_secrets, load_settings
from tools.costs import assert_budget_or_raise, estimate_image_batch_cost
from tools.image_gen import generate_images
from tools.intel_ingest import load_convexe_context
from tools.prompt_engine import build_prompt_variants
from tools.upload import KieUploader
from tools.utils import ensure_dir, now_utc_slug, read_json, slugify, write_json
from tools.video_gen import generate_videos_from_approved


def _make_airtable_client() -> AirtableClient:
    settings = load_settings()
    secrets = load_runtime_secrets()
    secrets.require("airtable_api_key", "airtable_base_id")
    return AirtableClient(
        credentials=AirtableCredentials(
            api_key=secrets.airtable_api_key,
            base_id=secrets.airtable_base_id,
        ),
        table_name=settings.airtable.table_name,
        timeout_seconds=settings.airtable.timeout_seconds,
    )


def _make_uploader() -> KieUploader:
    settings = load_settings()
    secrets = load_runtime_secrets()
    return KieUploader(
        api_key=secrets.kie_api_key,
        upload_endpoint=settings.providers.kie.upload_endpoint,
        timeout_seconds=settings.providers.kie.timeout_seconds,
        dry_run=settings.generation.dry_run,
    )


def cmd_init(_: argparse.Namespace) -> int:
    settings = load_settings()
    ensure_dir(settings.paths.references_root)
    ensure_dir(settings.paths.output_root)
    ensure_dir(settings.paths.batch_root)
    ensure_dir(settings.paths.runs_root)
    ensure_dir(settings.paths.image_root)
    ensure_dir(settings.paths.video_root)
    print("OK: projeto inicializado.")
    return 0


def cmd_validate_config(_: argparse.Namespace) -> int:
    settings = load_settings()
    pricing = load_pricing()
    default_order = ", ".join(settings.generation.default_provider_order)
    print(f"Projeto: {settings.project.name}")
    print(f"Dry run: {settings.generation.dry_run}")
    print(f"Provider order: {default_order}")
    print(f"Budget max USD: {settings.generation.max_batch_cost_usd:.2f}")
    print(f"Meta-ads root: {settings.paths.convexe_meta_ads_root}")
    print(f"Pricing currency: {pricing.currency}")
    if not settings.paths.convexe_meta_ads_root.exists():
        print("WARN: caminho de inteligencia Convexe nao encontrado; fallback sera usado.")
    return 0


def cmd_airtable_setup(_: argparse.Namespace) -> int:
    client = _make_airtable_client()
    table = client.setup_content_table()
    print(f"OK: tabela pronta em Airtable -> {table.get('name', 'Content')}")
    return 0


def _serialize_reference_attachments(reference_urls: list[str]) -> list[dict[str, str]]:
    return [{"url": url} for url in reference_urls if url.strip()]


def cmd_campaign_create(args: argparse.Namespace) -> int:
    settings = load_settings()
    pricing = load_pricing()
    client = _make_airtable_client()

    context = load_convexe_context(settings.paths.convexe_meta_ads_root)
    brief = {
        "product": args.product,
        "style": args.style,
        "mode": args.mode,
        "resolution": args.resolution or settings.generation.default_resolution,
        "aspect_ratio": args.aspect_ratio or settings.generation.default_aspect_ratio,
        "copy_ptbr": args.copy_text,
    }
    prompts = build_prompt_variants(brief=brief, brand_context=context, n=args.variations)
    if not prompts:
        raise ValueError("Nenhuma variante de prompt foi gerada.")

    batch_id = args.batch_id or f"{slugify(args.product)}-{now_utc_slug()}"
    primary_provider = (
        args.primary_provider
        or settings.generation.default_provider_order[0]
    )
    estimate = estimate_image_batch_cost(
        count=len(prompts),
        provider=primary_provider,
        resolution=brief["resolution"],
        pricing=pricing,
    )

    records_payload: list[dict[str, Any]] = []
    for idx, prompt in enumerate(prompts, start=1):
        ad_name = f"{args.product} v{idx:02d}"
        records_payload.append(
            {
                "Ad Name": ad_name,
                "Product": args.product,
                "Reference Images": _serialize_reference_attachments(args.reference or []),
                "Image Prompt": prompt.dense_prompt,
                "Image Model": "nano-banana-2",
                "Image Status": "Pending",
                "Video Model": "veo-3.1",
                "Video Status": "Pending",
                "Prompt JSON": prompt.model_dump_json(indent=2),
                "Prompt Schema": settings.generation.default_prompt_schema,
                "Provider Used": primary_provider,
                "Estimated Cost": estimate.lines[0].unit_cost_usd,
                "Batch ID": batch_id,
                "Generation Error": "",
                "Convexe Insight Source": str(context.get("source_insight", "fallback_brand_profile")),
            }
        )

    created = client.create_content_records(records_payload)
    tasks: list[dict[str, Any]] = []
    for row, prompt in zip(created, prompts, strict=False):
        tasks.append(
            {
                "airtable_record_id": row.get("id"),
                "ad_name": row.get("fields", {}).get("Ad Name", "ad-variant"),
                "prompt_json": prompt.model_dump(),
                "reference_images": args.reference or [],
                "expected_resolution": prompt.settings.resolution,
            }
        )

    batch_payload = {
        "batch_id": batch_id,
        "created_at_utc": now_utc_slug(),
        "product": args.product,
        "style": args.style,
        "provider_order": settings.generation.default_provider_order,
        "estimate_total_usd": estimate.total_usd,
        "source_insight": context.get("source_insight"),
        "records": tasks,
    }
    batch_path = settings.paths.batch_root / f"{batch_id}.json"
    write_json(batch_path, batch_payload)

    print(f"OK: campanha criada. Batch ID: {batch_id}")
    print(f"Registros Airtable criados: {len(created)}")
    print(f"Custo estimado total: USD {estimate.total_usd:.2f}")
    print(f"Batch salvo em: {batch_path}")
    return 0


def cmd_image_generate(args: argparse.Namespace) -> int:
    settings = load_settings()
    pricing = load_pricing()
    secrets = load_runtime_secrets()
    client = _make_airtable_client()
    uploader = _make_uploader()

    batch_path = settings.paths.batch_root / f"{args.batch_id}.json"
    if not batch_path.exists():
        raise FileNotFoundError(f"Batch file not found: {batch_path}")
    batch = read_json(batch_path)
    records = list(batch.get("records", []))
    if not records:
        raise ValueError("Batch has no records.")

    provider_order = args.provider_order or batch.get("provider_order") or settings.generation.default_provider_order
    resolution = str(records[0].get("expected_resolution", settings.generation.default_resolution))
    estimate = estimate_image_batch_cost(
        count=len(records),
        provider=provider_order[0],
        resolution=resolution,
        pricing=pricing,
    )

    if settings.generation.require_explicit_cost_confirmation and not args.confirm_cost:
        raise ValueError("Use --confirm-cost para executar geracao de imagem.")
    assert_budget_or_raise(
        estimate=estimate,
        max_budget_usd=settings.generation.max_batch_cost_usd,
        allow_over_budget=args.allow_over_budget,
    )

    run_dir = ensure_dir(settings.paths.image_root / slugify(batch.get("product", "campaign")) / now_utc_slug())
    result = generate_images(
        records=records,
        provider_order=list(provider_order),
        settings=settings,
        pricing=pricing,
        secrets=secrets,
        output_dir=run_dir,
        batch_id=args.batch_id,
        airtable=client,
        uploader=uploader,
    )

    audit_path = settings.paths.runs_root / f"{args.batch_id}-images-{now_utc_slug()}.json"
    write_json(
        audit_path,
        {
            "batch_id": args.batch_id,
            "estimate_total_usd": estimate.total_usd,
            "result": result.model_dump(mode="json"),
        },
    )
    print(f"OK: geracao concluida. Success={result.success_count}, Failures={result.failure_count}")
    print(f"Custo real acumulado: USD {result.total_cost_usd:.2f}")
    print(f"Audit: {audit_path}")
    return 0


def cmd_status(_: argparse.Namespace) -> int:
    settings = load_settings()
    secrets = load_runtime_secrets()

    batch_files = sorted(settings.paths.batch_root.glob("*.json"))
    print(f"Batches locais: {len(batch_files)}")

    if not secrets.airtable_api_key or not secrets.airtable_base_id:
        print("Airtable: credenciais ausentes, exibindo apenas status local.")
        return 0

    client = _make_airtable_client()
    records = client.fetch_records_by_status()
    image_counter = Counter()
    video_counter = Counter()
    for row in records:
        fields = row.get("fields", {}) or {}
        image_counter[str(fields.get("Image Status", "Unknown"))] += 1
        video_counter[str(fields.get("Video Status", "Unknown"))] += 1

    print(f"Total registros Airtable: {len(records)}")
    print(f"Image status: {dict(image_counter)}")
    print(f"Video status: {dict(video_counter)}")
    return 0


def cmd_video_generate(args: argparse.Namespace) -> int:
    settings = load_settings()
    pricing = load_pricing()
    secrets = load_runtime_secrets()
    client = _make_airtable_client()
    uploader = _make_uploader()

    if settings.generation.require_explicit_cost_confirmation and not args.confirm_cost:
        raise ValueError("Use --confirm-cost para executar geracao de video.")

    summary = generate_videos_from_approved(
        airtable=client,
        settings=settings,
        pricing=pricing,
        secrets=secrets,
        uploader=uploader,
        from_approved=args.from_approved,
        confirm_cost=args.confirm_cost,
        allow_over_budget=args.allow_over_budget,
    )
    audit_path = settings.paths.runs_root / f"video-run-{now_utc_slug()}.json"
    write_json(audit_path, summary)
    print(f"OK: videos processados={summary['generated']} de {summary['records']}")
    print(f"Custo real acumulado: USD {summary['total_cost_usd']:.2f}")
    print(f"Audit: {audit_path}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Media-Maker Convexe CLI")
    sub = parser.add_subparsers(dest="command")

    p_init = sub.add_parser("init", help="Inicializa estrutura local.")
    p_init.set_defaults(func=cmd_init)

    p_validate = sub.add_parser("validate-config", help="Valida arquivos de config.")
    p_validate.set_defaults(func=cmd_validate_config)

    p_airtable = sub.add_parser("airtable", help="Operacoes Airtable.")
    p_airtable_sub = p_airtable.add_subparsers(dest="airtable_command")
    p_airtable_setup = p_airtable_sub.add_parser("setup", help="Cria/valida tabela Content.")
    p_airtable_setup.set_defaults(func=cmd_airtable_setup)

    p_campaign = sub.add_parser("campaign", help="Operacoes de campanha.")
    p_campaign_sub = p_campaign.add_subparsers(dest="campaign_command")
    p_campaign_create = p_campaign_sub.add_parser("create", help="Cria batch e registros Pending.")
    p_campaign_create.add_argument("--product", required=True)
    p_campaign_create.add_argument("--style", default="premium documentary realism")
    p_campaign_create.add_argument("--variations", type=int, default=3)
    p_campaign_create.add_argument("--mode", default="txt2img", choices=["txt2img", "img2img"])
    p_campaign_create.add_argument("--resolution", default=None)
    p_campaign_create.add_argument("--aspect-ratio", default=None)
    p_campaign_create.add_argument("--copy-text", default=None)
    p_campaign_create.add_argument("--batch-id", default=None)
    p_campaign_create.add_argument("--primary-provider", default=None, choices=["kie", "google"])
    p_campaign_create.add_argument("--reference", action="append", default=[])
    p_campaign_create.set_defaults(func=cmd_campaign_create)

    p_image = sub.add_parser("image", help="Operacoes de imagem.")
    p_image_sub = p_image.add_subparsers(dest="image_command")
    p_image_generate = p_image_sub.add_parser("generate", help="Gera imagens para um batch.")
    p_image_generate.add_argument("--batch-id", required=True)
    p_image_generate.add_argument("--confirm-cost", action="store_true")
    p_image_generate.add_argument("--allow-over-budget", action="store_true")
    p_image_generate.add_argument("--provider-order", nargs="+", default=None)
    p_image_generate.set_defaults(func=cmd_image_generate)

    p_status = sub.add_parser("status", help="Mostra status local + Airtable.")
    p_status.set_defaults(func=cmd_status)

    p_video = sub.add_parser("video", help="Operacoes de video.")
    p_video_sub = p_video.add_subparsers(dest="video_command")
    p_video_generate = p_video_sub.add_parser("generate", help="Gera videos para imagens aprovadas.")
    p_video_generate.add_argument("--from-approved", action="store_true")
    p_video_generate.add_argument("--confirm-cost", action="store_true")
    p_video_generate.add_argument("--allow-over-budget", action="store_true")
    p_video_generate.set_defaults(func=cmd_video_generate)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not hasattr(args, "func"):
        parser.print_help()
        return 1
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
