from __future__ import annotations

from pathlib import Path

from tools.upload import KieUploader


def compose_product_name(
    *,
    frame_code: str | None,
    frame_name: str | None,
    product: str | None,
) -> str:
    code = (frame_code or "").strip()
    name = (frame_name or "").strip()
    fallback = (product or "").strip()

    if code and name:
        return f"[{code}] {name}"
    if name:
        return name
    if code:
        return f"Quadro {code}"
    if fallback:
        return fallback
    raise ValueError("Informe --frame-code, --frame-name ou --product.")


def infer_mode(reference_urls: list[str], explicit_mode: str | None = None) -> str:
    mode = (explicit_mode or "").strip().lower()
    if mode in {"txt2img", "img2img"}:
        return mode
    return "img2img" if reference_urls else "txt2img"


def prepare_reference_urls(
    *,
    mockup_paths: list[str],
    mockup_urls: list[str],
    uploader: KieUploader,
) -> list[str]:
    urls: list[str] = [url.strip() for url in mockup_urls if url.strip()]
    for raw_path in mockup_paths:
        candidate = Path(raw_path).expanduser().resolve()
        if not candidate.exists():
            raise FileNotFoundError(f"Mockup path not found: {candidate}")
        uploaded_url = uploader.upload_file(candidate)
        urls.append(uploaded_url)
    # Preserve order and de-duplicate
    deduped: list[str] = []
    seen: set[str] = set()
    for url in urls:
        if url in seen:
            continue
        seen.add(url)
        deduped.append(url)
    return deduped
