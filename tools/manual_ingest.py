from __future__ import annotations

from math import gcd
from pathlib import Path

from PIL import Image

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
        try:
            uploaded_url = uploader.upload_file(candidate)
            urls.append(uploaded_url)
        except Exception:  # noqa: BLE001
            # Fallback to local path so providers that support file inputs can still consume references.
            urls.append(str(candidate))
    # Preserve order and de-duplicate
    deduped: list[str] = []
    seen: set[str] = set()
    for url in urls:
        if url in seen:
            continue
        seen.add(url)
        deduped.append(url)
    return deduped


def infer_frame_ratio_from_mockup_paths(mockup_paths: list[str]) -> str | None:
    def _extract_visible_bbox_size(image: Image.Image) -> tuple[int, int] | None:
        if "A" not in image.getbands():
            return None
        alpha = image.getchannel("A")
        bbox = alpha.getbbox()
        if not bbox:
            return None
        left, top, right, bottom = bbox
        width = max(0, right - left)
        height = max(0, bottom - top)
        if width == 0 or height == 0:
            return None
        coverage = (width * height) / float(image.width * image.height)
        if coverage <= 0.02:
            return None
        return width, height

    def _normalized_ratio(width: int, height: int) -> str:
        common = [
            (1, 1),
            (5, 4),
            (4, 3),
            (3, 2),
            (16, 9),
            (2, 1),
            (21, 9),
            (4, 5),
            (3, 4),
            (2, 3),
            (9, 16),
            (1, 2),
        ]
        value = width / height
        best_pair = None
        best_delta = float("inf")
        for left, right in common:
            delta = abs((left / right) - value)
            if delta < best_delta:
                best_delta = delta
                best_pair = (left, right)
        if best_pair and best_delta <= 0.08:
            return f"{best_pair[0]}:{best_pair[1]}"
        factor = gcd(width, height)
        return f"{width // factor}:{height // factor}"

    candidates: list[tuple[float, int, int, int, int]] = []
    seen: set[Path] = set()
    for raw_path in mockup_paths:
        candidate = Path(raw_path).expanduser().resolve()
        if candidate in seen:
            continue
        seen.add(candidate)
        if not candidate.exists() or not candidate.is_file():
            continue
        try:
            with Image.open(candidate) as image:
                width, height = image.size
                visible_size = _extract_visible_bbox_size(image)
        except Exception:  # noqa: BLE001
            continue
        if width <= 0 or height <= 0:
            continue

        uses_visible_bbox = visible_size is not None
        if visible_size:
            width, height = visible_size
        ratio_value = width / height
        area = width * height
        path_text = str(candidate).lower()
        score = 0.0

        # Prefer references that carry transparent cutout of the actual frame object.
        if uses_visible_bbox:
            score += 8.0
        # Prefer dedicated frame sources over environment composites.
        if "mock ups - frame front" in path_text or "mock ups - frame angles" in path_text:
            score += 1.5
        if "front" in path_text or "angled" in path_text or "diagonal" in path_text:
            score += 0.5
        if "mockups em ambientes" in path_text:
            score -= 4.0
        if "logo" in path_text or "marca d" in path_text or "comprimido" in path_text:
            score -= 3.0
        if "sem moldura" in path_text:
            score += 2.0
        if "prontos & mock ups\\#" in path_text:
            score += 2.0

        # Prefer non-square ratios when available.
        if abs(ratio_value - 1.0) <= 0.08:
            score -= 2.0
        else:
            score += 2.0

        # Slight preference for higher-resolution references.
        score += min(area / 10_000_000.0, 1.5)

        candidates.append((score, area, width, height, len(candidates)))

    if not candidates:
        return None

    best_score, _area, best_width, best_height, _idx = max(candidates, key=lambda row: (row[0], row[1]))
    if best_score < -10.0:
        return None
    return _normalized_ratio(best_width, best_height)
